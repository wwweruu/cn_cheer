# 玄甲棋局

以中国古代铠甲为造型语言的 3D 中国象棋。已接入 14 类带骨骼动作与 PBR 的棋子、连续泥土战场与营地、7 套表面材质和环境贴图，支持本地双人规则、移动和吃子特效、悔棋、重开、镜头模式及画质设置。

**1.0.0 已发布**：本地双人 3D 中国象棋正式版，功能范围与已知限制见 [发布说明](docs/RELEASE_1.0.md)。许可证为 **GPL-3.0-or-later**（见 `LICENSE` 与 [THIRD_PARTY_NOTICES](docs/THIRD_PARTY_NOTICES.md)）。

## 环境

- Node.js 22 或更高版本
- 支持 WebGL 2 的现代浏览器

## 快速开始

```bash
git clone https://github.com/wwweruu/cn_cheer.git
cd cn_cheer
```

**下载运行时资产**（约 2.1 GB，不入仓库）：打开 [Release v1.0.0](https://github.com/wwweruu/cn_cheer/releases/tag/v1.0.0)，下载 5 个必需包——`cn_chess-1.0.0-assets-base.zip`、`cn_chess-1.0.0-assets-production-a.zip`、`cn_chess-1.0.0-assets-production-b.zip`、`cn_chess-1.0.0-assets-motion-a.zip`、`cn_chess-1.0.0-assets-motion-b.zip`——在**项目根目录**逐个解压（包内路径自带 `public/assets/` 前缀，解压即就位）。可用 Release 附件 `SHA256SUMS.txt` 校验完整性。不解压资产也能启动，但棋子会回退为程序化简易造型。

```bash
npm install
npm run dev
```

默认开发地址为 `http://127.0.0.1:5173`。生产构建用 `npm run build && npm run preview`。

## 质量命令

```bash
npm test
npm run lint
npm run build
npx playwright install chromium
npm run test:e2e
```

`npx playwright install chromium` 只需在首次运行端到端测试或 Playwright 升级后执行。

## 操作

- 点击己方棋子查看合法落点，再点击落点完成走子。
- 拖动棋盘旋转镜头，滚轮或双指缩放。
- 右侧工具栏可悔棋、重开、复位镜头、切换顶视、开关音效和切换特效。
- 棋局会自动保存在本机：刷新或重开浏览器后自动恢复到最近一手，悔棋历史一并还原；回到初始局面或重新开局后不再保留。
- 设置中的「棋局」分组可复制当前局面 FEN、粘贴 FEN 导入任意合法局面（导入后着法记录清空），并可将完整着法棋谱复制为中文记谱文本。
- 设置中可选自动、精细、流畅画质；窄屏也可打开设置。单个外观失败时保留可操作棋子，使用“重试外观”恢复。

## 当前成品

[动作修整样板](http://127.0.0.1:4175/native-motion-gallery.html?asset=horse_red&clip=idle)包含 10 枚棋子的原生人物动作与本地修整，支持上一轮对照、慢放、时间轴和 GLB 下载。红黑象新增本地四足行进，页面区分动作来源并列出剩余问题。

运行 `npm run dev -- --port 4175` 后可查看 [棋局](http://127.0.0.1:4175/) 和 [14 枚棋子检视页](http://127.0.0.1:4175/asset-gallery.html)。检视页支持旋转、缩放、三档精度比较及 GLB 下载。[动作检视页](http://127.0.0.1:4175/motion-gallery.html)可检查 14 类棋子的静置、攻击、受击、退场和行进，支持暂停与时间轴。

![当前游戏画面](docs/asset-reports/game/desktop-full.png)

## 一期验收画面

- [桌面端 1280×720](docs/screenshots/phase-1-desktop.jpg)
- [手机端 390×844](docs/screenshots/phase-1-mobile.jpg)

## 架构

- `src/game/rules`：`elephantops` 的项目适配层，负责合法着法、将军、胜负与同线同种棋子的前/中/后着法消歧。
- `src/game/gameRecord.ts`：对局 localStorage 存档——校验、保存与从初始局面重放着法以还原悔棋历史。
- `src/game/useGameController.ts`：回合状态、选择、动画锁、历史、设置、存档恢复与 FEN 导入。
- `src/scene`：棋盘、GLB 棋子与备用造型、镜头、灯光、环境和战斗特效。
- `src/assets`：生产路径、KTX2/WebP 解码回退、共享缓存、加载队列和距离画质切换。
- `public/assets/production-manifest.json` 与 `motion-manifest.json`：128 个静态/材质包与 84 个动画运行 GLB 的来源、体积与 SHA-256。
- `assets/source/production.json`：18 个静态、14 个动画 Blender 源工程与 7 套表面材质的位置索引。
- `src/ui`：对局状态与工具栏。

## 当前状态与边界

- 当前是本地双人对局，不含 AI、联网和账户系统。
- 14 类棋子已完成高模、8K Base Color/PBR、三档运行模型及 KTX2 压缩，并接入静置、攻击、受击、退场、行走和奔跑六段动作。人形采用修订后的 API 骨架，坐骑与机械采用本地局部关节；独立胜负表演尚未制作。
- 单模型 404、手动重试和 KTX2 解码器失败回退已通过真实浏览器检查。
- 桌面 RTX 4060 的完整特效实测约 103 次绘制、P95 5.7ms；移动端只做了同机窄屏模拟，不代表手机性能。天空与远景未达到原计划原生 ≥2K。
- 当前吃子使用可取消的共享时间轴，命中音效、攻击、受击、退场和占位同步，支持中途重开与画质切换。棋谱存档/恢复与 FEN 导入导出已接入；回放和 AI 的旧候选实现仍在本地备份，未接入当前版本。
- 暂未实现竞赛规则中的长将、长捉和重复局面争议裁决。
- 规则依赖 `elephantops@0.1.1` 使用 GPL-3.0-or-later。闭源或商业发行前必须完成许可证评估，并决定继续 GPL 发布、取得其他授权或替换规则核心。

## 开发计划

- [一期原型方案](DEVELOPMENT_PLAN.md)：历史范围与验收标准。
- [二期开发方案](PHASE_2_DEVELOPMENT_PLAN.md)：本地双人、正式资产与可取消演出、棋谱存档、性能和发布验收；AI 产品化移交三期。
- [美术资产精修流水线](docs/PHASE_2_ART_PIPELINE.md)：当前证据、完整样板、逐枚资产检查表和批次任务。

静态美术、战场和加载容错已完成基础接入；棋子动作质量仍在返工，本次原生候选尚未通过最终验收。后续二期计划还包括独立胜负表演、回放及真机/发布验收。

参考图可从仓库中的 [JPG 备份包](象棋3D参考图-备份.zip)恢复到 `象棋3D参考图-备份/`；生成脚本和部件清单在 `象棋3D参考图/`。当前样板输入与解压说明见美术流水线。

## Meshy 模型候选 Demo

API 客户端使用 Python 3.10+ 标准库。完整命令与计费见 [Meshy API 使用说明](docs/MESHY_API.md)。旧红帅 v1/v2 几何未达标后，给用户提供的官网 GLB 生成 8K/PBR，保留全部 3,010,366 个原始三角面；用户于 2026-09-06 认可样板并授权批量制作，现已完成全部 14 枚。

[最新完整高模样板](docs/GENERAL_RED_MASTER_SAMPLE.md)包含实际 GLB、五视角渲染和独立几何校验。运行 `npm run dev -- --port 4175`，打开 [最新预览](http://127.0.0.1:4175/master-review.html)。[旧样板记录](docs/GENERAL_RED_SAMPLE.md)的 LOD 仅属于被退回的旧造型。

来源、实际纹理尺寸、逐文件哈希和费用见 [生产清单与检查证据](docs/asset-reports/production.json) 及 [94 笔任务账本](docs/asset-reports/ledger.json)。无密钥或签名下载地址进入前端。

```powershell
npm run meshy -- plan
npm run meshy -- demo
npm run test:meshy
```

`plan` 是原候选配置的离线估算；`demo` 只访问本地模拟服务、消耗 0 积分，输出为测试几何体。生产流程另支持高模、Retexture、单图建模和场景图像，并共用 1800 积分累计上限与 1200 余额下限。重复运行原任务键会查询和恢复已有任务，新版本才可能产生新费用。
