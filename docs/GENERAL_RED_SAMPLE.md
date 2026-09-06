# 红帅单枚静态样板 · v1 造型未通过

制作日期：2026-09-05。用户已退回 `general_red/v1/review-r8` 的造型，Ultra 高模 v2 对照也未达标。2026-09-06 已给用户指定的官网 GLB 上贴图，并完整保留原始几何；最新交付见[完整高模样板](GENERAL_RED_MASTER_SAMPLE.md)。三笔 API 任务合计 75 积分，余额 2990；其余 13 枚及正式游戏模型未开始替换。

下面保留 v1 的制作、贴图与运行检查记录，不能将这些技术检查视为造型验收通过。

## 查看样板

运行本地开发服务后，访问 [可旋转验收页](http://127.0.0.1:4175/review.html)。支持正面、45°、背面、脸部近景、线框、棋格尺度，以及四个模型版本切换。

```powershell
# 已生成的本地文件如需重新放入预览目录，执行此命令；不调用 API
python scripts/prepare_sample_review.py --source assets/generated/meshy/general_red/v1/review-r8
npm run dev -- --port 4175
```

上面的校验和准备脚本依赖 Pillow；API 客户端本身仍只依赖标准库。预览文件位于 `public/assets/review/general_red/`，已加入 Git 忽略，不包含 Key、任务响应或签名下载地址。

![红帅45度实物渲染](../assets/generated/meshy/general_red/v1/review-r8/review_three_quarter.png)

本图使用实际 4K GLB 在 Blender 中渲染，非概念参考图。页面则由 Three.js 实时渲染同一 GLB。

## 实际调用与费用

| 项目 | 结果 |
| --- | --- |
| 输入 | `象棋3D参考图-备份/帅-红方/` 下的正面、侧面、背面 JPG |
| 调用 | Multi Image to 3D，Meshy 7，8K，PBR，Ultra 关闭 |
| 几何参数 | `should_remesh=true`，目标 20,000 三角面，保存重拓扑前高模 |
| 任务 ID | `01a071c2-91fd-7298-9f0e-74b8d5c3f5cf` |
| 终态 | `SUCCEEDED`，已归档 |
| 实际积分 | 35；余额 3065 → 3030 |
| 本地后处理 | Blender 修复、底座、文字、LOD 和材质烘焙，无额外 Meshy 消费 |

真实账本为 `.meshy/live/ledger.json`，现有 v1=35、v2=25、官网原件贴图=15 三笔。上表仅记录 v1 历史费用。不要删除账本或另开目录重跑付费任务。

## 文件与规格

原始 API 文件位于 `assets/generated/meshy/general_red/v1/`：

- `model.glb`：原始带材质候选，20,557 三角面；Base Color 实际 8192×8192，法线及打包金属/粗糙度图实际 4096×4096。
- `source_pre_remeshed.glb`：1,906,764 三角面的原始高模，**不含纹理**。
- 原始独立 PBR 图、任务记录、预览图与检查记录均已下载保存。

本次验收文件位于 `assets/generated/meshy/general_red/v1/review-r8/`：

| 文件 | 三角面 | 纹理 | 体积 |
| --- | ---: | --- | ---: |
| `general_red_desktop.glb` | 19,913 | 4K | 10.53 MiB |
| `general_red_mobile.glb` | 19,913 | 2K | 4.10 MiB |
| `general_red_lod1.glb` | 7,723 | 2K，重新烘焙 | 3.54 MiB |
| `general_red_lod2.glb` | 2,739 | 2K，重新烘焙 | 2.95 MiB |
| `general_red_source.blend` | 整理后的源网格 | 保留 8K 原图 | 可继续编辑 |
| `general_red_lod1_bake.blend`、`general_red_lod2_bake.blend` | LOD 与烘焙来源 | 已打包 | 可继续编辑 |
| `review_*.png` | 正面、45°、背面、细节 | 1200×1440 | 实物渲染 |
| `review.json`、`runtime-validation.json` | 几何、纹理、文件哈希 | `user_approved=false` | 验收记录 |

全部运行 GLB 内嵌三张 WebP 纹理，通过 `EXT_texture_webp` 载入。每份包含人物和底座两个网格、三个材质/绘制单元。总高约 1.511，横向约 0.901，底面中心为原点，面朝 glTF +Z；适配现有 1.05 的格距。红方的朝向变换沿用游戏现有逻辑。

已补充赤漆圆底座、铜金边饰，以及用楷体字形生成的“帅”字。修复导入时拆开的顶点与旧法线，改善脸、衣袖的折面。远景模型通过封闭表面重建、减面、新 UV 和 PBR 烘焙制作，避免直接大幅减面造成的破面。

## 用户验收重点与当前边界

- 检查人物比例、红金配色、脸部、手掌、甲片和底座文字。
- 冠冕流苏、指尖仍偏粗；背部披风没有完整还原参考图。用户已明确判定本版不达到批量标准。
- LOD1/LOD2 用于远景，近看会损失手部、冠冕细节，金属高光也与主模型有差异。正式自动切换距离和跳变仍待整盘验收；近景请检查 4K 主模型。
- 当前是静态视觉样板。绑定、动作、武器拆分、KTX2、自动 LOD、最终材质合并及真机性能尚未完成，不将这些标记为验收通过。

## 已执行检查

- 四份 GLB 的容器、索引范围、有限坐标、单位法线、实际三角面、嵌入纹理尺寸、PBR 通道引用与文件 SHA-256 均通过本地校验。
- Chrome 实时预览的四版本载入、视角和开关操作通过；390×844 窄屏无横向溢出。测试证据保存在 `.meshy/review-*.png` 及浏览器检查记录。
- 在真实游戏页中，仅替换该次浏览器请求的红帅 GLB 响应进行检查：14 个模型均成功载入，无页面异常。截图为 `.meshy/general-red-ingame.png`；原有模型文件、运行清单和游戏逻辑未改变。
- 32 项 Meshy 离线用例、现有 15 项游戏测试通过。预览代码通过 TypeScript、lint 和构建检查。
- 构建仍提示 Three.js 相关大体积 JS 分块；当前验证不代表整盘内存、帧率或正式发布已通过。

## 可复现本地制作

每次选择新的目录名以保留已有版本。第一个脚本输出源工程、4K/2K 主模型与渲染；第二个重建低精度模型并烘焙贴图；最后校验并准备预览。三个步骤都不调用 Meshy。

```powershell
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --python blender/prepare_meshy_sample.py -- --input assets/generated/meshy/general_red/v1/model.glb --output assets/generated/meshy/general_red/v1/review-next-primary --render-size 1200 --add-base

& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --python blender/bake_sample_lods.py -- --source assets/generated/meshy/general_red/v1/review-next-primary --output assets/generated/meshy/general_red/v1/review-next-final

python scripts/prepare_sample_review.py --source assets/generated/meshy/general_red/v1/review-next-final
```

用户验收通过后，记录认可的版本与需要沿用的具体标准，再实现带整批预留、限流及恢复逻辑的并发调度。不能启动多个客户端进程绕过现有单账本锁。
