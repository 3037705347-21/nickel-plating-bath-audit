"""Check titration conversion, coupled makeup, and batch-sheet output."""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, "/workspace")

from bath_audit.boric_acid import boric_acid_concentration_g_l
from bath_audit.chloride import chloride_concentration_g_l
from bath_audit.forecast import shift_start_targets_g_l
from bath_audit.makeup import makeup_plan
from bath_audit.nickel import nickel_concentration_g_l
from bath_audit.packaging import package_plan
from bath_audit.release_state import audit, surface


DATA = Path("/workspace/data")
NICKEL_G_PER_MOL = 58.6934
BORIC_ACID_G_PER_MOL = 61.832
CHLORIDE_G_PER_MOL = 35.453
COPPER_G_PER_MOL = 63.546
NICKEL_SULFATE_HEXAHYDRATE_G_PER_MOL = 262.84608
NICKEL_CHLORIDE_HEXAHYDRATE_G_PER_MOL = 237.69108
FARADAY_C_PER_MOL = 96485.33212


def _reference_concentration(
    sample_ml: float,
    titrant_ml: float,
    blank_ml: float,
    molarity: float,
    molar_mass: float,
) -> float:
    """Calculate a concentration with an independent titration formula."""
    net_ml = titrant_ml - blank_ml
    return net_ml / 1000.0 * molarity * molar_mass / (sample_ml / 1000.0)


def _reference_nickel(
    sample_ml: float,
    titrant_ml: float,
    blank_ml: float,
    molarity: float,
    dilution_factor: float,
    copper_g_l: float,
) -> float:
    """Calculate dilution-corrected nickel with copper interference removed."""
    apparent = _reference_concentration(
        sample_ml,
        titrant_ml,
        blank_ml,
        molarity,
        NICKEL_G_PER_MOL,
    )
    apparent *= dilution_factor
    return max(
        0.0,
        apparent - copper_g_l * NICKEL_G_PER_MOL / COPPER_G_PER_MOL,
    )


def _reference_forecast(
    tank_volume_l: float,
    planned_charge_ah: float,
    cathode_efficiency: float,
    dragout_l: float,
    target_nickel_g_l: float,
    target_boric_acid_g_l: float,
    target_chloride_g_l: float,
) -> dict[str, object]:
    """Calculate the pre-shift targets and forecast losses independently."""
    deposited_g = (
        planned_charge_ah
        * 3600.0
        * cathode_efficiency
        / (2.0 * FARADAY_C_PER_MOL)
        * NICKEL_G_PER_MOL
    )
    remaining_volume = tank_volume_l - dragout_l
    start = {
        "nickel": (target_nickel_g_l * tank_volume_l + deposited_g) / remaining_volume,
        "boric_acid": target_boric_acid_g_l * tank_volume_l / remaining_volume,
        "chloride": target_chloride_g_l * tank_volume_l / remaining_volume,
    }
    return {
        "nickel_deposited_g": deposited_g,
        "dragout_loss_g": {
            "nickel": start["nickel"] * dragout_l,
            "boric_acid": start["boric_acid"] * dragout_l,
            "chloride": start["chloride"] * dragout_l,
        },
        "shift_start_target_g_l": start,
    }


def _reference_makeup(
    tank_volume_l: float,
    nickel_g_l: float,
    boric_acid_g_l: float,
    chloride_g_l: float,
    target_nickel_g_l: float,
    target_boric_acid_g_l: float,
    target_chloride_g_l: float,
    nickel_sulfate_assay: float,
    nickel_chloride_assay: float,
    boric_acid_assay: float,
) -> dict[str, object]:
    """Calculate a coupled makeup plan without calling the workspace code."""
    nickel_need_g = max(0.0, target_nickel_g_l - nickel_g_l) * tank_volume_l
    boric_need_g = max(0.0, target_boric_acid_g_l - boric_acid_g_l) * tank_volume_l
    chloride_need_g = max(0.0, target_chloride_g_l - chloride_g_l) * tank_volume_l
    nickel_need_mol = nickel_need_g / NICKEL_G_PER_MOL
    chloride_need_mol = chloride_need_g / CHLORIDE_G_PER_MOL
    nickel_chloride_mol = chloride_need_mol / 2.0
    nickel_sulfate_mol = nickel_need_mol - nickel_chloride_mol
    if nickel_sulfate_mol < -1e-12:
        raise ValueError("infeasible coupled makeup")
    nickel_sulfate_mol = max(0.0, nickel_sulfate_mol)
    additions = {
        "nickel_sulfate_hexahydrate": nickel_sulfate_mol
        * NICKEL_SULFATE_HEXAHYDRATE_G_PER_MOL
        / nickel_sulfate_assay
        / 1000.0,
        "nickel_chloride_hexahydrate": nickel_chloride_mol
        * NICKEL_CHLORIDE_HEXAHYDRATE_G_PER_MOL
        / nickel_chloride_assay
        / 1000.0,
        "boric_acid": boric_need_g / boric_acid_assay / 1000.0,
    }
    predicted = {
        "nickel": nickel_g_l
        + (nickel_sulfate_mol + nickel_chloride_mol) * NICKEL_G_PER_MOL / tank_volume_l,
        "boric_acid": boric_acid_g_l + boric_need_g / tank_volume_l,
        "chloride": chloride_g_l
        + 2.0 * nickel_chloride_mol * CHLORIDE_G_PER_MOL / tank_volume_l,
    }
    return {
        "addition_kg": additions,
        "total_addition_kg": sum(additions.values()),
        "predicted_g_l": predicted,
    }


def _reference_package(
    tank_volume_l: float,
    nickel_g_l: float,
    boric_acid_g_l: float,
    chloride_g_l: float,
    exact_plan: dict[str, object],
    nickel_sulfate_assay: float,
    nickel_chloride_assay: float,
    boric_acid_assay: float,
    nickel_sulfate_bag_kg: float,
    nickel_chloride_bag_kg: float,
    boric_acid_bag_kg: float,
) -> dict[str, object]:
    """Convert exact additions to whole bags with independent arithmetic."""
    required = exact_plan["addition_kg"]
    bag_sizes = {
        "nickel_sulfate_hexahydrate": nickel_sulfate_bag_kg,
        "nickel_chloride_hexahydrate": nickel_chloride_bag_kg,
        "boric_acid": boric_acid_bag_kg,
    }
    bags = {}
    for key, bag_kg in bag_sizes.items():
        ratio = float(required[key]) / bag_kg
        nearest = round(ratio)
        if abs(ratio - nearest) <= 1e-12 * max(1.0, ratio):
            bags[key] = int(nearest)
        else:
            bags[key] = math.ceil(ratio)
    additions = {key: bags[key] * bag_sizes[key] for key in bag_sizes}
    sulfate_pure_g = (
        additions["nickel_sulfate_hexahydrate"] * 1000.0 * nickel_sulfate_assay
    )
    chloride_pure_g = (
        additions["nickel_chloride_hexahydrate"] * 1000.0 * nickel_chloride_assay
    )
    boric_pure_g = additions["boric_acid"] * 1000.0 * boric_acid_assay
    sulfate_mol = sulfate_pure_g / NICKEL_SULFATE_HEXAHYDRATE_G_PER_MOL
    chloride_mol = chloride_pure_g / NICKEL_CHLORIDE_HEXAHYDRATE_G_PER_MOL
    return {
        "addition_kg": additions,
        "bags": bags,
        "total_addition_kg": sum(additions.values()),
        "predicted_g_l": {
            "nickel": nickel_g_l
            + (sulfate_mol + chloride_mol) * NICKEL_G_PER_MOL / tank_volume_l,
            "boric_acid": boric_acid_g_l + boric_pure_g / tank_volume_l,
            "chloride": chloride_g_l
            + 2.0 * chloride_mol * CHLORIDE_G_PER_MOL / tank_volume_l,
        },
    }


def _sample_record() -> dict[str, str]:
    """Load the bundled simulated laboratory row."""
    with (DATA / "lab_record.csv").open(newline="", encoding="utf-8") as handle:
        return next(csv.DictReader(handle))


def _write_record(path: Path, fieldnames: list[str], row: dict[str, str]) -> None:
    """Write one CSV row in the requested column order."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)


def _run_cli(record_path: Path, output_path: Path) -> subprocess.CompletedProcess[str]:
    """Run the batch-sheet command in a subprocess."""
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "bath_audit.cli",
            str(record_path),
            str(output_path),
        ],
        cwd="/workspace",
        capture_output=True,
        text=True,
        timeout=60,
    )


def _reference_report(row: dict[str, str]) -> dict[str, object]:
    """Build an independent full batch report from one CSV row."""
    tank_volume_l = float(row["tank_volume_l"])
    dilution_factor = float(row["dilution_factor"])
    nickel = _reference_nickel(
        float(row["edta_sample_ml"]),
        float(row["edta_titrant_ml"]),
        float(row["edta_blank_ml"]),
        float(row["edta_molarity"]),
        dilution_factor,
        float(row["copper_g_l"]),
    )
    boric_acid = _reference_concentration(
        float(row["boric_sample_ml"]),
        float(row["naoh_titrant_ml"]),
        float(row["naoh_blank_ml"]),
        float(row["naoh_molarity"]),
        BORIC_ACID_G_PER_MOL,
    ) * dilution_factor
    chloride = _reference_concentration(
        float(row["chloride_sample_ml"]),
        float(row["agno3_titrant_ml"]),
        float(row["agno3_blank_ml"]),
        float(row["agno3_molarity"]),
        CHLORIDE_G_PER_MOL,
    ) * dilution_factor
    target_nickel = float(row["target_nickel_g_l"])
    target_boric = float(row["target_boric_acid_g_l"])
    target_chloride = float(row["target_chloride_g_l"])
    forecast = _reference_forecast(
        tank_volume_l,
        float(row["planned_charge_ah"]),
        float(row["cathode_efficiency"]),
        float(row["dragout_l"]),
        target_nickel,
        target_boric,
        target_chloride,
    )
    start_targets = forecast["shift_start_target_g_l"]
    exact_plan = _reference_makeup(
        tank_volume_l,
        nickel,
        boric_acid,
        chloride,
        start_targets["nickel"],
        start_targets["boric_acid"],
        start_targets["chloride"],
        float(row["nickel_sulfate_assay"]),
        float(row["nickel_chloride_assay"]),
        float(row["boric_acid_assay"]),
    )
    plan = _reference_package(
        tank_volume_l,
        nickel,
        boric_acid,
        chloride,
        exact_plan,
        float(row["nickel_sulfate_assay"]),
        float(row["nickel_chloride_assay"]),
        float(row["boric_acid_assay"]),
        float(row["nickel_sulfate_bag_kg"]),
        float(row["nickel_chloride_bag_kg"]),
        float(row["boric_acid_bag_kg"]),
    )
    return {
        "batch_id": row["batch_id"],
        "tank_volume_l": tank_volume_l,
        "analysis_g_l": {
            "nickel": nickel,
            "boric_acid": boric_acid,
            "chloride": chloride,
        },
        "deficit_g": {
            "nickel": max(0.0, start_targets["nickel"] - nickel) * tank_volume_l,
            "boric_acid": max(0.0, start_targets["boric_acid"] - boric_acid)
            * tank_volume_l,
            "chloride": max(0.0, start_targets["chloride"] - chloride)
            * tank_volume_l,
        },
        "addition_kg": plan["addition_kg"],
        "bags": plan["bags"],
        "total_addition_kg": plan["total_addition_kg"],
        "predicted_g_l": plan["predicted_g_l"],
        "forecast": forecast,
    }


def test_c1_edta_blank_correction():
    """case_id=NI-C1-01. 题面原文：「三种滴定的净体积都是」：EDTA净体积先行扣空白。"""
    expected = _reference_nickel(3.0, 14.25, 0.75, 0.05, 2.0, 0.10)
    actual = nickel_concentration_g_l(3.0, 14.25, 0.75, 0.05, 2.0, 0.10)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)


def test_c1_nickel_stoichiometry_and_molar_mass():
    """case_id=NI-C1-02. 题面原文：「镍与EDTA按摩尔比1:1反应」：使用指定摩尔质量。"""
    expected = _reference_nickel(2.0, 21.45, 0.32, 0.1, 1.5, 0.08)
    actual = nickel_concentration_g_l(2.0, 21.45, 0.32, 0.1, 1.5, 0.08)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)


def test_c1_zero_net_titrant_returns_zero():
    """case_id=NI-C1-03. 题面原文：「空白不得大于对应滴定体积」：等量时净体积为零。"""
    actual = nickel_concentration_g_l(2.0, 0.67, 0.67, 0.1, 1.0, 0.0)
    assert actual == pytest.approx(0.0, abs=1e-12)


def test_c1_invalid_sample_volume_rejected():
    """case_id=NI-C1-04. 题面原文：「槽容、取样体积、稀释倍数」都必须大于零：零体积应被拒绝。"""
    with pytest.raises(ValueError):
        nickel_concentration_g_l(0.0, 14.0, 0.5, 0.1, 1.0, 0.0)


def test_c1_copper_interference_subtracted():
    """case_id=NI-C1-05. 题面原文：「真正的镍浓度要从表观镍中减去」：扣除铜当量。"""
    apparent = _reference_concentration(2.0, 21.45, 0.32, 0.1, NICKEL_G_PER_MOL)
    expected = apparent - 0.25 * NICKEL_G_PER_MOL / COPPER_G_PER_MOL
    actual = nickel_concentration_g_l(2.0, 21.45, 0.32, 0.1, 1.0, 0.25)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)


def test_c1_dilution_factor_applied():
    """case_id=NI-C1-06. 题面原文：「非正稀释倍数」应报错：正常倍数应回到原槽液基准。"""
    dilute = nickel_concentration_g_l(3.0, 14.25, 0.75, 0.05, 1.0, 0.0)
    concentrated = nickel_concentration_g_l(3.0, 14.25, 0.75, 0.05, 2.5, 0.0)
    assert concentrated == pytest.approx(dilute * 2.5, rel=1e-12, abs=1e-12)


def test_c2_boric_blank_correction():
    """case_id=NI-C2-01. 题面原文：「硼酸加入甘露醇后」：先扣空白再换算。"""
    expected = _reference_concentration(4.0, 18.42, 0.22, 0.1, BORIC_ACID_G_PER_MOL)
    expected *= 2.0
    actual = boric_acid_concentration_g_l(4.0, 18.42, 0.22, 0.1, 2.0)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)


def test_c2_boric_one_to_one_stoichiometry():
    """case_id=NI-C2-02. 题面原文：「与NaOH按摩尔比1:1反应」：不得按二元酸乘二。"""
    expected = _reference_concentration(5.0, 12.25, 0.25, 0.1, BORIC_ACID_G_PER_MOL)
    actual = boric_acid_concentration_g_l(5.0, 12.25, 0.25, 0.1, 1.0)
    assert actual == pytest.approx(expected, rel=1e-12, abs=1e-12)


def test_c2_boric_zero_net_titrant_returns_zero():
    """case_id=NI-C2-03. 题面原文：「空白滴定体积、铜含量和带出液量不得为负」：等量净体积记为零。"""
    actual = boric_acid_concentration_g_l(4.0, 1.25, 1.25, 0.1, 1.0)
    assert actual == pytest.approx(0.0, abs=1e-12)


def test_c3_coupled_nickel_salts():
    """case_id=NI-C3-01; case_id=NI-C3-06. 题面原文：「镍和氯必须同时配平」：两种镍盐共同满足缺口。"""
    arguments = (2000.0, 60.0, 30.0, 20.0, 70.0, 35.0, 32.0, 0.985, 0.975, 0.995)
    expected = _reference_makeup(*arguments)
    actual = makeup_plan(*arguments)
    assert actual["addition_kg"]["nickel_chloride_hexahydrate"] > 0.0
    assert actual["addition_kg"]["nickel_sulfate_hexahydrate"] == pytest.approx(
        expected["addition_kg"]["nickel_sulfate_hexahydrate"], rel=1e-12, abs=1e-12
    )
    assert actual["addition_kg"]["nickel_chloride_hexahydrate"] == pytest.approx(
        expected["addition_kg"]["nickel_chloride_hexahydrate"], rel=1e-12, abs=1e-12
    )


def test_c3_assay_applied_to_raw_mass():
    """case_id=NI-C3-02. 题面原文：「商品有效含量表示每千克商品中该纯品的质量分数」：按有效含量折算商品量。"""
    arguments = (1750.0, 64.0, 29.0, 22.0, 74.0, 34.0, 31.0, 0.982, 0.968, 0.991)
    expected = _reference_makeup(*arguments)
    actual = makeup_plan(*arguments)
    assert actual["addition_kg"]["nickel_sulfate_hexahydrate"] == pytest.approx(
        expected["addition_kg"]["nickel_sulfate_hexahydrate"], rel=1e-12, abs=1e-12
    )
    assert actual["addition_kg"]["nickel_chloride_hexahydrate"] == pytest.approx(
        expected["addition_kg"]["nickel_chloride_hexahydrate"], rel=1e-12, abs=1e-12
    )
    assert actual["total_addition_kg"] == pytest.approx(
        expected["total_addition_kg"], rel=1e-12, abs=1e-12
    )


def test_c3_boric_acid_addition():
    """case_id=NI-C3-03. 题面原文：「硼酸纯品质量除以 `boric_acid_assay`」：按硼酸缺口折算。"""
    arguments = (900.0, 61.0, 27.5, 23.0, 72.0, 36.0, 30.0, 0.99, 0.97, 0.992)
    expected = _reference_makeup(*arguments)
    actual = makeup_plan(*arguments)
    assert actual["addition_kg"]["boric_acid"] == pytest.approx(
        expected["addition_kg"]["boric_acid"], rel=1e-12, abs=1e-12
    )
    assert actual["predicted_g_l"]["nickel"] == pytest.approx(
        expected["predicted_g_l"]["nickel"], rel=1e-12, abs=1e-12
    )
    assert actual["predicted_g_l"]["boric_acid"] == pytest.approx(
        expected["predicted_g_l"]["boric_acid"], rel=1e-12, abs=1e-12
    )
    assert actual["predicted_g_l"]["chloride"] == pytest.approx(
        expected["predicted_g_l"]["chloride"], rel=1e-12, abs=1e-12
    )


def test_c3_rejects_chloride_without_enough_nickel():
    """case_id=NI-C3-04. 题面原文：「若氯缺口所需的氯化镍摩尔数超过镍缺口摩尔数」：应拒绝配方。"""
    with pytest.raises(ValueError):
        makeup_plan(1000.0, 69.0, 34.0, 20.0, 70.0, 35.0, 30.0, 0.98, 0.97, 0.99)


def test_c3_equal_demand_uses_only_nickel_chloride():
    """case_id=NI-C3-05. 题面原文：「等于氯缺口摩尔数」：边界等量时允许全部用氯化镍。"""
    actual = makeup_plan(
        1000.0,
        60.0,
        30.0,
        20.0,
        65.86934,
        30.0,
        27.0906,
        1.0,
        1.0,
        1.0,
    )
    assert actual["addition_kg"]["nickel_sulfate_hexahydrate"] == pytest.approx(
        0.0, abs=1e-12
    )
    assert actual["addition_kg"]["nickel_chloride_hexahydrate"] == pytest.approx(
        23.769108, rel=1e-12, abs=1e-12
    )
    assert actual["predicted_g_l"]["nickel"] == pytest.approx(
        65.86934, rel=1e-12, abs=1e-12
    )
    assert actual["predicted_g_l"]["chloride"] == pytest.approx(
        27.0906, rel=1e-12, abs=1e-12
    )


def test_c4_faraday_deposition():
    """case_id=NI-C4-01. 题面原文：「先按下一班计划计算镍沉积量」：核对法拉第沉积式。"""
    arguments = (1200.0, 1800.0, 0.94, 15.0, 75.0, 35.0, 30.0)
    expected = _reference_forecast(*arguments)
    actual = shift_start_targets_g_l(*arguments)
    assert actual["nickel_deposited_g"] == pytest.approx(
        expected["nickel_deposited_g"], rel=1e-12, abs=1e-12
    )


def test_c4_dragout_raises_start_targets():
    """case_id=NI-C4-02. 题面原文：「C_start * (tank_volume_l - dragout_l) = C_end * tank_volume_l」：反算班前目标。"""
    arguments = (800.0, 450.0, 0.88, 24.0, 68.0, 32.0, 27.0)
    expected = _reference_forecast(*arguments)
    actual = shift_start_targets_g_l(*arguments)
    assert actual["shift_start_target_g_l"]["nickel"] == pytest.approx(
        expected["shift_start_target_g_l"]["nickel"], rel=1e-12, abs=1e-12
    )
    assert actual["shift_start_target_g_l"]["boric_acid"] == pytest.approx(
        expected["shift_start_target_g_l"]["boric_acid"], rel=1e-12, abs=1e-12
    )
    assert actual["shift_start_target_g_l"]["chloride"] == pytest.approx(
        expected["shift_start_target_g_l"]["chloride"], rel=1e-12, abs=1e-12
    )


def test_c4_dragout_losses_use_start_concentration():
    """case_id=NI-C4-03. 题面原文：「镍的带出损失为」：损失按班前浓度计算。"""
    arguments = (650.0, 700.0, 0.91, 18.0, 72.0, 34.0, 29.0)
    expected = _reference_forecast(*arguments)
    actual = shift_start_targets_g_l(*arguments)
    assert actual["dragout_loss_g"]["nickel"] == pytest.approx(
        expected["dragout_loss_g"]["nickel"], rel=1e-12, abs=1e-12
    )
    assert actual["dragout_loss_g"]["boric_acid"] == pytest.approx(
        expected["dragout_loss_g"]["boric_acid"], rel=1e-12, abs=1e-12
    )
    assert actual["dragout_loss_g"]["chloride"] == pytest.approx(
        expected["dragout_loss_g"]["chloride"], rel=1e-12, abs=1e-12
    )


def test_c4_rejects_full_tank_dragout():
    """case_id=NI-C4-04. 题面原文：「带出液量必须小于槽容」：等量也应拒绝。"""
    with pytest.raises(ValueError):
        shift_start_targets_g_l(1200.0, 100.0, 0.9, 1200.0, 75.0, 35.0, 30.0)


def test_c4_zero_charge_and_dragout_leave_targets_unchanged():
    """case_id=NI-C4-05. 题面原文：「计划安时数、空白滴定体积、铜含量和带出液量不得为负」：零值保持目标。"""
    actual = shift_start_targets_g_l(900.0, 0.0, 0.9, 0.0, 74.0, 33.0, 28.0)
    assert actual["nickel_deposited_g"] == pytest.approx(0.0, abs=1e-12)
    assert actual["shift_start_target_g_l"]["nickel"] == pytest.approx(74.0, abs=1e-12)
    assert actual["shift_start_target_g_l"]["boric_acid"] == pytest.approx(
        33.0, abs=1e-12
    )
    assert actual["shift_start_target_g_l"]["chloride"] == pytest.approx(
        28.0, abs=1e-12
    )


def test_c4_zero_efficiency_deposits_no_nickel():
    """case_id=NI-C4-06. 题面原文：「电流效率不在0到1之间」：区间内零效率应可用。"""
    actual = shift_start_targets_g_l(900.0, 600.0, 0.0, 0.0, 74.0, 33.0, 28.0)
    assert actual["nickel_deposited_g"] == pytest.approx(0.0, abs=1e-12)
    assert actual["shift_start_target_g_l"]["nickel"] == pytest.approx(74.0, abs=1e-12)


def test_c5_rounds_each_material_up_to_whole_bags():
    """case_id=NI-C5-01. 题面原文：「理论质量必须**向上取整**到对应包装规格的整数倍」：逐项整袋发料。"""
    arguments = (1000.0, 60.0, 30.0, 20.0, 70.0, 35.0, 32.0, 0.985, 0.975, 0.995)
    exact_plan = _reference_makeup(*arguments)
    expected = _reference_package(
        1000.0, 60.0, 30.0, 20.0, exact_plan, 0.985, 0.975, 0.995, 25.0, 10.0, 5.0
    )
    actual = package_plan(
        1000.0, 60.0, 30.0, 20.0, exact_plan, 0.985, 0.975, 0.995, 25.0, 10.0, 5.0
    )
    assert actual["bags"] == expected["bags"]
    assert actual["addition_kg"] == pytest.approx(expected["addition_kg"], rel=1e-12)
    assert actual["addition_kg"]["nickel_sulfate_hexahydrate"] % 25.0 == pytest.approx(
        0.0, abs=1e-12
    )
    assert actual["addition_kg"]["nickel_chloride_hexahydrate"] % 10.0 == pytest.approx(
        0.0, abs=1e-12
    )
    assert actual["addition_kg"]["boric_acid"] % 5.0 == pytest.approx(0.0, abs=1e-12)


def test_c5_predicted_uses_packaged_material_mass():
    """case_id=NI-C5-02; case_id=NI-C5-05. 题面原文：「必须用整袋商品质量乘有效含量得到的实际纯品摩尔数反算」：预测包含整袋超量。"""
    arguments = (1000.0, 60.0, 30.0, 20.0, 70.0, 35.0, 32.0, 0.985, 0.975, 0.995)
    exact_plan = _reference_makeup(*arguments)
    expected = _reference_package(
        1000.0, 60.0, 30.0, 20.0, exact_plan, 0.985, 0.975, 0.995, 25.0, 10.0, 5.0
    )
    actual = package_plan(
        1000.0, 60.0, 30.0, 20.0, exact_plan, 0.985, 0.975, 0.995, 25.0, 10.0, 5.0
    )
    assert actual["predicted_g_l"]["nickel"] == pytest.approx(
        expected["predicted_g_l"]["nickel"], rel=1e-12
    )
    assert actual["predicted_g_l"]["boric_acid"] == pytest.approx(
        expected["predicted_g_l"]["boric_acid"], rel=1e-12
    )
    assert actual["predicted_g_l"]["chloride"] == pytest.approx(
        expected["predicted_g_l"]["chloride"], rel=1e-12
    )
    assert actual["predicted_g_l"]["nickel"] > 70.0
    assert actual["predicted_g_l"]["chloride"] > 32.0


def test_c5_no_deficit_means_no_bags():
    """case_id=NI-C5-03. 题面原文：「缺口为零时袋数和补加质量都为零」：无缺口不发料。"""
    exact_plan = _reference_makeup(
        500.0, 80.0, 40.0, 35.0, 70.0, 35.0, 30.0, 0.985, 0.975, 0.995
    )
    actual = package_plan(
        500.0, 80.0, 40.0, 35.0, exact_plan, 0.985, 0.975, 0.995, 25.0, 10.0, 5.0
    )
    assert actual["bags"] == {
        "nickel_sulfate_hexahydrate": 0,
        "nickel_chloride_hexahydrate": 0,
        "boric_acid": 0,
    }
    assert actual["total_addition_kg"] == pytest.approx(0.0, abs=1e-12)


def test_c5_rejects_nonpositive_bag_size():
    """case_id=NI-C5-04. 题面原文：「包装规格非正时」：配置错误应拒绝。"""
    exact_plan = _reference_makeup(
        1000.0, 60.0, 30.0, 20.0, 70.0, 35.0, 32.0, 0.985, 0.975, 0.995
    )
    with pytest.raises(ValueError):
        package_plan(
            1000.0,
            60.0,
            30.0,
            20.0,
            exact_plan,
            0.985,
            0.975,
            0.995,
            0.0,
            10.0,
            5.0,
        )


def test_e2e_state_transition_matrix():
    """case_id=NI-F7-01; case_id=NI-F7-02. 题面原文：「同一条事件重复上报只能计算一次」：拒收、放行、再次拒收按最后状态计净数。"""
    assert audit()["transitions"] == {}
    events = [
        {"event_id": "evt-01", "batch_id": "B-2026-01", "status": "rejected"},
        {"event_id": "evt-02", "batch_id": "B-2026-01", "status": "released"},
        {"event_id": "evt-03", "batch_id": "B-2026-01", "status": "rejected"},
        {"event_id": "evt-02", "batch_id": "B-2026-01", "status": "released"},
    ]
    assert audit(events)["transitions"]["B-2026-01"] == [
        "rejected",
        "released",
        "rejected"
    ]
    summary = surface(events)
    assert summary["counts"] == {"released": 0, "rejected": 1}
    assert summary["event_count"] == 3
    assert surface()["counts"] == {"released": 0, "rejected": 0}


def test_e2e_sample_report():
    """case_id=NI-E2E-01. 题面原文：「输出JSON的根对象固定包含」：核对完整模拟批单。"""
    row = _sample_record()
    expected = _reference_report(row)
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory) / "batch.json"
        completed = _run_cli(DATA / "lab_record.csv", output)
        assert completed.returncode == 0, completed.stderr
        actual = json.loads(output.read_text(encoding="utf-8"))
    assert actual["batch_id"] == expected["batch_id"]
    assert actual["tank_volume_l"] == pytest.approx(expected["tank_volume_l"])
    assert actual["analysis_g_l"]["nickel"] == pytest.approx(
        expected["analysis_g_l"]["nickel"], rel=1e-12
    )
    assert actual["analysis_g_l"]["boric_acid"] == pytest.approx(
        expected["analysis_g_l"]["boric_acid"], rel=1e-12
    )
    assert actual["analysis_g_l"]["chloride"] == pytest.approx(
        expected["analysis_g_l"]["chloride"], rel=1e-12
    )
    assert actual["deficit_g"]["nickel"] == pytest.approx(
        expected["deficit_g"]["nickel"], rel=1e-12
    )
    assert actual["deficit_g"]["boric_acid"] == pytest.approx(
        expected["deficit_g"]["boric_acid"], rel=1e-12
    )
    assert actual["deficit_g"]["chloride"] == pytest.approx(
        expected["deficit_g"]["chloride"], rel=1e-12
    )
    assert actual["addition_kg"]["nickel_sulfate_hexahydrate"] == pytest.approx(
        expected["addition_kg"]["nickel_sulfate_hexahydrate"], rel=1e-12
    )
    assert actual["addition_kg"]["nickel_chloride_hexahydrate"] == pytest.approx(
        expected["addition_kg"]["nickel_chloride_hexahydrate"], rel=1e-12
    )
    assert actual["addition_kg"]["boric_acid"] == pytest.approx(
        expected["addition_kg"]["boric_acid"], rel=1e-12
    )
    assert actual["bags"] == expected["bags"]
    assert actual["total_addition_kg"] == pytest.approx(
        expected["total_addition_kg"], rel=1e-12
    )
    assert actual["predicted_g_l"]["nickel"] == pytest.approx(
        expected["predicted_g_l"]["nickel"], rel=1e-12
    )
    assert actual["predicted_g_l"]["boric_acid"] == pytest.approx(
        expected["predicted_g_l"]["boric_acid"], rel=1e-12
    )
    assert actual["predicted_g_l"]["chloride"] == pytest.approx(
        expected["predicted_g_l"]["chloride"], rel=1e-12
    )
    assert actual["forecast"]["nickel_deposited_g"] == pytest.approx(
        expected["forecast"]["nickel_deposited_g"], rel=1e-12
    )
    assert actual["forecast"]["dragout_loss_g"]["nickel"] == pytest.approx(
        expected["forecast"]["dragout_loss_g"]["nickel"], rel=1e-12
    )
    assert actual["forecast"]["dragout_loss_g"]["boric_acid"] == pytest.approx(
        expected["forecast"]["dragout_loss_g"]["boric_acid"], rel=1e-12
    )
    assert actual["forecast"]["dragout_loss_g"]["chloride"] == pytest.approx(
        expected["forecast"]["dragout_loss_g"]["chloride"], rel=1e-12
    )
    assert actual["forecast"]["shift_start_target_g_l"]["nickel"] == pytest.approx(
        expected["forecast"]["shift_start_target_g_l"]["nickel"], rel=1e-12
    )
    assert actual["forecast"]["shift_start_target_g_l"]["boric_acid"] == pytest.approx(
        expected["forecast"]["shift_start_target_g_l"]["boric_acid"], rel=1e-12
    )
    assert actual["forecast"]["shift_start_target_g_l"]["chloride"] == pytest.approx(
        expected["forecast"]["shift_start_target_g_l"]["chloride"], rel=1e-12
    )


def test_e2e_reordered_columns():
    """case_id=NI-E2E-02. 题面原文：「列顺序可以调整」：按列名映射而非位置。"""
    row = _sample_record()
    expected = _reference_report(row)
    with tempfile.TemporaryDirectory() as directory:
        directory_path = Path(directory)
        record_path = directory_path / "reordered.csv"
        output_path = directory_path / "batch.json"
        fieldnames = list(reversed(list(row.keys())))
        _write_record(record_path, fieldnames, row)
        completed = _run_cli(record_path, output_path)
        assert completed.returncode == 0, completed.stderr
        actual = json.loads(output_path.read_text(encoding="utf-8"))
    assert actual["analysis_g_l"]["nickel"] == pytest.approx(
        expected["analysis_g_l"]["nickel"], rel=1e-12
    )
    assert actual["analysis_g_l"]["boric_acid"] == pytest.approx(
        expected["analysis_g_l"]["boric_acid"], rel=1e-12
    )
    assert actual["analysis_g_l"]["chloride"] == pytest.approx(
        expected["analysis_g_l"]["chloride"], rel=1e-12
    )
    assert actual["addition_kg"]["nickel_sulfate_hexahydrate"] == pytest.approx(
        expected["addition_kg"]["nickel_sulfate_hexahydrate"], rel=1e-12
    )
    assert actual["addition_kg"]["nickel_chloride_hexahydrate"] == pytest.approx(
        expected["addition_kg"]["nickel_chloride_hexahydrate"], rel=1e-12
    )
    assert actual["addition_kg"]["boric_acid"] == pytest.approx(
        expected["addition_kg"]["boric_acid"], rel=1e-12
    )
    assert actual["bags"] == expected["bags"]
    assert actual["forecast"]["shift_start_target_g_l"]["nickel"] == pytest.approx(
        expected["forecast"]["shift_start_target_g_l"]["nickel"], rel=1e-12
    )


def test_e2e_invalid_row_preserves_output():
    """case_id=NI-E2E-03. 题面原文：「目标输出文件不得被创建或覆盖」：异常时保留旧文件。"""
    row = _sample_record()
    row["edta_blank_ml"] = "9.00"
    row["edta_titrant_ml"] = "1.00"
    with tempfile.TemporaryDirectory() as directory:
        directory_path = Path(directory)
        record_path = directory_path / "invalid.csv"
        output_path = directory_path / "batch.json"
        _write_record(record_path, list(row.keys()), row)
        output_path.write_text("existing result\n", encoding="utf-8")
        completed = _run_cli(record_path, output_path)
        assert completed.returncode != 0
        assert completed.stderr.strip() != ""
        assert output_path.read_text(encoding="utf-8") == "existing result\n"
