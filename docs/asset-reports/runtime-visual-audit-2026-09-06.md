# 运行时视觉审计报告 — 2026-09-06

## 环境与方法

- 平台：Windows，Git Bash，Node v24.15.0
- 浏览器：系统 Chrome（Playwright `channel: 'chrome'`，headless）
- Dev server：`vite --host 127.0.0.1 --port 4175`（审计期间临时启动，结束后已停止，端口已确认释放；日志见项目根目录 `dev-server-4175.log`）
- 未修改任何源代码或资产文件

## 检查脚本运行结果

| 脚本 | 退出码 | 结果摘要 | 控制台错误 |
|---|---|---|---|
| check_asset_gallery.mjs | 0 | 14 枚棋子 × 3 档（desktop/mobile/lod2）共 42 组全部载入；`browser.json` 42 行无任何 pageerror | 无 |
| check_motion_gallery.mjs | 0 | 14 枚棋子 × 3 档 × 6 个 clip（idle/attack/hit/death/walk/run）全部通过：基座漂移 ≤ 1e-5、固定底座采样齐全、压缩纹理数 = 3 | 无 |
| check_native_motion_gallery.mjs | 0 | 10 个修整样板全部通过：版本校验、review-clip 过滤、固定底座校验、前后样本切换均正常；每 clip 两帧像素差异 3,470–69,438，姿态变化可见 | 无 |
| check_production_game.mjs | 0 | 桌面 + 移动双端通过：32 枚棋子全部 ready、加载 0 失败；三档特效（完整/简洁/关闭）p95 ≈ 5.7–5.8 ms、draw calls 100–103；顶视 90 点全部可见、顶行歪斜 ≤ 3px；吃子（兵五进1/卒五进1/兵五进1）与悔棋流程正常 | 无（404 已被脚本过滤，实际也未观察到） |
| check_asset_fallbacks.mjs | 0 | 模型缺失回退与解码器缺失回退两种注入故障均正常恢复（failed→0，23 项全 ready） | 无 |
| check_motion_game.mjs | 0 | 吃子动画时序正常：攻击方 attack / 受击方 hit / 死亡方 death clip 推进与不透明度正常，32 枚移动棋子均锁定 idle | 无 |
| check_camera_quality.mjs | 0 | 桌面/移动画质切换、请求共享、环绕与缩放通过 | 无 |
| check_environment.mjs | 0 | 棋盘 180 条射线交点校验通过；六个方向天空视图渲染正常 | 无 |
| check_cannon_game.mjs | 0 | 炮的两条吃子流程均通过 | 无 |
| check_vehicle_game.mjs | 0 | 马/车移动与双方吃子流程通过 | 无 |
| check_vehicle_articulation.mjs | 0 | cannon_black 三档（desktop/mobile/distant）各 15 个关节校验通过 | 无 |

**关键控制台错误清单：无。** 所有脚本捕获的 pageerror / console.error 均为空；未观察到 404、WebGL 错误、纹理解码失败或动画 clip 缺失。

## 单元测试（npm test / vitest）

- 退出码 0，6 个测试文件、24 个测试全部通过（含 `src/assets/assetCache.test.ts` 资产缓存 4 项、`src/scene/moveTimeline.test.ts` 动画时间线 4 项），耗时 2.23s。

## 截图产物路径

- 棋子检视：`docs/asset-reports/pieces/{asset}-{desktop,mobile,lod2}.png`（42 张）+ `pieces/browser.json`
- 动作检视：`docs/asset-reports/motion/browser/{asset}-{tier}.png`（42 张，攻击动作 @550ms）+ `motion/browser.json`
- 动作修整样板：`docs/asset-reports/native-motion/browser/{piece}-{clip}-{100,600}.png`、`{piece}-page.png` + `results.json`
- 实战棋局：`docs/asset-reports/game/{desktop,mobile}-{full,reduced,off,top,settings,capture}.png` + `game/performance.json`

## 目视检查结论

### 棋子检视页（抽查 4 枚）

| 截图 | 结论 |
|---|---|
| pieces/general_red-desktop.png | 红帅渲染完整：冕冠、金甲、红披风纹理清晰，底座"帥"字正常；站姿双臂略外展（资产静置姿态），无塌陷/扭曲 |
| pieces/horse_red-desktop.png | 骑兵+披甲战马完整，长矛、马甲铆钉纹理正常，骑乘姿态自然，无穿插 |
| pieces/cannon_black-desktop.png | 投石机（炮）木质结构与士兵操作员正常，底座"炮"字清晰，绳索/绞盘细节完整 |
| pieces/chariot_red-mobile.png | 中景档双马战车渲染正常，车盖、轮毂、驭手纹理清晰，无明显减面瑕疵 |

### 动作检视页（抽查 4 枚棋子攻击动作 @550ms）

| 截图 | 结论 |
|---|---|
| motion/browser/general_red-desktop.png | 红帅攻击中段：身体侧转、单掌前推，披风随动，无 T-pose 残留、无四肢穿插 |
| motion/browser/horse_black-desktop.png | 黑马攻击：骑手挺枪前刺，马匹姿态稳定，人马无穿插 |
| motion/browser/soldier_red-desktop.png | 红兵攻击：跃起挥刀、盾在身后，动态自然，无关节扭曲 |
| motion/browser/elephant_red-mobile.png | 红相（战象）攻击：象背塔楼骑手挥臂，象体披甲完整，中景 2K 纹理正常 |

### 动作修整样板页（抽查 2 枚）

- `native-motion/browser/soldier_red-walk-600.png`：行进中段单腿抬起、持刀盾姿态自然；脚本像素差分确认姿态变化（50,910 变化像素），无底座漂移。
- `native-motion/browser/horse_red-idle-100.png`：静置姿态稳定，人与马无异常。

### 实战棋局

- `game/desktop-full.png`：战场全景正常——32 枚棋子就位、围栏/瞭望塔/军帐环境资产完整、地面与天空纹理正常，UI 面板渲染正常。
- `game/desktop-capture.png`（顶视，吃子后）：90 个交叉点全部在视口内，"楚河汉界"河道正常，红黑双方阵型与吃子记录（3 手）一致，无棋子错位。

## 总体结论

**全部通过。** 11 个检查脚本退出码均为 0，vitest 24/24 通过；三类页面（棋子检视、动作检视/修整样板、实战棋局）在桌面与移动端的截图目视检查均未发现穿插、塌陷、扭曲、T-pose 残留或纹理异常；控制台无任何 404 / WebGL / 解码 / clip 缺失错误。

### 轻微观察（非阻塞）

- `general_red` 静置姿态双臂外展角度略大（接近浅 A-pose），为资产自身 rest/idle 姿态，非渲染缺陷；动作 clip 播放时姿态正常。
- 桌面端 draw calls 在特效"关闭"档仍为 100（与"简洁"相同），若追求极致可再查合批空间，但 p95 帧耗时 5.8ms 已很充裕。
