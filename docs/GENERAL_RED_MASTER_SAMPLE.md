# 红帅完整高模贴图样板

完成日期：2026-09-06。**已将同等目标的 8K/PBR 贴图应用到用户提供的官网 GLB，保留原件全部 3,010,366 个三角面的空间表面。** 底座、边饰、“帅”字、完整披风、冠冕珠串与靴子按原件保留；用户源文件未修改。用户于 2026-09-06 明确确认“可以，就按这个制作吧”，本版成为后续制作标准。其余棋子按批次制作并逐枚检查结构；运行版本与游戏接入继续制作。

[打开可旋转样板](http://127.0.0.1:4175/master-review.html)：可检查正面、45°、披风背面、脸部与珠串、底座与靴子，也可下载完整 GLB。

![完整源高模贴图效果](../assets/generated/meshy/general_red/texture/v1/preserved/renders/three_quarter.png)

## 本次交付

| 文件 | 内容 |
| --- | --- |
| `assets/generated/meshy/general_red/texture/v1/preserved/model.glb` | 完整源几何与嵌入式 PBR，140,612,912 字节，约 134.10 MiB |
| 同目录 `geometry-preservation.json` | 独立表面比对通过；三角面与原始包围盒一致 |
| 同目录 `model.transfer.json` | 贴图来源、坐标对应误差、微小三角面恢复和哈希 |
| 同目录 `renders/` | 实际交付 GLB 的正面、45°、背面、细节、底座，1200×1440 |
| `assets/generated/meshy/general_red/texture/v1/model.glb` | 服务端原始贴图输出，保留归档；不是最终交付的几何版本 |
| `assets/generated/meshy/general_red/geometry-baseline.json` | 官网原件哈希、必保留结构与已退回候选记录 |

贴图实测为 8192×8192 Base Color，4096×4096 法线和打包金属/粗糙度；1 个材质、3 张嵌入纹理。独立原始 PNG 也已归档。完整源高模用于近景验收，运行 LOD 尚未据本版制作。

## 为什么增加本地几何恢复

Retexture 返回模型保留了主要结构，但将整体归一化至高度 2，并把三角面从 3,010,366 调整为 3,010,174。为严格保留用户指定原件，本地将新 UV、法线与 PBR 迁回原件坐标和全部原始三角面。

3,010,107 个三角面取得精确的顶点对应，其余 259 个微小面恢复原始几何并从附近纹理顶点取得 UV；最大局部 UV 取样距离为归一化高度的约 0.08%，未移动几何。嵌入贴图字节不变。最后用独立脚本按 float32 坐标逐位比较全部世界空间三角面，完整表面与原件一致，无容差放宽；顶点、三角面顺序和 UV 接缝分点不影响比较。

保留原件完整几何不等于宣称它本身毫无缺陷：冠冕顶部框架等细节沿用用户指定版本，当前未擅自雕改。贴图、金属高光和微小 UV 区域仍属于视觉验收范围。

## 实际费用与技术检查

Retexture 任务 `01a0725c-802d-74d1-8896-2f32b469dade`：Meshy 7、三张原始参考图、重新展开 UV、8K/PBR，消耗 **15 积分**。总账本三笔：旧 v1=35、Ultra 对照 v2=25、本次贴图=15，累计 **75**；本次后余额 **2990**。几何迁移、渲染、下载与验证均在本地完成，没有重新提交付费生成。

41 项 API 离线测试通过，覆盖新贴图端点、共用预算、未知提交恢复和分段下载完整性。独立几何检查通过；Chrome 实测完整模型载入、四个检查视角、线框/旋转/棋格开关正常，390px 窄屏无横向溢出。五个视角的 Blender 渲染经过视觉检查。lint 与构建通过。当前不将单枚源高模检查当作 32 枚整盘性能通过。

## 复现与恢复

```powershell
# 只恢复并下载已有任务，不新建付费任务
python scripts/meshy/cli.py resume

# 同一贴图版本使用相同参数不会重复创建；更换来源必须新版本
python scripts/meshy/cli.py texture-plan --model "建模素材/红帅/Meshy_AI_Imperial_Marshal_0905140513_generate.glb"

# UV 迁回原始几何，依赖 NumPy、SciPy；本次 SciPy 仅安装于 .meshy/pydeps
python scripts/restore_source_geometry.py --source "建模素材/红帅/Meshy_AI_Imperial_Marshal_0905140513_generate.glb" --textured assets/generated/meshy/general_red/texture/v1/model.glb --output assets/generated/meshy/general_red/texture/v1/preserved/model.glb
python blender/verify_texture_geometry.py --source "建模素材/红帅/Meshy_AI_Imperial_Marshal_0905140513_generate.glb" --textured assets/generated/meshy/general_red/texture/v1/preserved/model.glb --output assets/generated/meshy/general_red/texture/v1/preserved/geometry-preservation.json

# 本地预览准备依赖 Pillow
python scripts/prepare_master_review.py --source assets/generated/meshy/general_red/texture/v1/preserved --geometry-report assets/generated/meshy/general_red/texture/v1/preserved/geometry-preservation.json
npm run dev -- --port 4175
```

最终 GLB SHA-256：`a8cc6eab5cc35fcb563dd8733a4ea5d9844c7cbda69f312fb9621bd0da05df4a`。

关于为何旧 API 两版未达标、尚未完全复刻官网历史生成流程，见[方法调研](MESHY_GEOMETRY_RESEARCH.md)。当前红帅使用用户提供的官网原件；没有把这次贴图成功当作其他 13 枚已能稳定生成同等几何的证据。
