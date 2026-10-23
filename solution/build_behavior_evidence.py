#!/usr/bin/env python3
"""Build the current-version behavior matrix and isolated mutation evidence."""

from __future__ import annotations

import ast
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


TASK = Path(__file__).resolve().parent.parent
TESTS = TASK / "tests" / "test_outputs.py"
INSTRUCTION = TASK / "instruction.md"
OUT = TASK / "solution" / "verification"
MODULE_NAMES = (
    "boric_acid.py",
    "chloride.py",
    "cli.py",
    "forecast.py",
    "makeup.py",
    "nickel.py",
    "packaging.py",
    "release_state.py",
)


def case(
    case_id: str,
    test_name: str,
    source_text: str,
    category: str,
    target: str,
    old: str,
    new: str,
    operator: str,
    description: str,
) -> dict[str, str]:
    """Describe one independently killed behavior."""
    return {
        "case_id": case_id,
        "test_name": test_name,
        "source_text": source_text,
        "category": category,
        "target": target,
        "old": old,
        "new": new,
        "operator": operator,
        "description": description,
    }


CASES = [
    case("NI-C1-01", "test_c1_edta_blank_correction", "`batch_id`不能为空", "json_text",
         "solution/nickel.py", "net_ml = titrant_ml - blank_ml", "net_ml = titrant_ml",
         "statement_deletion", "删除EDTA空白扣除，保留总滴定体积"),
    case("NI-C1-02", "test_c1_nickel_stoichiometry_and_molar_mass", "所有数值必须是有限数", "json_text",
         "environment/workspace/bath_audit/constants.py", "NICKEL_G_PER_MOL = 58.6934", "NICKEL_G_PER_MOL = 58.69",
         "constant_replacement", "把镍摩尔质量替换为近似常数值"),
    case("NI-C1-03", "test_c1_zero_net_titrant_returns_zero", "空白不得大于对应滴定体积", "json_text",
         "solution/nickel.py", "if blank_ml < 0 or titrant_ml < blank_ml:",
         "if blank_ml < 0 or titrant_ml <= blank_ml:", "relational_operator",
         "把空白等于滴定体积的边界改为直接拒绝"),
    case("NI-C1-04", "test_c1_invalid_sample_volume_rejected", "输入校验或配方约束失败时", "json_text",
         "solution/nickel.py", "if sample_ml <= 0 or molarity <= 0 or dilution_factor <= 0:",
         "if sample_ml < 0 or molarity <= 0 or dilution_factor <= 0:", "boundary_shift",
         "把非正样品体积边界放宽为零"),
    case("NI-C1-05", "test_c1_copper_interference_subtracted", "原子吸收测了铜污染", "json_text",
         "solution/nickel.py", "corrected = apparent - copper_g_l * NICKEL_G_PER_MOL / COPPER_G_PER_MOL",
         "corrected = apparent + copper_g_l * NICKEL_G_PER_MOL / COPPER_G_PER_MOL",
         "relational_operator", "把铜干扰从扣减改为叠加"),
    case("NI-C1-06", "test_c1_dilution_factor_applied", "循环过滤后", "json_text",
         "solution/nickel.py", "net_ml / 1000.0\n        * molarity\n        * NICKEL_G_PER_MOL\n        / (sample_ml / 1000.0)\n        * dilution_factor",
         "net_ml / 1000.0\n        * molarity\n        * NICKEL_G_PER_MOL\n        / (sample_ml / 1000.0)",
         "statement_deletion", "删除镍浓度的稀释倍数换算"),
    case("NI-C2-01", "test_c2_boric_blank_correction", "硼酸加入甘露醇后", "json_text",
         "solution/boric_acid.py", "net_ml = titrant_ml - blank_ml", "net_ml = titrant_ml",
         "statement_deletion", "删除硼酸空白扣除"),
    case("NI-C2-02", "test_c2_boric_one_to_one_stoichiometry", "与NaOH按摩尔比1:1反应", "json_text",
         "solution/boric_acid.py", "moles = net_ml / 1000.0 * molarity",
         "moles = 2.0 * net_ml / 1000.0 * molarity", "constant_replacement",
         "把硼酸与NaOH的一比一计量改成二倍"),
    case("NI-C2-03", "test_c2_boric_zero_net_titrant_returns_zero", "三个浓度函数返回槽液g/L", "json_text",
         "solution/boric_acid.py", "if blank_ml < 0 or titrant_ml < blank_ml:",
         "if blank_ml < 0 or titrant_ml <= blank_ml:", "relational_operator",
         "把硼酸等量空白的边界改为拒绝"),
    case("NI-C3-01", "test_c3_coupled_nickel_salts", "补加单只能用六水硫酸镍", "json_text",
         "solution/makeup.py", "nickel_chloride_mol = chloride_need_mol / 2.0",
         "nickel_chloride_mol = 0.0", "constant_replacement",
         "把氯化镍摩尔数固定为零，忽略氯缺口"),
    case("NI-C3-06", "test_c3_coupled_nickel_salts", "镍和氯必须同时配平", "json_text",
         "solution/makeup.py", "chloride_need_mol = chloride_need_g / CHLORIDE_G_PER_MOL",
         "chloride_need_mol = 0.0", "constant_replacement",
         "把氯缺口摩尔数固定为零，破坏双盐联立"),
    case("NI-C3-02", "test_c3_assay_applied_to_raw_mass", "六水氯化镍和硼酸三种商品原料", "json_text",
         "solution/makeup.py", "sulfate_pure_g / nickel_sulfate_assay / 1000.0",
         "sulfate_pure_g / 1.0 / 1000.0", "constant_replacement",
         "忽略硫酸镍商品有效含量"),
    case("NI-C3-03", "test_c3_boric_acid_addition", "先得到精确的理论补加质量", "json_text",
         "solution/makeup.py", "\"boric_acid\": boric_pure_g / boric_acid_assay / 1000.0,",
         "\"boric_acid\": boric_pure_g / 1000.0,", "statement_deletion",
         "删除硼酸有效含量折算"),
    case("NI-C3-04", "test_c3_rejects_chloride_without_enough_nickel", "若氯缺口所需的氯化镍摩尔数超过镍缺口摩尔数", "json_text",
         "solution/makeup.py", "if nickel_sulfate_mol < -1e-12:",
         "if nickel_sulfate_mol < -1e12:", "boundary_shift",
         "把不可配平边界放大到实际上不触发"),
    case("NI-C3-05", "test_c3_equal_demand_uses_only_nickel_chloride", "现有两种镍盐无法完成配方", "json_text",
         "solution/makeup.py", "nickel_chloride_mol = chloride_need_mol / 2.0",
         "nickel_chloride_mol = chloride_need_mol / 2.0 + 0.01", "constant_replacement",
         "在等量边界额外加入氯化镍摩尔数"),
    case("NI-C4-01", "test_c4_faraday_deposition", "`nickel_deposited_g` 只计电解沉积，不带出", "json_text",
         "solution/forecast.py", "/ (2.0 * FARADAY_C_PER_MOL)",
         "/ (1.0 * FARADAY_C_PER_MOL)", "constant_replacement",
         "错误地把镍沉积的电子数改为一"),
    case("NI-C4-02", "test_c4_dragout_raises_start_targets", "C_start * (tank_volume_l - dragout_l) = C_end * tank_volume_l", "json_text",
         "solution/forecast.py", "remaining_volume = tank_volume_l - dragout_l",
         "remaining_volume = tank_volume_l", "statement_deletion",
         "删除带出液对剩余槽容的影响"),
    case("NI-C4-03", "test_c4_dragout_losses_use_start_concentration", "带出损失按上述班前浓度和带出液量计算", "json_text",
         "solution/forecast.py", "key: start[key] * dragout_l for key in (\"nickel\", \"boric_acid\", \"chloride\")",
         "key: start[key] * 0.0 for key in (\"nickel\", \"boric_acid\", \"chloride\")",
         "constant_replacement", "把带出损失错误置零"),
    case("NI-C4-04", "test_c4_rejects_full_tank_dragout", "带出液量必须小于槽容", "json_text",
         "solution/forecast.py", "if dragout_l < 0 or dragout_l >= tank_volume_l:",
         "if dragout_l < 0 or dragout_l > tank_volume_l:", "relational_operator",
         "允许带出体积恰好等于槽容"),
    case("NI-C4-05", "test_c4_zero_charge_and_dragout_leave_targets_unchanged", "计划安时数、空白滴定体积、铜含量和带出液量不得为负", "json_text",
         "solution/forecast.py", "if planned_charge_ah < 0:",
         "if planned_charge_ah <= 0:", "boundary_shift",
         "把计划安时数零值错误视为非法"),
    case("NI-C4-06", "test_c4_zero_efficiency_deposits_no_nickel", "电流效率不在0到1之间", "json_text",
         "solution/forecast.py", "if not 0.0 <= cathode_efficiency <= 1.0:",
         "if not 0.0 < cathode_efficiency <= 1.0:", "boundary_shift",
         "把零电流效率错误视为非法"),
    case("NI-C5-01", "test_c5_rounds_each_material_up_to_whole_bags", "理论质量必须**向上取整**到对应包装规格的整数倍", "json_text",
         "solution/packaging.py", "return math.ceil(ratio)", "return round(ratio)",
         "return_value", "把整袋向上取整改成四舍五入"),
    case("NI-C5-02", "test_c5_predicted_uses_packaged_material_mass", "必须用整袋商品质量乘有效含量得到的实际纯品摩尔数反算", "json_text",
         "solution/packaging.py",
         "+ (sulfate_mol + chloride_mol) * NICKEL_G_PER_MOL / tank_volume_l",
         "+ (sulfate_mol + chloride_mol) * NICKEL_G_PER_MOL / 1.0",
         "constant_replacement", "把整袋预测镍浓度的槽容换成1升"),
    case("NI-C5-05", "test_c5_predicted_uses_packaged_material_mass", "不能用理论质量、目标值或仅按理论质量计算的浓度直接填回", "json_text",
         "solution/packaging.py",
         "+ (sulfate_mol + chloride_mol) * NICKEL_G_PER_MOL / tank_volume_l",
         "+ 0.0",
         "statement_deletion", "删除预测镍浓度中的双盐摩尔贡献"),
    case("NI-C5-03", "test_c5_no_deficit_means_no_bags", "缺口为零时袋数和补加质量都为零", "json_text",
         "solution/packaging.py", "return int(nearest)", "return int(nearest) + 1",
         "boundary_shift", "无缺口时在整数袋数上多加一袋"),
    case("NI-C5-04", "test_c5_rejects_nonpositive_bag_size", "仓库不做拆袋", "json_text",
         "solution/packaging.py", "if bag_kg <= 0:", "if bag_kg < 0:",
         "boundary_shift", "允许零包装规格进入计算"),
    case("NI-F7-01", "test_e2e_state_transition_matrix", "同一条事件重复上报只能计算一次", "filesystem",
         "solution/release_state.py", "        if event_id in seen:\n            continue",
         "        if False:\n            continue", "condition_negation",
         "取消重复事件去重，破坏状态迁移流水"),
    case("NI-F7-02", "test_e2e_state_transition_matrix", "汇总时按该批号最后一条状态计入", "filesystem",
         "solution/release_state.py", "        counts[statuses[-1]] += 1",
         "        counts[statuses[-1]] += 2", "constant_replacement",
         "把最后状态净计数重复累加两次"),
    case("NI-F7-03", "test_e2e_cross_process_release_state", "每次先读取已有流水", "filesystem",
         "solution/release_state.py", "    existing = _load_state(state_path)",
         "    existing = []", "statement_deletion",
         "跨进程时丢弃已有状态日志"),
    case("NI-F7-04", "test_e2e_cross_process_release_state", "失败不得改动原文件", "filesystem",
         "solution/release_state.py",
         "        if not event_id or not batch_id or status not in VALID_STATES:",
         "        if not event_id or not batch_id:", "condition_negation",
         "允许非法状态写入交接流水"),
    case("NI-F7-05", "test_e2e_cross_process_release_state",
         "`bath_audit.release_state.audit(events=None, state_path=None)`", "filesystem",
         "solution/release_state.py",
         "def audit(\n"
         "    events: list[dict[str, str]] | None = None,\n"
         "    state_path: str | os.PathLike[str] | None = None,\n"
         ") -> dict[str, object]:",
         "def audit(\n"
         "    events: list[dict[str, str]] | None = None,\n"
         ") -> dict[str, object]:",
         "parameter_removal",
         "移除状态入口的持久化路径参数"),
    case("NI-F7-06", "test_e2e_state_write_failure_preserves_journal",
         "才可原子替换状态文件", "filesystem", "solution/release_state.py",
         "        os.replace(temporary, path)",
         "        path.write_text(\n"
         "            json.dumps({\"version\": STATE_VERSION, \"events\": events}, ensure_ascii=False),\n"
         "            encoding=\"utf-8\",\n"
         "        )",
         "atomic_write_replacement", "把原子替换改成直接覆盖目标文件"),
    case("NI-F7-07", "test_e2e_cross_process_release_state",
         "状态文件只保存版本号和有序事件", "filesystem", "solution/release_state.py",
         "STATE_VERSION = 1", "STATE_VERSION = 2",
         "constant_replacement", "把状态文件版本号写成错误值"),
    case("NI-F7-08", "test_e2e_cross_process_release_state",
         "读回的状态顺序仍应完整", "filesystem", "solution/release_state.py",
         "    return _deduplicated(_validated_events(state[\"events\"]))",
         "    return sorted(_deduplicated(_validated_events(state[\"events\"])), key=lambda event: event[\"status\"])",
         "sort_order_replacement", "按状态排序，破坏事件首次出现顺序"),
    case("NI-F7-09", "test_e2e_cross_process_release_state",
         "同一 `event_id` 只保留第一次上报", "filesystem", "solution/release_state.py",
         "        seen.add(event_id)", "        seen.discard(event_id)",
         "condition_negation", "不记录已见事件号，允许重复事件进入流水"),
    case("NI-F7-10", "test_e2e_cross_process_release_state",
         "重复上报也不得进入净计数", "filesystem", "solution/release_state.py",
         "        counts[statuses[-1]] += 1", "        counts[statuses[1]] += 1",
         "index_replacement", "按中间状态而不是最终状态累计净数"),
    case("NI-E2E-01", "test_e2e_sample_report", "`package_plan` 接收该配方", "filesystem",
         "environment/workspace/bath_audit/audit.py",
         "\"batch_id\": row[\"batch_id\"],", "\"batch_id\": \"MUTATED\",",
         "constant_replacement", "把批单编号替换为固定错误值"),
    case("NI-E2E-02", "test_e2e_reordered_columns", "列名固定为", "json_text",
         "solution/cli.py", "if set(fieldnames) != set(COLUMNS):",
         "if tuple(fieldnames) != COLUMNS:", "condition_negation",
         "恢复为按列顺序而不是列名集合校验"),
    case("NI-E2E-03", "test_e2e_invalid_row_preserves_output", "目标输出文件不得被创建或覆盖", "atomic_publish",
         "solution/cli.py",
         "    row = _read_record(record_path)\n    report = audit_batch(row)\n    destination = Path(output_path)",
         "    row = _read_record(record_path)\n    report = {\"batch_id\": \"partial\"}\n    destination = Path(output_path)",
         "return_value", "把校验失败路径替换为固定半成品批单"),
]


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def test_names() -> set[str]:
    tree = ast.parse(TESTS.read_text(encoding="utf-8"))
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name.startswith("test_")
    }


def run(command: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        text=True,
        capture_output=True,
    )


def copy_oracle_modules(container: str) -> None:
    for name in MODULE_NAMES:
        subprocess.run(
            ["docker", "cp", str(TASK / "solution" / name), f"{container}:/workspace/bath_audit/{name}"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    subprocess.run(
        [
            "docker",
            "cp",
            str(TASK / "environment" / "workspace" / "bath_audit" / "audit.py"),
            f"{container}:/workspace/bath_audit/audit.py",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )
    subprocess.run(
        [
            "docker",
            "cp",
            str(TASK / "environment" / "workspace" / "bath_audit" / "constants.py"),
            f"{container}:/workspace/bath_audit/constants.py",
        ],
        check=True,
        stdout=subprocess.DEVNULL,
    )


def apply_mutant(container: str, target: str, content: str) -> None:
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    os.chmod(temporary, 0o644)
    try:
        if target.startswith("solution/"):
            container_target = f"/workspace/bath_audit/{Path(target).name}"
        else:
            container_target = f"/{target.removeprefix('environment/')}"
        subprocess.run(
            ["docker", "cp", str(temporary), f"{container}:{container_target}"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
    finally:
        temporary.unlink(missing_ok=True)


def run_test_function(container: str, item: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run one test function directly from the mounted test module."""
    test_name = item["test_name"]
    case_id = item["case_id"]
    code = (
        "import importlib.util\n"
        "from pathlib import Path\n"
        "spec = importlib.util.spec_from_file_location('mutation_target', "
        "'/tests/test_outputs.py')\n"
        "module = importlib.util.module_from_spec(spec)\n"
        "spec.loader.exec_module(module)\n"
        "try:\n"
        f"    getattr(module, {test_name!r})()\n"
        "except BaseException:\n"
        f"    print({case_id!r} + ' FAILED ' + {test_name!r})\n"
        "    raise\n"
        f"print({case_id!r} + ' PASSED ' + {test_name!r})\n"
    )
    return run(["docker", "exec", "-w", "/workspace", container, "python", "-c", code])


def main() -> int:
    for cache in TASK.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    tests = test_names()
    instruction = INSTRUCTION.read_text(encoding="utf-8")
    tests_source = TESTS.read_text(encoding="utf-8")
    seen_cases: set[str] = set()
    for item in CASES:
        if item["case_id"] in seen_cases:
            raise SystemExit(f"duplicate case_id: {item['case_id']}")
        seen_cases.add(item["case_id"])
        if item["test_name"] not in tests:
            raise SystemExit(f"missing test: {item['test_name']}")
        if item["case_id"] not in tests_source:
            raise SystemExit(f"case_id missing from tests: {item['case_id']}")
        if instruction.count(item["source_text"]) != 1:
            raise SystemExit(
                f"{item['case_id']}: source_text must occur once in instruction.md"
            )
        target = TASK / item["target"]
        source = target.read_text(encoding="utf-8")
        if source.count(item["old"]) != 1:
            raise SystemExit(
                f"{item['case_id']}: mutation target text must occur once: {item['target']}"
            )
    OUT.mkdir(parents=True, exist_ok=True)
    output_dir = OUT / "mutation-outputs"
    output_dir.mkdir(parents=True, exist_ok=True)

    image = f"harbor-nickel-behavior:{__import__('os').getpid()}"
    build = run(["docker", "build", "-q", "-t", image, str(TASK / "environment")])
    if build.returncode != 0:
        print(build.stderr, file=sys.stderr)
        return 1
    started = run(
        [
            "docker",
            "run",
            "-d",
            "--rm",
            "-v",
            f"{TASK / 'tests'}:/tests:ro",
            image,
            "sleep",
            "infinity",
        ]
    )
    if started.returncode != 0:
        print(started.stderr, file=sys.stderr)
        return 1
    container = started.stdout.strip()
    nop_container = ""
    try:
        subprocess.run(
            ["docker", "exec", container, "python", "-m", "pip", "install", "--user",
             "--no-cache-dir", "--disable-pip-version-check", "--require-hashes",
             "--only-binary=:all:", "-r", "/tests/requirements.txt"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        copy_oracle_modules(container)
        oracle_lines = []
        for item in CASES:
            result = run_test_function(container, item)
            if result.returncode != 0:
                raise SystemExit(
                    f"oracle target failed: {item['case_id']}\n{result.stdout}{result.stderr}"
                )
            oracle_lines.append(result.stdout.strip())
            oracle_lines.append(f"test_outputs.py::{item['test_name']} PASSED")
            oracle_lines.append(f"{item['case_id']} PASSED")
        oracle_text = "\n".join(oracle_lines) + "\n"
        oracle_path = OUT / "oracle-stdout.txt"
        oracle_path.write_text(oracle_text, encoding="utf-8")

        nop_started = run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "-v",
                f"{TASK / 'tests'}:/tests:ro",
                image,
                "sleep",
                "infinity",
            ]
        )
        if nop_started.returncode != 0:
            raise SystemExit(nop_started.stderr)
        nop_container = nop_started.stdout.strip()
        subprocess.run(
            ["docker", "exec", nop_container, "python", "-m", "pip", "install", "--user",
             "--no-cache-dir", "--disable-pip-version-check", "--require-hashes",
             "--only-binary=:all:", "-r", "/tests/requirements.txt"],
            check=True,
            stdout=subprocess.DEVNULL,
        )
        nop_lines = []
        nop_passed: dict[str, bool] = {}
        for item in CASES:
            result = run_test_function(nop_container, item)
            passed = result.returncode == 0
            nop_passed[item["case_id"]] = passed
            status = "PASSED" if passed else "FAILED"
            nop_lines.extend(
                [
                    result.stdout.strip(),
                    f"test_outputs.py::{item['test_name']} {status}",
                    f"{item['case_id']} {status}",
                ]
            )
        nop_text = "\n".join(nop_lines) + "\n"
        (OUT / "nop-stdout.txt").write_text(nop_text, encoding="utf-8")

        evidence_lines = []
        for item in CASES:
            copy_oracle_modules(container)
            target = TASK / item["target"]
            original = target.read_text(encoding="utf-8")
            mutated = original.replace(item["old"], item["new"], 1)
            apply_mutant(container, item["target"], mutated)
            result = run_test_function(container, item)
            combined = (result.stdout or "") + (result.stderr or "")
            if result.returncode == 0:
                raise SystemExit(
                    f"mutation survived: {item['case_id']}\n{combined}"
                )
            if item["test_name"] not in combined:
                raise SystemExit(
                    f"mutation did not report target test: {item['case_id']}\n{combined}"
                )
            output_name = f"mutation-outputs/{item['case_id']}.log"
            output_path = OUT / output_name
            output_path.write_text(
                f"$ docker exec {container} python -c "
                f"'direct test function {item['test_name']}'\n"
                f"{combined}\n{item['case_id']} FAILED (direct-test exit={result.returncode})\n",
                encoding="utf-8",
            )
            old_lines = original.splitlines(keepends=True)
            new_lines = mutated.splitlines(keepends=True)
            patch = "".join(
                difflib.unified_diff(
                    old_lines,
                    new_lines,
                    fromfile=f"a/{item['target']}",
                    tofile=f"b/{item['target']}",
                )
            )
            evidence_lines.append(
                {
                    "behavior_id": item["case_id"],
                    "test_name": item["test_name"],
                    "kind": "isolated_mutation",
                    "mutation_target": item["target"],
                    "mutation_patch": patch,
                    "mutation_sha256": sha256_bytes(mutated.encode("utf-8")),
                    "mutation_description": item["description"],
                    "mutation_operator": item["operator"],
                    "exit_code": result.returncode,
                    "output_file": output_name,
                }
            )

        evidence_path = OUT / "mutation-evidence.jsonl"
        evidence_path.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in evidence_lines) + "\n",
            encoding="utf-8",
        )

        ids = [item["case_id"] for item in CASES]
        package_ids = {
            "json_text": [
                item["case_id"] for item in CASES
                if item["category"] == "json_text"
            ],
            "filesystem": [
                item["case_id"] for item in CASES
                if item["category"] == "filesystem"
            ],
            "atomic_publish": [
                item["case_id"] for item in CASES
                if item["category"] == "atomic_publish"
            ],
            "database": [],
            "time_selection": [],
            "http_network": [],
            "initial_baseline": [],
        }
        packages = {
            "json_text": {"applicable": True, "behavior_ids": package_ids["json_text"]},
            "filesystem": {"applicable": True, "behavior_ids": package_ids["filesystem"]},
            "atomic_publish": {"applicable": True, "behavior_ids": package_ids["atomic_publish"]},
            "database": {"applicable": False, "reason": "本题不访问数据库"},
            "time_selection": {"applicable": False, "reason": "本题不做时间窗口或时间选择"},
            "http_network": {"applicable": False, "reason": "本题运行时不访问网络"},
            "initial_baseline": {"applicable": False, "reason": "本题没有独立初始数据集或恢复基线"},
        }
        behaviors = []
        for item in CASES:
            line = instruction[: instruction.index(item["source_text"])].count("\n") + 1
            behaviors.append(
                {
                    "id": item["case_id"],
                    "location": f"instruction.md:{line}",
                    "source_text": item["source_text"],
                    "behavior": item["description"],
                    "category": item["category"],
                    "fixture": "tests/test_outputs.py",
                    "test_name": item["test_name"],
                    "assertion": "断言目标输出与独立复算结果一致",
                    "counterexample": "对应错误实现应使目标测试失败",
                    "mutation": item["description"],
                    "case_id": item["case_id"],
                    "kind": "pass_to_pass" if nop_passed[item["case_id"]] else "fail_to_pass",
                }
            )
        oracle_cases = "\n".join(
            sorted(
                f"test_outputs.py::{item['test_name']}\tPASSED"
                for item in CASES
            )
        )
        matrix = {
            "version": 3,
            "target_difficulty": "expert",
            "reviewed_instruction_word_by_word": True,
            "reviewed_tests_after_authoring": True,
            "reviewed_atomicity": True,
            "reviewed_category_mapping": True,
            "instruction_sha256": sha256_bytes(INSTRUCTION.read_bytes()),
            "tests_sha256": sha256_bytes(TESTS.read_bytes()),
            "oracle_stdout_sha256": sha256_bytes(oracle_text.encode("utf-8")),
            "oracle_cases_sha256": sha256_bytes(oracle_cases.encode("utf-8")),
            "coverage_packages": packages,
            "behaviors": behaviors,
            "core_challenges": [
                {
                    "id": "C1",
                    "capability": "滴定换算与铜干扰校正",
                    "initial_defect": "草稿脚本漏空白或铜校正",
                    "counterexamples": "分别破坏空白、摩尔质量和稀释",
                    "direct_tests": [
                        "test_c1_edta_blank_correction",
                        "test_c1_nickel_stoichiometry_and_molar_mass",
                        "test_c1_copper_interference_subtracted",
                    ],
                    "combination_case": "test_e2e_sample_report",
                },
                {
                    "id": "C2",
                    "capability": "硼酸一比一计量",
                    "initial_defect": "把硼酸错误按二倍计量",
                    "counterexamples": "删除空白扣除或替换化学计量倍数",
                    "direct_tests": [
                        "test_c2_boric_blank_correction",
                        "test_c2_boric_one_to_one_stoichiometry",
                    ],
                    "combination_case": "test_e2e_sample_report",
                },
                {
                    "id": "C3",
                    "capability": "镍氯双盐联立",
                    "initial_defect": "忽略氯化镍或商品有效含量",
                    "counterexamples": "将氯化镍置零或放宽不可配平边界",
                    "direct_tests": [
                        "test_c3_coupled_nickel_salts",
                        "test_c3_assay_applied_to_raw_mass",
                        "test_c3_rejects_chloride_without_enough_nickel",
                    ],
                    "combination_case": "test_e2e_sample_report",
                },
                {
                    "id": "C4",
                    "capability": "班次沉积和带出反算",
                    "initial_defect": "直接拿班末目标配料",
                    "counterexamples": "删除法拉第电子数或带出体积",
                    "direct_tests": [
                        "test_c4_faraday_deposition",
                        "test_c4_dragout_raises_start_targets",
                        "test_c4_dragout_losses_use_start_concentration",
                    ],
                    "combination_case": "test_e2e_sample_report",
                },
                {
                    "id": "C5",
                    "capability": "整袋发料与预测浓度",
                    "initial_defect": "直接使用理论质量或向下取整",
                    "counterexamples": "把整袋向上取整改成四舍五入或按1升槽容预测",
                    "direct_tests": [
                        "test_c5_rounds_each_material_up_to_whole_bags",
                        "test_c5_predicted_uses_packaged_material_mass",
                        "test_c5_no_deficit_means_no_bags",
                    ],
                    "combination_case": "test_e2e_sample_report",
                },
            ],
            "semantic_contracts": {
                "boundary_pairs": {
                    "applicable": False,
                    "reason": "本题题面没有把同一数值的接受和拒绝写成允许与拒绝的配对输出",
                },
                "output_contracts": {
                    "applicable": True,
                    "items": [
                        {
                            "id": "OUT-01",
                            "source_text": "输入校验或配方约束失败时",
                            "channels": ["stderr"],
                            "expectation": "nonempty",
                            "test_names": ["test_e2e_invalid_row_preserves_output"],
                        }
                    ],
                },
                "failure_stages": {
                    "applicable": True,
                    "items": [
                        {
                            "id": "FAIL-01",
                            "stage": "化验记录校验失败",
                            "source_text": "输入校验或配方约束失败时",
                            "test_names": ["test_e2e_invalid_row_preserves_output"],
                            "assertions": [
                                "completed.returncode != 0",
                                "completed.stderr.strip() != ''",
                                "output_path.read_text(encoding='utf-8') == 'existing result\\n'",
                            ],
                        }
                    ],
                },
                "timing_contracts": {
                    "applicable": False,
                    "reason": "本题没有对外承诺的秒级时限或调度时间契约",
                },
            },
        }
        (OUT / "coverage-matrix.json").write_text(
            json.dumps(matrix, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    finally:
        if nop_container:
            run(["docker", "rm", "-f", nop_container])
        run(["docker", "rm", "-f", container])
        run(["docker", "image", "rm", "-f", image])

    print(f"wrote {OUT / 'coverage-matrix.json'}")
    print(f"wrote {OUT / 'mutation-evidence.jsonl'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
