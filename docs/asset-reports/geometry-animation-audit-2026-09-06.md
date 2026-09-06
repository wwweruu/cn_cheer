# GLB 几何与骨骼动画质量审计报告

- 审计日期：2026-09-06
- 工具：`tools/audit_glb_assets.py`（纯 Python GLB 解析，无 Blender 依赖；环境内 `blender` 不可用）
- 范围：`public/assets/models/` 下全部 **222** 个 GLB（顶层棋子 14、motion/ 84、native-motion/ 40、production/ 84）
- 原始数据：`docs/asset-reports/glb-audit-raw.json`（每个文件的完整解析结果）

## 0. 结论摘要

| 指标 | 数值 |
|---|---|
| 解析 GLB 总数 | 222（解析失败 0） |
| 总顶点 / 总三角面 | 5,501,085 / 6,010,901 |
| 含骨骼动画的文件 | 124（motion/ 84 + native-motion/ 40，均含蒙皮网格） |
| 内嵌纹理图像总数 | 624 |
| error 级问题 | 0 |
| warn 级问题 | 112（退化三角 2 条、循环首尾不一致 110 条） |

**总体结论**：几何数据健康（无索引越界、无 NaN/Inf、法线全部单位化、蒙皮权重全部归一、关节索引无越界）；14 类棋子 idle/attack/hit/death/walk/run 六段动画覆盖齐全；纹理全部内嵌且尺寸可解析。production/ 84 个文件为**静态运行版**（单节点、无动画、无蒙皮），与交付文档 PRODUCTION_DELIVERY.md 中“保留的静态运行文件”定位一致，动画运行版实际为 motion/ 下的 84 个 GLB，非缺陷。需要关注的问题仅两类：① 顶层 elephant 红/黑各有一个小网格 16.67% 退化三角；② motion/ 与 native-motion/ 候选文件的 walk/run/idle 首尾姿态不一致（其中 walk/run 平移差需对照“运行 GLB 已去除水平根位移”的交付约定复核）。

## 1. 几何检查

### 1.1 顶层棋子（public/assets/models/*.glb）

| 棋子 | 顶点数 | 三角面 | 包围盒对角线 | 包围盒 Y 范围 | 退化三角 | 法线 |
|---|---|---|---|---|---|---|
| advisor_black.glb | 5,870 | 4,376 | 1.967 | [-0.19, 1.24] | — | 单位化 ✓ |
| advisor_red.glb | 5,255 | 4,140 | 2.179 | [-0.39, 1.32] | — | 单位化 ✓ |
| cannon_black.glb | 9,598 | 7,816 | 2.872 | [-0.65, 1.73] | — | 单位化 ✓ |
| cannon_red.glb | 10,409 | 8,302 | 2.345 | [-0.40, 1.24] | — | 单位化 ✓ |
| chariot_black.glb | 14,957 | 10,298 | 3.672 | [-0.62, 2.29] | — | 单位化 ✓ |
| chariot_red.glb | 14,755 | 10,102 | 3.671 | [-0.62, 2.29] | — | 单位化 ✓ |
| elephant_black.glb | 10,540 | 8,882 | 2.235 | [-0.28, 1.43] | Cube.009[0] 16.7% | 单位化 ✓ |
| elephant_red.glb | 10,191 | 8,302 | 2.320 | [-0.28, 1.54] | Cube.011[0] 16.7% | 单位化 ✓ |
| general_black.glb | 7,560 | 6,164 | 2.105 | [-0.38, 1.24] | — | 单位化 ✓ |
| general_red.glb | 7,296 | 5,554 | 2.156 | [-0.38, 1.31] | — | 单位化 ✓ |
| horse_black.glb | 7,962 | 6,154 | 2.214 | [-0.51, 1.27] | — | 单位化 ✓ |
| horse_red.glb | 7,901 | 6,074 | 2.214 | [-0.51, 1.27] | — | 单位化 ✓ |
| soldier_black.glb | 6,336 | 5,348 | 1.996 | [-0.19, 1.27] | — | 单位化 ✓ |
| soldier_red.glb | 6,684 | 5,228 | 1.974 | [-0.19, 1.24] | — | 单位化 ✓ |

尺度中位数对角线 **2.214**，14 枚棋子范围 1.967–3.672 （最大/中位数 = 1.66，为 chariot 车马复合体，属合理体型差异），**无尺度离群**。

### 1.2 动画运行资产（motion / native-motion / production）

| 目录 | 文件数 | 顶点数 min–max | 三角面 min–max | 对角线 min–max | 退化三角问题 | 法线问题 | 索引/NaN 问题 |
|---|---|---|---|---|---|---|---|
| motion/ | 84 | 11,057–71,561 | 11,900–59,920 | 1.342–2.071 | 0 | 0 | 0 |
| native-motion/ | 40 | 14,454–26,652 | 19,898–19,900 | 1.368–2.067 | 0 | 0 | 0 |
| production/ | 84 | 11,221–70,331 | 11,919–59,920 | 1.293–2.066 | 0 | 0 | 0 |

运行资产三角面规模按 desktop/mobile/distant 分级递减，符合 LOD 设计；三组目录均无索引越界、无 NaN/Inf、法线全部存在且单位化。

## 2. 蒙皮检查

含蒙皮网格的文件 **124** 个（motion/ 84 + native-motion/ 40）。顶层 14 枚与 production/ 84 个为纯静态网格，无蒙皮，与静态运行版定位一致，属预期。全部蒙皮文件具备 JOINTS_0/WEIGHTS_0，权重和偏离 1 超过 0.01 的顶点比例为 **0**，关节索引越界 **0**。

| 目录 | 蒙皮文件 | 骨骼数 min–max | 权重未归一顶点 | 关节越界 |
|---|---|---|---|---|
| motion/ | 84 | 4–38 | 0 个文件 | 0 |
| native-motion/ | 40 | 25–47 | 0 个文件 | 0 |
| production/ | 0（静态版，无蒙皮） | — | — | — |

## 3. 动画检查

### 3.1 六段动作覆盖矩阵

| 棋子类别 | idle | attack | hit | death | walk | run |
|---|---|---|---|---|---|---|
| advisor_black | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| advisor_red | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| cannon_black | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| cannon_red | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| chariot_black | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| chariot_red | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| elephant_black | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| elephant_red | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| general_black | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| general_red | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| horse_black | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| horse_red | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| soldier_black | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| soldier_red | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

14 类棋子六段动作 **全部覆盖，无缺失**。每个含动画文件均含恰好 6 个 clip（idle/attack/hit/death/walk/run）。

### 3.2 clip 时长统计（124 个含动画文件 × 6 clip）

| clip | 时长 min | 中位 | 时长 max | 时长为 0 | 关键帧 <2 | NaN 输出 |
|---|---|---|---|---|---|---|
| idle | 3.97s | 4.00s | 5.97s | 0 | 0 | 0 |
| attack | 1.33s | 1.50s | 3.47s | 0 | 0 | 0 |
| hit | 0.70s | 0.70s | 1.63s | 0 | 0 | 0 |
| death | 1.60s | 1.60s | 2.23s | 0 | 0 | 0 |
| walk | 1.00s | 1.20s | 2.80s | 0 | 0 | 0 |
| run | 0.62s | 0.80s | 1.80s | 0 | 0 | 0 |

### 3.3 循环（loop）首尾姿态一致性

对 idle/walk/run 三类循环 clip 检查首末帧姿态差（旋转 > 5° 或平移 > 0.02 记为不一致）：共 **110** 条，全部位于 motion/ 与 native-motion/（production/ 与顶层文件为静态版，无 clip）。

| 目录 | idle | walk | run | 小计 |
|---|---|---|---|---|
| motion/ | 12 | 36 | 36 | 84 |
| native-motion/ | 7 | 13 | 6 | 26 |

旋转差最大的 8 条：

| 文件 | clip | 首末旋转差 | 首末平移差 |
|---|---|---|---|
| public/assets/models/native-motion/general_black/v8.webp.glb | walk | 23.1° | 4.996 |
| public/assets/models/native-motion/general_black/v9.webp.glb | walk | 23.1° | 4.996 |
| public/assets/models/native-motion/horse_black/v5.webp.glb | idle | 20.4° | 0.000 |
| public/assets/models/native-motion/horse_black/v5.webp.glb | walk | 20.4° | 0.000 |
| public/assets/models/native-motion/horse_black/v5.webp.glb | run | 20.4° | 0.000 |
| public/assets/models/native-motion/horse_red/v9.webp.glb | idle | 20.4° | 0.000 |
| public/assets/models/native-motion/horse_red/v9.webp.glb | walk | 20.4° | 0.000 |
| public/assets/models/native-motion/horse_red/v9.webp.glb | run | 20.4° | 0.000 |

平移差最大的 8 条：

| 文件 | clip | 首末旋转差 | 首末平移差 |
|---|---|---|---|
| public/assets/models/native-motion/general_black/v8.webp.glb | walk | 23.1° | 4.996 |
| public/assets/models/native-motion/general_black/v9.webp.glb | walk | 23.1° | 4.996 |
| public/assets/models/motion/general_black/desktop.glb | walk | 8.3° | 1.300 |
| public/assets/models/motion/general_black/desktop.webp.glb | walk | 8.3° | 1.300 |
| public/assets/models/motion/general_black/distant.glb | walk | 8.3° | 1.300 |
| public/assets/models/motion/general_black/distant.webp.glb | walk | 8.3° | 1.300 |
| public/assets/models/motion/general_black/mobile.glb | walk | 8.3° | 1.300 |
| public/assets/models/motion/general_black/mobile.webp.glb | walk | 8.3° | 1.300 |

> 说明：交付文档约定“运行 GLB 去除水平位移，游戏负责落点移动”，但 motion/ 正式动画资产中仍有 36 条 walk + 36 条 run 存在首末平移差（最大 general_black 1.300，约为其包围盒对角线的 75%），若属残留根位移会与代码驱动的位移叠加，建议逐条复核是根骨骼水平位移还是躯干起伏。native-motion/ 为候选版本库：general_black v8/v9 的 walk 平移差达 4.996（相对其包围盒对角线 ≈1.65 的 3 倍），horse_red v9 / horse_black v5 的 idle 首末旋转差 20.4°，循环播放会明显跳帧，建议弃用或修复这些候选版本。

## 4. 纹理检查

内嵌图像共 **624** 张，全部走 bufferView 内嵌（外部 uri 0 张），尺寸全部解析成功，无缺失 internal buffer。

| 格式 | 尺寸 | 张数 |
|---|---|---|
| image/ktx2 | 1024×1024 | 84 |
| image/ktx2 | 2048×2048 | 84 |
| image/ktx2 | 4096×4096 | 84 |
| image/webp | 1024×1024 | 84 |
| image/webp | 2048×2048 | 204 |
| image/webp | 4096×4096 | 84 |

纹理分 4096/2048/1024 三档，与 desktop/mobile/distant 分级对应；KTX2（GPU 压缩）与 WebP 双格式并存，符合 `.webp.glb` 变体命名约定。

## 5. 问题清单（按严重度）

### 5.1 error 级

无。

### 5.2 warn 级 — 退化三角形（2 条）

- `public/assets/models/elephant_black.glb` — Cube.009[0] degenerate tris 16.67% (18/108)
- `public/assets/models/elephant_red.glb` — Cube.011[0] degenerate tris 16.67% (18/108)

### 5.3 warn 级 — 循环 clip 首尾姿态不一致（110 条，全量列表）

| 文件 | clip | 首末旋转差(°) | 首末平移差 |
|---|---|---|---|
| public/assets/models/motion/advisor_black/desktop.glb | run | 5.8 | 0.024 |
| public/assets/models/motion/advisor_black/desktop.glb | walk | 9.0 | 1.001 |
| public/assets/models/motion/advisor_black/desktop.webp.glb | run | 5.8 | 0.024 |
| public/assets/models/motion/advisor_black/desktop.webp.glb | walk | 9.0 | 1.001 |
| public/assets/models/motion/advisor_black/distant.glb | run | 5.8 | 0.024 |
| public/assets/models/motion/advisor_black/distant.glb | walk | 9.0 | 1.001 |
| public/assets/models/motion/advisor_black/distant.webp.glb | run | 5.8 | 0.024 |
| public/assets/models/motion/advisor_black/distant.webp.glb | walk | 9.0 | 1.001 |
| public/assets/models/motion/advisor_black/mobile.glb | run | 5.8 | 0.024 |
| public/assets/models/motion/advisor_black/mobile.glb | walk | 9.0 | 1.001 |
| public/assets/models/motion/advisor_black/mobile.webp.glb | run | 5.8 | 0.024 |
| public/assets/models/motion/advisor_black/mobile.webp.glb | walk | 9.0 | 1.001 |
| public/assets/models/motion/advisor_red/desktop.glb | run | 2.5 | 0.065 |
| public/assets/models/motion/advisor_red/desktop.glb | walk | 0.9 | 0.073 |
| public/assets/models/motion/advisor_red/desktop.webp.glb | run | 2.5 | 0.065 |
| public/assets/models/motion/advisor_red/desktop.webp.glb | walk | 0.9 | 0.073 |
| public/assets/models/motion/advisor_red/distant.glb | run | 2.5 | 0.065 |
| public/assets/models/motion/advisor_red/distant.glb | walk | 0.9 | 0.073 |
| public/assets/models/motion/advisor_red/distant.webp.glb | run | 2.5 | 0.065 |
| public/assets/models/motion/advisor_red/distant.webp.glb | walk | 0.9 | 0.073 |
| public/assets/models/motion/advisor_red/mobile.glb | run | 2.5 | 0.065 |
| public/assets/models/motion/advisor_red/mobile.glb | walk | 0.9 | 0.073 |
| public/assets/models/motion/advisor_red/mobile.webp.glb | run | 2.5 | 0.065 |
| public/assets/models/motion/advisor_red/mobile.webp.glb | walk | 0.9 | 0.073 |
| public/assets/models/motion/general_black/desktop.glb | run | 5.8 | 0.027 |
| public/assets/models/motion/general_black/desktop.glb | walk | 8.3 | 1.300 |
| public/assets/models/motion/general_black/desktop.webp.glb | run | 5.8 | 0.027 |
| public/assets/models/motion/general_black/desktop.webp.glb | walk | 8.3 | 1.300 |
| public/assets/models/motion/general_black/distant.glb | run | 5.8 | 0.027 |
| public/assets/models/motion/general_black/distant.glb | walk | 8.3 | 1.300 |
| public/assets/models/motion/general_black/distant.webp.glb | run | 5.8 | 0.027 |
| public/assets/models/motion/general_black/distant.webp.glb | walk | 8.3 | 1.300 |
| public/assets/models/motion/general_black/mobile.glb | run | 5.8 | 0.027 |
| public/assets/models/motion/general_black/mobile.glb | walk | 8.3 | 1.300 |
| public/assets/models/motion/general_black/mobile.webp.glb | run | 5.8 | 0.027 |
| public/assets/models/motion/general_black/mobile.webp.glb | walk | 8.3 | 1.300 |
| public/assets/models/motion/general_red/desktop.glb | run | 6.2 | 0.082 |
| public/assets/models/motion/general_red/desktop.glb | walk | 7.5 | 1.013 |
| public/assets/models/motion/general_red/desktop.webp.glb | run | 6.2 | 0.082 |
| public/assets/models/motion/general_red/desktop.webp.glb | walk | 7.5 | 1.013 |
| public/assets/models/motion/general_red/distant.glb | run | 6.2 | 0.082 |
| public/assets/models/motion/general_red/distant.glb | walk | 7.5 | 1.013 |
| public/assets/models/motion/general_red/distant.webp.glb | run | 6.2 | 0.082 |
| public/assets/models/motion/general_red/distant.webp.glb | walk | 7.5 | 1.013 |
| public/assets/models/motion/general_red/mobile.glb | run | 6.2 | 0.082 |
| public/assets/models/motion/general_red/mobile.glb | walk | 7.5 | 1.013 |
| public/assets/models/motion/general_red/mobile.webp.glb | run | 6.2 | 0.082 |
| public/assets/models/motion/general_red/mobile.webp.glb | walk | 7.5 | 1.013 |
| public/assets/models/motion/soldier_black/desktop.glb | idle | 3.2 | 0.062 |
| public/assets/models/motion/soldier_black/desktop.glb | run | 4.5 | 0.135 |
| public/assets/models/motion/soldier_black/desktop.glb | walk | 2.2 | 0.020 |
| public/assets/models/motion/soldier_black/desktop.webp.glb | idle | 3.2 | 0.062 |
| public/assets/models/motion/soldier_black/desktop.webp.glb | run | 4.5 | 0.135 |
| public/assets/models/motion/soldier_black/desktop.webp.glb | walk | 2.2 | 0.020 |
| public/assets/models/motion/soldier_black/distant.glb | idle | 3.2 | 0.062 |
| public/assets/models/motion/soldier_black/distant.glb | run | 4.5 | 0.135 |
| public/assets/models/motion/soldier_black/distant.glb | walk | 2.2 | 0.020 |
| public/assets/models/motion/soldier_black/distant.webp.glb | idle | 3.2 | 0.062 |
| public/assets/models/motion/soldier_black/distant.webp.glb | run | 4.5 | 0.135 |
| public/assets/models/motion/soldier_black/distant.webp.glb | walk | 2.2 | 0.020 |
| public/assets/models/motion/soldier_black/mobile.glb | idle | 3.2 | 0.062 |
| public/assets/models/motion/soldier_black/mobile.glb | run | 4.5 | 0.135 |
| public/assets/models/motion/soldier_black/mobile.glb | walk | 2.2 | 0.020 |
| public/assets/models/motion/soldier_black/mobile.webp.glb | idle | 3.2 | 0.062 |
| public/assets/models/motion/soldier_black/mobile.webp.glb | run | 4.5 | 0.135 |
| public/assets/models/motion/soldier_black/mobile.webp.glb | walk | 2.2 | 0.020 |
| public/assets/models/motion/soldier_red/desktop.glb | idle | 8.7 | 0.259 |
| public/assets/models/motion/soldier_red/desktop.glb | run | 5.6 | 0.104 |
| public/assets/models/motion/soldier_red/desktop.glb | walk | 9.6 | 0.597 |
| public/assets/models/motion/soldier_red/desktop.webp.glb | idle | 8.7 | 0.259 |
| public/assets/models/motion/soldier_red/desktop.webp.glb | run | 5.6 | 0.104 |
| public/assets/models/motion/soldier_red/desktop.webp.glb | walk | 9.6 | 0.597 |
| public/assets/models/motion/soldier_red/distant.glb | idle | 8.7 | 0.259 |
| public/assets/models/motion/soldier_red/distant.glb | run | 5.6 | 0.104 |
| public/assets/models/motion/soldier_red/distant.glb | walk | 9.6 | 0.597 |
| public/assets/models/motion/soldier_red/distant.webp.glb | idle | 8.7 | 0.259 |
| public/assets/models/motion/soldier_red/distant.webp.glb | run | 5.6 | 0.104 |
| public/assets/models/motion/soldier_red/distant.webp.glb | walk | 9.6 | 0.597 |
| public/assets/models/motion/soldier_red/mobile.glb | idle | 8.7 | 0.259 |
| public/assets/models/motion/soldier_red/mobile.glb | run | 5.6 | 0.104 |
| public/assets/models/motion/soldier_red/mobile.glb | walk | 9.6 | 0.597 |
| public/assets/models/motion/soldier_red/mobile.webp.glb | idle | 8.7 | 0.259 |
| public/assets/models/motion/soldier_red/mobile.webp.glb | run | 5.6 | 0.104 |
| public/assets/models/motion/soldier_red/mobile.webp.glb | walk | 9.6 | 0.597 |
| public/assets/models/native-motion/advisor_red/v7.webp.glb | idle | 12.4 | 0.000 |
| public/assets/models/native-motion/cannon_black/v8.webp.glb | idle | 14.7 | 0.000 |
| public/assets/models/native-motion/cannon_black/v8.webp.glb | run | 14.7 | 0.000 |
| public/assets/models/native-motion/cannon_black/v8.webp.glb | walk | 14.7 | 0.000 |
| public/assets/models/native-motion/cannon_red/v10.webp.glb | idle | 14.7 | 0.000 |
| public/assets/models/native-motion/cannon_red/v10.webp.glb | run | 14.7 | 0.000 |
| public/assets/models/native-motion/cannon_red/v10.webp.glb | walk | 14.7 | 0.000 |
| public/assets/models/native-motion/elephant_black/v2.webp.glb | idle | 7.7 | 0.000 |
| public/assets/models/native-motion/elephant_black/v2.webp.glb | run | 7.7 | 0.000 |
| public/assets/models/native-motion/elephant_black/v2.webp.glb | walk | 7.7 | 0.000 |
| public/assets/models/native-motion/elephant_red/v2.webp.glb | idle | 7.7 | 0.000 |
| public/assets/models/native-motion/elephant_red/v2.webp.glb | run | 7.7 | 0.000 |
| public/assets/models/native-motion/elephant_red/v2.webp.glb | walk | 7.7 | 0.000 |
| public/assets/models/native-motion/general_black/v8.webp.glb | walk | 23.1 | 4.996 |
| public/assets/models/native-motion/general_black/v9.webp.glb | walk | 23.1 | 4.996 |
| public/assets/models/native-motion/horse_black/v5.webp.glb | idle | 20.4 | 0.000 |
| public/assets/models/native-motion/horse_black/v5.webp.glb | run | 20.4 | 0.000 |
| public/assets/models/native-motion/horse_black/v5.webp.glb | walk | 20.4 | 0.000 |
| public/assets/models/native-motion/horse_red/v9.webp.glb | idle | 20.4 | 0.000 |
| public/assets/models/native-motion/horse_red/v9.webp.glb | run | 20.4 | 0.000 |
| public/assets/models/native-motion/horse_red/v9.webp.glb | walk | 20.4 | 0.000 |
| public/assets/models/native-motion/soldier_black/v15.webp.glb | walk | 15.6 | 0.342 |
| public/assets/models/native-motion/soldier_black/v16.webp.glb | walk | 15.6 | 1.140 |
| public/assets/models/native-motion/soldier_black/v17.webp.glb | walk | 15.6 | 1.140 |
| public/assets/models/native-motion/soldier_black/v18.webp.glb | walk | 15.6 | 1.140 |
| public/assets/models/native-motion/soldier_red/v13.webp.glb | walk | 15.3 | 0.471 |

### 5.4 其他检查项结果

- 索引越界：0（222 个文件全部通过）
- NaN/Inf 顶点：0
- 法线缺失 / 非单位化：0
- 包围盒尺度离群：0（14 枚顶层棋子对角线 1.97–3.67，同数量级）
- 蒙皮权重未归一：0；关节索引越界：0；全零权重顶点：0
- 时长为 0 的 clip：0；关键帧 <2 的 clip：0；sampler 输出 NaN：0
- 动画覆盖缺失的棋子类别：0
- 纹理缺失 internal buffer / 无法解析尺寸：0

