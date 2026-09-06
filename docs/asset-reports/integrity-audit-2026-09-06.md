# 资产完整性校验报告 — 2026-09-06

## 清单结构说明

两份清单均为 JSON，顶层结构：

- `production-manifest.json`：`files`（128 条）+ `missing`（数组，当前为空）。每条 `files` 记录含 `source`（生成来源，本地反斜杠路径）、`path`（运行时 URL 路径，形如 `/assets/models/...`，对应磁盘 `public/assets/...`）、`bytes`（体积）、`sha256`（小写十六进制）。
- `motion-manifest.json`：`files`（84 条，字段同前）+ `versions`（按棋子名记录版本信息）。无 `missing` 字段。

## 校验方法

对每条清单记录依次检查：文件存在性 → 实际字节数 vs `bytes` → 重新计算 SHA-256 vs `sha256`；所有 `.glb` 再校验二进制头（magic 应为 `glTF`、version 应为 2、header 中的 length 应等于文件实际大小）。反向扫描 `public/assets/` 下的 `.glb` 与纹理文件（webp/png/jpg/jpeg/ktx/ktx2/hdr/exr），找出未列入任何清单的孤立文件。

## 结果统计

| 指标 | 数量 |
|---|---|
| 清单条目总数 | 212 |
| 全部通过（存在+大小+哈希+GLB头） | 212 |
| 缺失文件 | 0 |
| 大小不一致 | 0 |
| SHA-256 不一致 | 0 |
| GLB 头异常（清单内） | 0 |
| GLB 头检查总数（含孤立 GLB） | 280 |
| 孤立文件（在盘上、不在清单） | 94 |

## 缺失文件（0 项）

无。

## 大小不一致（0 项）

无。

## SHA-256 不一致（0 项）

无。

## GLB 头异常（0 项）

无。

## 孤立文件（在盘上但不在任何清单，共 94 个）

- `public\assets\environment\atmosphere\distant_camp.webp`（49582 字节）
- `public\assets\environment\atmosphere\distant_mountains.webp`（41476 字节）
- `public\assets\environment\atmosphere\fx_embers.webp`（70740 字节）
- `public\assets\environment\atmosphere\fx_smoke.webp`（393450 字节）
- `public\assets\environment\atmosphere\sky_nx.webp`（33126 字节）
- `public\assets\environment\atmosphere\sky_ny.webp`（15202 字节）
- `public\assets\environment\atmosphere\sky_nz.webp`（34384 字节）
- `public\assets\environment\atmosphere\sky_px.webp`（37038 字节）
- `public\assets\environment\atmosphere\sky_py.webp`（19382 字节）
- `public\assets\environment\atmosphere\sky_pz.webp`（33670 字节）
- `public\assets\models\advisor_black.glb`（227360 字节）
- `public\assets\models\advisor_red.glb`（207972 字节）
- `public\assets\models\cannon_black.glb`（377956 字节）
- `public\assets\models\cannon_red.glb`（404120 字节）
- `public\assets\models\chariot_black.glb`（606196 字节）
- `public\assets\models\chariot_red.glb`（593512 字节）
- `public\assets\models\elephant_black.glb`（427312 字节）
- `public\assets\models\elephant_red.glb`（411624 字节）
- `public\assets\models\general_black.glb`（297812 字节）
- `public\assets\models\general_red.glb`（292840 字节）
- `public\assets\models\horse_black.glb`（320844 字节）
- `public\assets\models\horse_red.glb`（317448 字节）
- `public\assets\models\native-motion\advisor_red\v7.webp.glb`（3143076 字节）
- `public\assets\models\native-motion\advisor_red\v8.webp.glb`（3142020 字节）
- `public\assets\models\native-motion\cannon_black\v10.webp.glb`（3698896 字节）
- `public\assets\models\native-motion\cannon_black\v11.webp.glb`（3688540 字节）
- `public\assets\models\native-motion\cannon_black\v8.webp.glb`（3683096 字节）
- `public\assets\models\native-motion\cannon_black\v9.webp.glb`（3696552 字节）
- `public\assets\models\native-motion\cannon_red\v10.webp.glb`（4045564 字节）
- `public\assets\models\native-motion\cannon_red\v11.webp.glb`（4057520 字节）
- `public\assets\models\native-motion\cannon_red\v12.webp.glb`（4060740 字节）
- `public\assets\models\native-motion\cannon_red\v13.webp.glb`（4060740 字节）
- `public\assets\models\native-motion\elephant_black\v2.webp.glb`（4886376 字节）
- `public\assets\models\native-motion\elephant_black\v3.webp.glb`（4897360 字节）
- `public\assets\models\native-motion\elephant_black\v5.webp.glb`（4913144 字节）
- `public\assets\models\native-motion\elephant_black\v6.webp.glb`（4913444 字节）
- `public\assets\models\native-motion\elephant_black\v8.webp.glb`（4923372 字节）
- `public\assets\models\native-motion\elephant_red\v2.webp.glb`（4170264 字节）
- `public\assets\models\native-motion\elephant_red\v3.webp.glb`（4180896 字节）
- `public\assets\models\native-motion\elephant_red\v5.webp.glb`（4167844 字节）
- `public\assets\models\native-motion\elephant_red\v6.webp.glb`（4167844 字节）
- `public\assets\models\native-motion\elephant_red\v8.webp.glb`（4177768 字节）
- `public\assets\models\native-motion\general_black\v10.webp.glb`（3720632 字节）
- `public\assets\models\native-motion\general_black\v12.webp.glb`（3720196 字节）
- `public\assets\models\native-motion\general_black\v20.webp.glb`（3720340 字节）
- `public\assets\models\native-motion\general_black\v6.webp.glb`（3745132 字节）
- `public\assets\models\native-motion\general_black\v8.webp.glb`（3708928 字节）
- `public\assets\models\native-motion\general_black\v9.webp.glb`（3708928 字节）
- `public\assets\models\native-motion\horse_black\v5.webp.glb`（4120424 字节）
- `public\assets\models\native-motion\horse_black\v6.webp.glb`（4135620 字节）
- `public\assets\models\native-motion\horse_black\v8.webp.glb`（4009916 字节）
- `public\assets\models\native-motion\horse_red\v10.webp.glb`（3970808 字节）
- `public\assets\models\native-motion\horse_red\v11.webp.glb`（3974208 字节）
- `public\assets\models\native-motion\horse_red\v12.webp.glb`（3816068 字节）
- `public\assets\models\native-motion\horse_red\v9.webp.glb`（3956324 字节）
- `public\assets\models\native-motion\soldier_black\v15.webp.glb`（4692632 字节）
- `public\assets\models\native-motion\soldier_black\v16.webp.glb`（4655592 字节）
- `public\assets\models\native-motion\soldier_black\v17.webp.glb`（4655592 字节）
- `public\assets\models\native-motion\soldier_black\v18.webp.glb`（4656684 字节）
- `public\assets\models\native-motion\soldier_black\v19.webp.glb`（4655740 字节）
- `public\assets\models\native-motion\soldier_red\v13.webp.glb`（4114384 字节）
- `public\assets\models\native-motion\soldier_red\v14.webp.glb`（4114956 字节）
- `public\assets\models\soldier_black.glb`（250436 字节）
- `public\assets\models\soldier_red.glb`（258804 字节）
- `public\assets\review\general_red\agent-master\model.glb`（140612912 字节）
- `public\assets\review\general_red\compression\desktop.glb`（3155696 字节）
- `public\assets\review\general_red\compression\mobile.glb`（8476392 字节）
- `public\assets\review\general_red\general_red_desktop.glb`（11038760 字节）
- `public\assets\review\general_red\general_red_lod1.glb`（3710056 字节）
- `public\assets\review\general_red\general_red_lod2.glb`（3093420 字节）
- `public\assets\review\general_red\general_red_mobile.glb`（4295784 字节）
- `public\assets\review\general_red\geometry-comparison\agent-benchmark\back.png`（1030300 字节）
- `public\assets\review\general_red\geometry-comparison\agent-benchmark\detail.png`（1166001 字节）
- `public\assets\review\general_red\geometry-comparison\agent-benchmark\front.png`（1099518 字节）
- `public\assets\review\general_red\geometry-comparison\agent-benchmark\model.glb`（54183084 字节）
- `public\assets\review\general_red\geometry-comparison\agent-benchmark\three_quarter.png`（1094438 字节）
- `public\assets\review\general_red\geometry-comparison\api-v1-high\back.png`（1076703 字节）
- `public\assets\review\general_red\geometry-comparison\api-v1-high\detail.png`（1145744 字节）
- `public\assets\review\general_red\geometry-comparison\api-v1-high\front.png`（1066398 字节）
- `public\assets\review\general_red\geometry-comparison\api-v1-high\model.glb`（34310832 字节）
- `public\assets\review\general_red\geometry-comparison\api-v1-high\three_quarter.png`（1053157 字节）
- `public\assets\review\general_red\geometry-comparison\api-v2-ultra\back.png`（1092723 字节）
- `public\assets\review\general_red\geometry-comparison\api-v2-ultra\detail.png`（1157077 字节）
- `public\assets\review\general_red\geometry-comparison\api-v2-ultra\front.png`（1101318 字节）
- `public\assets\review\general_red\geometry-comparison\api-v2-ultra\model.glb`（52477248 字节）
- `public\assets\review\general_red\geometry-comparison\api-v2-ultra\three_quarter.png`（1085117 字节）
- `public\assets\review\general_red\review_back.png`（2123544 字节）
- `public\assets\review\general_red\review_detail.png`（2685414 字节）
- `public\assets\review\general_red\review_front.png`（2095550 字节）
- `public\assets\review\general_red\review_three_quarter.png`（2132012 字节）
- `public\assets\review\general_red\runtime\general_red_desktop.glb`（10453516 字节）
- `public\assets\review\general_red\runtime\general_red_distant.glb`（935584 字节）
- `public\assets\review\general_red\runtime\general_red_mobile.glb`（3155696 字节）
- `public\assets\review\general_red\runtime\general_red_rebaked_distant.glb`（3463076 字节）

## 孤立 GLB 头异常（0 项）

无。

## 与历史 validation.json 的对照

`docs/asset-reports/validation.json` 是 2026 年早些时候的构建/测试证据，并非资产哈希清单，记录的是：前端单测 23、API 离线测试 59、lint passed、生产构建 passed、E2E 通过 5 / 跳过 1、motion 变体 42、clip×tier 组合 252、每组合采样 5、动画最大固定位移误差 1.884e-08、物理机移动端测试 False、native 2k 天空盒 False。它与本次校验没有可直接比对的哈希/体积字段；本次完整性校验是该记录的补充（其只证明当时构建与测试通过，不证明盘上资产与清单逐字节一致）。
