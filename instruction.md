# 镀镍槽液补加批单

装饰镍电镀线停了四天，昨天重新循环过滤后，化验室对同一个槽子做了镍、硼酸和氯离子三组滴定，并另外用原子吸收测了铜污染。下一班已经排了生产计划，槽子还会因为工件带出损失一部分槽液。槽容、班末目标浓度和当天到货的两批镍盐有效含量已经录在交接CSV里。现在需要把化验读数换成槽液浓度，再给配制班一张能撑过下一班的补加批单。

`/workspace` 里现有的脚本能把演示记录跑成一份草稿，但其中的换算口径和配方拆分还不适合这次检修后的补加。请保留现有包名、命令行入口和下面列出的四个计算入口，把它们补成可用于实际批单的版本。

命令行格式：

```bash
python -m bath_audit.cli RECORD.csv BATCH.json
```

输入文件只有一行数据，列名固定为：

```text
batch_id,tank_volume_l,
edta_sample_ml,edta_titrant_ml,edta_blank_ml,edta_molarity,
boric_sample_ml,naoh_titrant_ml,naoh_blank_ml,naoh_molarity,
chloride_sample_ml,agno3_titrant_ml,agno3_blank_ml,agno3_molarity,
target_nickel_g_l,target_boric_acid_g_l,target_chloride_g_l,
nickel_sulfate_assay,nickel_chloride_assay,boric_acid_assay,
dilution_factor,copper_g_l,planned_charge_ah,cathode_efficiency,dragout_l,
nickel_sulfate_bag_kg,nickel_chloride_bag_kg,boric_acid_bag_kg
```

列顺序可以调整，但缺列、多列或数据行数不是一行都应拒绝。`batch_id`不能为空；所有数值必须是有限数。槽容、取样体积、稀释倍数、滴定剂摩尔浓度、目标浓度、三种原料有效含量和三种包装规格都必须大于零，有效含量、阴极电流效率都不得超过1；计划安时数、空白滴定体积、铜含量和带出液量不得为负，空白不得大于对应滴定体积，带出液量必须小于槽容。

三种滴定的净体积都是 `V_net = V_titrant - V_blank`，单位为mL。镍与EDTA按摩尔比1:1反应，氯离子与硝酸银按摩尔比1:1反应；硼酸加入甘露醇后与NaOH按摩尔比1:1反应。浓度按 `V_net / 1000 * M * 摩尔质量 / (V_sample / 1000) * dilution_factor` 计算，结果为槽液g/L。采用以下摩尔质量：

```text
Ni                 58.6934 g/mol
H3BO3              61.832  g/mol
Cl                 35.453  g/mol
Cu                 63.546  g/mol
NiSO4·6H2O        262.84608 g/mol
NiCl2·6H2O        237.69108 g/mol
```

EDTA也会与铜离子按1:1络合，所以上面的镍结果是镍和铜折算成的表观镍。真正的镍浓度要从表观镍中减去 `copper_g_l * 58.6934 / 63.546`；结果为负时说明铜校正量超过了滴定结果，应拒绝该记录。报告里的 `analysis_g_l.nickel` 写校正后的镍浓度。

班末目标浓度不能直接拿去配料。先按下一班计划计算镍沉积量 `planned_charge_ah * 3600 * cathode_efficiency / (2 * 96485.33212) * 58.6934`，单位为g。设班前槽液浓度为 `C_start`、班末目标为 `C_end`、带出液量为 `dragout_l`，补水恢复槽容后三种组分都满足：

```text
C_start * (tank_volume_l - dragout_l) = C_end * tank_volume_l
```

镍还要在右侧加上沉积量。由此反算班前镍、硼酸和氯离子目标。镍的带出损失为 `C_start_nickel * dragout_l`；硼酸和氯离子同理。

补加单只能用六水硫酸镍、六水氯化镍和硼酸三种商品原料。先分别计算镍、硼酸和氯离子相对目标的缺口质量 `max(0, target-current)*tank_volume_l`，单位为g。商品有效含量表示每千克商品中该纯品的质量分数。

这里公式中的 `target` 指刚反算出的班前目标，`current` 指铜校正后的当前浓度；后面的双盐联立和补加质量都按班前目标计算。

镍和氯必须同时配平。设需要补入的纯六水氯化镍为 `b` mol、纯六水硫酸镍为 `a` mol，则 `a+b` 等于镍缺口摩尔数，`2b` 等于氯缺口摩尔数；据此求出两种纯盐质量，再分别除以 `nickel_sulfate_assay` 和 `nickel_chloride_assay`。硼酸纯品质量除以 `boric_acid_assay`。先得到精确的理论补加质量，单位kg。若氯缺口所需的氯化镍摩尔数超过镍缺口摩尔数，现有两种镍盐无法完成配方，程序必须拒绝计算，不能悄悄改用其他原料。

仓库不做拆袋，三种原料只能按各自包装规格整袋发料。理论质量必须**向上取整**到对应包装规格的整数倍，不能四舍五入，也不能向零取整；缺口为零时袋数和补加质量都为零。输出里的 `addition_kg` 是整袋发料后的实际商品质量，`bags` 是整数袋数，`total_addition_kg` 是三项整袋质量之和。

输出JSON的根对象固定包含：

```text
batch_id
tank_volume_l
analysis_g_l
deficit_g
addition_kg
bags
total_addition_kg
predicted_g_l
forecast
```

`analysis_g_l`、`predicted_g_l` 的键均为 `nickel`、`boric_acid`、`chloride`。`deficit_g` 使用同样的三个键。`addition_kg` 和 `bags` 的键为 `nickel_sulfate_hexahydrate`、`nickel_chloride_hexahydrate`、`boric_acid`，没有补加的原料写0。`total_addition_kg` 为三项整袋商品补加质量之和。`predicted_g_l` 表示整袋补加后、下一班开始前的浓度，必须用整袋商品质量乘有效含量得到的实际纯品摩尔数反算，不能用理论质量、目标值或仅按理论质量计算的浓度直接填回。

`forecast` 包含 `nickel_deposited_g`、`dragout_loss_g`、`shift_start_target_g_l`。后两个都是对象，键为 `nickel`、`boric_acid`、`chloride`。`nickel_deposited_g` 只计电解沉积，不带出；带出损失按上述班前浓度和带出液量计算。

下游会直接调用下面四个入口，请保持参数次序和返回结构：

```text
bath_audit.nickel.nickel_concentration_g_l(
    sample_ml, titrant_ml, blank_ml, molarity, dilution_factor, copper_g_l
)
bath_audit.boric_acid.boric_acid_concentration_g_l(
    sample_ml, titrant_ml, blank_ml, molarity, dilution_factor
)
bath_audit.chloride.chloride_concentration_g_l(
    sample_ml, titrant_ml, blank_ml, molarity, dilution_factor
)
bath_audit.forecast.shift_start_targets_g_l(
    tank_volume_l,
    planned_charge_ah,
    cathode_efficiency,
    dragout_l,
    target_nickel_g_l,
    target_boric_acid_g_l,
    target_chloride_g_l,
)
bath_audit.makeup.makeup_plan(
    tank_volume_l,
    nickel_g_l,
    boric_acid_g_l,
    chloride_g_l,
    target_nickel_g_l,
    target_boric_acid_g_l,
    target_chloride_g_l,
    nickel_sulfate_assay,
    nickel_chloride_assay,
    boric_acid_assay,
)
bath_audit.packaging.package_plan(
    tank_volume_l,
    nickel_g_l,
    boric_acid_g_l,
    chloride_g_l,
    exact_plan,
    nickel_sulfate_assay,
    nickel_chloride_assay,
    boric_acid_assay,
    nickel_sulfate_bag_kg,
    nickel_chloride_bag_kg,
    boric_acid_bag_kg,
)
```

三个浓度函数返回槽液g/L；`shift_start_targets_g_l` 返回与 `forecast` 相同结构的对象；`makeup_plan` 返回理论精确配方，包含 `addition_kg`、`total_addition_kg` 和 `predicted_g_l`；`package_plan` 接收该配方并返回包含 `addition_kg`、`bags`、`total_addition_kg` 和 `predicted_g_l` 的整袋方案。浓度函数遇到非正样品体积、非正稀释倍数、负铜含量、负空白、空白大于滴定体积或非正摩尔浓度时应抛出 `ValueError`。带出液量不小于槽容、计划安时数为负或电流效率不在0到1之间时，也应抛出 `ValueError`。包装规格非正时，`package_plan` 应抛出 `ValueError`。

输入校验或配方约束失败时，命令以非零状态退出，并把原因写到标准错误；目标输出文件不得被创建或覆盖。成功时生成JSON后以0退出。`/workspace/data/lab_record.csv` 是一份按固定规则生成的模拟记录，用于核对接口和输出结构，不是原始化验台账。
