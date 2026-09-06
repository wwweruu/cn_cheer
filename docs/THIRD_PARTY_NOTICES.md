# 第三方依赖与资产来源清单（1.0.0）

## 代码依赖

| 依赖 | 版本 | 许可证 | 用途 |
|---|---|---|---|
| elephantops | 0.1.1 | **GPL-3.0-or-later** | 中国象棋规则核心（合法着法、将军、胜负判定） |
| react / react-dom | 19.2.8 | MIT | UI |
| three | 0.185.3 | MIT | WebGL 渲染 |
| @react-three/fiber | 9.7.0 | MIT | React Three.js 绑定 |
| @react-three/drei | 10.7.7 | MIT | Three.js 辅助组件 |
| motion | 12.43.0 | MIT | UI 动效 |
| @phosphor-icons/react | 2.1.10 | MIT | 图标 |

开发依赖（vite、typescript、eslint、vitest、playwright 等）均为 MIT / Apache-2.0，详见 `package.json` 与各自包内 LICENSE。

**许可证路线**：因规则核心 elephantops 为 GPL-3.0-or-later，本项目 1.0 按 GPL-3.0-or-later 开源发布（见根目录 `LICENSE`）。闭源或商业发行前必须替换规则实现或取得其他授权。

## 美术与音频资产

- 14 类棋子高模与 PBR 纹理：由 Meshy API 付费生成（账户积分消耗与任务账本见 `docs/asset-reports/ledger.json`），再经本地 Blender 管线修整（`blender/`）。按 Meshy 付费订阅条款可用于商业用途；原始任务记录见 `docs/asset-reports/production.json`。
- 战场、营地、环境与表面材质：来源与逐文件 SHA-256 见 `docs/asset-reports/production.json`。
- 运行时资产（GLB/KTX2/WebP）不进 git 仓库，以 Release 附件分发；`public/assets/production-manifest.json` 与 `public/assets/motion-manifest.json` 记录全部 212 个运行时文件的来源、体积与哈希。
- 音效：随动作演出接入的命中/走子音效，来源记录见 `docs/asset-reports/production.json`。

## 校验证据

- `docs/asset-reports/integrity-audit-2026-09-06.md`：212 个清单资产 SHA-256 全量校验通过。
- `docs/asset-reports/geometry-animation-audit-2026-09-06.md`：222 个 GLB 几何/蒙皮/动画技术校验。
- `docs/asset-reports/runtime-visual-audit-2026-09-06.md`：真实浏览器渲染与性能校验。
