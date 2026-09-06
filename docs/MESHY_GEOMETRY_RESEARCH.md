# 红帅：官网 Agent 与 API 高模实测

核对日期：2026-09-05；后续更新 2026-09-06。用户确认官网 Agent 直接使用原始三视图，没有先重画参考图。**以用户提供的 GLB 为几何基准；API 建模 v1/v2 均未达标。** 随后已给官网原件生成 8K/PBR 并恢复全部原始三角面，详见[最新完整样板](GENERAL_RED_MASTER_SAMPLE.md)。下文保留几何对照证据，不表示剩余 13 枚已能稳定复现官网效果。

## 实测结果

| 来源 | 原始三角面 | 实际检查 | 结论 |
| --- | ---: | --- | --- |
| 官网 Agent，用户提供 | 3,010,366 | 长披风、圆形底座、文字装饰、冠冕珠串和服饰层次保留较完整 | 指定几何基准 |
| API v1，重拓扑前原件 | 1,906,764 | 长披风和底座已经缺失 | 不是只因之后减到 20k 才丢失结构 |
| API v1，带贴图输出 | 20,557 | 全局简化，局部细节粗糙 | 用户已退回造型；贴图方向保留 |
| API v2，Ultra，无重拓扑 | 2,917,173 | 相对指定基准披风不完整，底座缺失，珠串不完整，靴尖与脚踝存在可见孔洞/黑区 | 用户再次指出缺陷，本次检查未通过 |

面数接近不代表还原度相同。v2 仅为一次对照生成，存在生成随机性，也同时改变了 Ultra、重拓扑与贴图阶段，不能把全部差异严格归因于某一个参数。检查使用 [inspect_high_geometry.py](../blender/inspect_high_geometry.py) 导入原始 GLB，以同一素模材质、相机和光照渲染；仅整体等高居中，未修形、减面或叠加法线贴图。基准模型包含底座，人物在同一整体高度下会显得稍小。

[本地对比页](http://127.0.0.1:4175/assets/review/general_red/geometry-comparison/index.html)包含正面、45°、背面、细节和三份原始 GLB 下载。重新准备：

```powershell
python scripts/prepare_geometry_comparison.py
npm run dev -- --port 4175
```

## 官网方法：已查明与尚未查明

官方将 Agent 描述为对话式创作流程，可从图片进入 3D 生成，再进入标准后处理。文档没有给出这枚模型的内部调用日志，也没有足够证据证明官网 Agent 使用独有几何引擎，或证明它与公开 API 的全部内部参数完全相同。[官方 Agent 说明](https://docs.meshy.ai/en/webapp/3d-agent)

官网当前表单曾显示 Meshy 7、高细节、无贴图；但空白表单的当前状态不能当作这枚历史任务的真实参数。本次未成功读取到该任务的完整历史配置。因此不能声称已经复刻了它的精确生成流程。公开的 [Meshy Agent 工具仓库](https://github.com/meshy-dev/meshy-3d-agent) 是集成参考，也不能据此推断官网历史任务的服务端配置。

公开 API 明确提供 `ultra_mode=true` 以提高几何保真度，并建议最高质量时关闭 `should_remesh`。`image_urls` 可用 1–4 张图，Meshy 7 将第一张作为主正面；`pose_mode=""` 不强制变更姿势；`image_enhancement=false` 保持原图外观。[多图 API 参数](https://docs.meshy.ai/en/api/multi-image-to-3d)

已据此增加 `--geometry-master` 并完成真实实验。**可以通过 API 获得约 300 万面的高模，但目前尚未验证出能稳定达到指定 GLB 还原度的 API 参数组合。** 后续需要取得官网成功任务的实际配置或更多受控证据再确定生成路线，不能把“支持 Ultra”写成“已经达到官网效果”。

## 本次可复现请求与费用

```powershell
# 离线查看参数与估价
python scripts/meshy/cli.py plan --pieces general_red --variant 2 --geometry-master
# 这笔任务已完成；下列相同命令只恢复已有记录，不会重新付费生成
python scripts/meshy/cli.py run --pieces general_red --variant 2 --geometry-master
```

关键请求：

```json
{
  "ai_model": "meshy-7",
  "ultra_mode": true,
  "should_remesh": false,
  "should_texture": false,
  "pose_mode": "",
  "image_enhancement": false,
  "auto_size": false,
  "target_formats": ["glb"],
  "multi_view_thumbnails": true
}
```

输入为 `象棋3D参考图-备份/帅-红方/正面.jpg、侧面.jpg、背面.jpg`，与 v1 输入逐文件 SHA-256 一致。请求没有目标面数或贴图分辨率。任务 `01a07232-f762-74b6-a207-d4fd5020be13` 成功归档到 `assets/generated/meshy/general_red/v2/`，服务端报告消耗 **25 积分**，余额 **3030 → 3005**。与 v1 的 35 合计 **60**，统一账本 `.meshy/live/ledger.json` 中仅两笔红帅任务。技术成功与造型验收分别记录。

按核对时价格，Ultra 无贴图高模为 20 + 5 = 25；另做 8K Retexture 为 15，两阶段合计 40。优先验收几何再花贴图积分。费用来源：[官方 API 价格](https://docs.meshy.ai/en/api/pricing)。本次没有给不合格 v2 再做贴图，也没有生成其他棋子。

## 后续生产标准

1. 红帅的源几何采用指定官网 GLB 作为基准。原件保留，检查副本记录来源和哈希；不再通过细分旧低模或补简单底座冒充同等还原度。
   用户追加明确要求：**底座不能丢失**。保留原件底座的整体形状、层级边饰、文字装饰和人物站立关系；贴图、分件、重拓扑及每档 LOD 导出前后都检查，底座缺失或明显变形直接判定不合格。展示时裁切图片也不能作为完整资产验收证据。
2. 其他棋子先验收原始高模：完整轮廓、披风/底座/武器、冠冕、手指、面部、甲片、衣纹与靴子。不是每枚必须恰好 300 万面，也不能靠面数直接判定通过。
3. 几何合格后再做 UV 和 PBR。官网原件没有 UV、材质或贴图；旧模型的 UV 与几何不同，不能直接把旧 PNG 挂上就认为贴图已经迁移。可针对该高模重新展开 UV 并按三视图生成/烘焙同等材质效果。
4. 原始高模始终保留。20k/8k/3k 仅用于后续游戏运行版本的初始目标，不能提前约束源几何，也不能为达面数而删掉主要结构；运行版本还需对照高模检查轮廓与近景细节，并实测性能。
5. 仍先完成一枚并由用户验收，之后才批量。v1 被用户退回；v2 由本次几何检查判为未达标，均未成为正式游戏资产。

Retexture 处理无 UV 原件需要 `enable_original_uv=false`，输出后核对几何保留情况。后续已实际验证该账户支持 Meshy 7 多视图贴图；服务端做了整体归一化与少量三角面调整，因此将 UV/PBR 迁回原件后再次独立检查。该项另花 15，项目合计 75、余额 2990，详见最新样板。[Retexture 参数与限制](https://docs.meshy.ai/en/api/retexture)

## 可追溯文件与校验

| 文件 | SHA-256 |
| --- | --- |
| `建模素材/红帅/Meshy_AI_Imperial_Marshal_0905140513_generate.glb` | `8470e341567efbdc4a0bfe3cbc2413576aee99ef0d3f60c6fea49a4ff7339daf` |
| `assets/generated/meshy/general_red/v1/source_pre_remeshed.glb` | `1080956e64cc396ee36ade412972fdfd5fba2437dc0afdeb11cf7b2c28140a38` |
| `assets/generated/meshy/general_red/v2/model.glb` | `0cf72e142cbe9516502597d7c415d407328dad444a7d5c184374c9002e41608b` |

35 项 Meshy 离线测试通过，包括新增高模的 25 积分预留、无纹理归档、相同任务恢复和旧版本保护。对比页准备脚本核对原件 SHA-256 与渲染记录，展示文件不含 Key、服务端任务响应或签名 URL。

对比页四个视角、12 张渲染图、三份 GLB 下载均通过 Chrome 检查，页面无异常，390px 窄屏无横向溢出；lint 与构建通过。Vite 开发服务忽略了大型预览目录的文件监听，新增预览文件后应重启服务再查看。
