# 玄甲棋局

一期可玩原型：以中国古代铠甲为造型语言的 3D 中国象棋，支持本地双人完整基础规则、程序化 3D 棋盘与棋子、移动和吃子特效、悔棋、重开、镜头模式及表现设置。

## 环境

- Node.js 22 或更高版本
- 支持 WebGL 2 的现代浏览器

## 启动

```bash
npm install
npm run dev
```

默认开发地址为 `http://127.0.0.1:5173`。

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

## 一期验收画面

- [桌面端 1280×720](docs/screenshots/phase-1-desktop.jpg)
- [手机端 390×844](docs/screenshots/phase-1-mobile.jpg)

## 架构

- `src/game/rules`：`elephantops` 的项目适配层，负责合法着法、将军和胜负。
- `src/game/useGameController.ts`：回合状态、选择、动画锁、历史及设置。
- `src/scene`：棋盘、程序化铠甲棋子、镜头、灯光和战斗特效。
- `src/ui`：对局状态与工具栏。

## 一期边界

- 当前是本地双人对局，不含 AI、联网和账户系统。
- 棋子是程序化一期资产，可在二期替换为 GLB 高精度角色。
- 暂未实现竞赛规则中的长将、长捉和重复局面争议裁决。
- 规则依赖 `elephantops@0.1.1` 使用 GPL-3.0-or-later。闭源或商业发行前必须完成许可证评估，并决定继续 GPL 发布、取得其他授权或替换规则核心。

一期完整范围与验收标准见 `DEVELOPMENT_PLAN.md`，二期实施方案见 `PHASE_2_DEVELOPMENT_PLAN.md`。
