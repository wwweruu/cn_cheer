# Meshy 模型批量制作 Demo

> 2026-09-06 原生动画实测：已接入并调用 `Text to Motion`、`motion_task_id` 和独立人物绑定，生成 10 枚棋子的候选样板。新增消耗 198，项目累计 1395/1800，核实账户余额 1720。四足绑定样本被服务端拒绝，脚踝和装备接触仍有待修问题，尚未替换棋局资源。见[原生样板报告](MESHY_NATIVE_MOTION_SAMPLES.md)与[接口复核](MESHY_ANIMATION_API_REVIEW.md)。

> 2026-09-06 追加任务已实施：C1 连续泥土战场替换木质棋盘；14 类棋子各有 6 段动作与三档运行包。动画新增 105 积分、土壤材质 10，累计 1197，核实余额 1868。当前验收和限制见 [交付报告](asset-reports/PRODUCTION_DELIVERY.md)。下方早期阶段的静态范围与预算保留作历史计划。

核对日期：2026-09-06。用户认可官网红帅原件的完整几何/PBR 样板后，已完成本轮 14 枚棋子、棋盘和环境资产接入。62 笔任务累计消耗 **1082**，余额 **1983**。文件、实际分辨率与验收边界见[交付报告](asset-reports/PRODUCTION_DELIVERY.md)，方法对照见[高模实测](MESHY_GEOMETRY_RESEARCH.md)。

最新制作范围为 8K 棋子、场景贴图和棋盘，执行与总预算以[高精度资产生产清单](API_ASSET_PRODUCTION_PLAN.md)为准。`--geometry-master` 为 Ultra 无重拓扑高模，25 积分；`texture-plan/texture --model <本地GLB>` 为现有模型上贴图，8K=15、2K/4K=10，默认仅红帅。现已支持单图建模、Text to Image、Image to Image 和最多三个并行任务，全部共用预算、账本、恢复与下载校验；54 项离线测试通过。

场景配置在 `scripts/meshy/scene-assets.json`，失败图像的修订在 `scene-image-revisions.json`。`npm run meshy -- scene-plan` 仅检查输入和估价；`scene-run --assets <资产键> --concurrency 3` 才会执行真实队列。已有任务按工序、版本及输入哈希恢复，不因重启再扣费。生产候选及失败版本均保留。

## 1. 现在可以直接运行

需要 Python 3.10+，只用标准库，无须 `pip install`。本项目现有的 npm 命令可作入口，或直接执行 `python scripts/meshy/cli.py ...`。

在项目根目录运行：

```powershell
# 检查 14 枚棋子、42 张单视图，打印费用；不联网
npm run meshy -- plan

# 本地 HTTP 模拟：提交、轮询、下载、校验、重启续跑；不读取 Key
npm run meshy -- demo

# 故障与预算自动化测试；不需要真实参考图或 Key
npm run test:meshy
```

`plan` 与 `demo` 使用本机解压的 `象棋3D参考图-备份/<棋子>/正面.jpg、侧面.jpg、背面.jpg`。如缺失，先解压仓库根目录的 JPG 备份包。测试命令自行构造临时输入，不依赖该备份包。

预期：`plan` 验证 14 枚 / 42 张图，首轮新建费用 420；`demo` 完成 14 次模拟 POST，再次运行相同任务新增 POST 为 0，模拟余额 2580，真实消耗为 0。每次 Demo 输出在独立的 `.meshy/demo/run-*/` 中，报告为 `demo-report.json`。

实现文件：

| 文件 | 用途 |
| --- | --- |
| [cli.py](../scripts/meshy/cli.py) | 命令入口，离线与真实调用分开 |
| [pipeline.py](../scripts/meshy/pipeline.py) | HTTP、余额检查、本地账本、恢复和资产下载 |
| [pieces.json](../scripts/meshy/pieces.json) | 与运行时 14 个资产键对应的参考图及参数 |
| [mock_server.py](../scripts/meshy/mock_server.py) | 仅监听 `127.0.0.1` 的模拟 API |
| [test_pipeline.py](../scripts/meshy/test_pipeline.py) | 预算、HTTP 协议与故障恢复测试 |
| [.env.example](../.env.example) | 本地 Key 配置模板 |

## 2. 当前 API 计费判断

下表是 **API 每次调用**的价格快照，不能套用网页套餐中的免费重试、绑定或重拓扑宣传。多图接口一次提交三张视图仍是一个模型任务；14 个资产可供 32 枚棋子复用，首轮按 14 次计算。来源：[官方 API 价格](https://docs.meshy.ai/en/api/pricing)、[多图接口](https://docs.meshy.ai/en/api/multi-image-to-3d)。

| 与项目有关的调用 | 积分 / 次 |
| --- | ---: |
| Meshy 6/7 多图或单图建模，不带贴图 | 20 |
| Meshy 6/7 建模，带 2K 或 4K 贴图 | 30 |
| Meshy 6/7 建模，带 8K 贴图 | 35 |
| Meshy 7 开启 Ultra | 在基础价上加 5 |
| Retexture，2K/4K；8K | 10；15 |
| 单独调用 Remesh / Auto-Rigging | 各 5 |
| Animation | 3 |
| Text to Motion，Prime；Swift（现有脚本尚未接入） | 10；3 |
| Convert / Resize | 各 1 |
| UV Unwrap | 5 |

旧贴图 Demo 保留 `meshy-7`、Ultra 关闭、PBR、GLB 和 2K 默认，可显式选择 4K/8K；请求内重拓扑，未另调收费 Remesh。它不再作为新生产的几何质量配置。新高模命令 `plan/run --pieces general_red --variant 2 --geometry-master` 使用 Ultra、关闭重拓扑、跳过贴图，不设置目标面数。新配置已实测但仍未达指定造型，不会因接口成功就自动批量，也不会失败后自动切模型重发。

创建任务时扣费；技术失败可退款，成功但造型不满意不能按失败退款。账本只在终态响应明确报告 `consumed_credits=0` 后释放失败任务的全部预留额；字段缺失时继续保守占用预算。来源：[官方退款说明](https://help.meshy.ai/en/articles/15643245-when-were-my-meshy-credits-used-or-refunded)、[Usage 的扣费与退款口径](https://docs.meshy.ai/en/api/usage)。

用户已确认 3000 积分可用于 API。正式运行仍会通过 [Balance API](https://docs.meshy.ai/en/api/balance) 读取当时余额，不以手填的 3000 作为授权服务器余额。Usage 汇总接口仅对 Studio/Enterprise 团队 Key 开放，因此本 Demo 使用余额接口、逐任务 `consumed_credits` 和本地记录对账。[Usage 权限说明](https://docs.meshy.ai/en/api/usage)

## 3. 旧版仅棋子预算（Demo 基线）

以下为按当前单价计算的项目分配建议，后处理行是**后续预留，并非 Demo 会自动执行的付费任务**。

本节不再作为扩展范围的生产预算；不要与新清单的预算叠加。

| 项目 | 算式 | 积分 |
| --- | --- | ---: |
| 首轮全部 14 枚带 PBR 候选 | 14 × 30 | 420 |
| 每枚最多再生成两版的余量 | 14 × 2 × 30 | 840 |
| 两个额外 LOD，如使用单独 Remesh | 14 × 2 × 5 | 140 |
| 六个人形候选绑定，须先验证适配 | 6 × 5 | 30 |
| 六个人形各七次动作生成的预留 | 6 × 7 × 3 | 126 |
| 每枚一次 2K 材质修订的预留 | 14 × 10 | 140 |
| **计划上界** | | **1696** |
| **相对 3000 的剩余额度** | 3000 − 1696 | **1304** |

首轮红帅、红马、红炮试样是 3 × 30 = 90，**已包含在 420 内**；通过造型检查后补其余 11 枚是 330。优先只重做不合格项，不会自动跑满三轮。LOD、拆件、底座、文字修正与自制动画也可在 Blender 中完成，无额外 Meshy 积分消耗，但仍需制作和验收工作量。

客户端将累计已用/预留限定为 **1800**，每次提交前检查账户至少保留 **1200**。每枚各工序的 `variant=1..3`，不是三轮额度会自动用满。建模与 Retexture 已共用账本；以后接入其他端点也必须复用，不能另开无预算脚本。

这些是按已核对价格执行的客户端提交限制。Meshy 没有在这个生成请求中提供服务端“最高扣费”参数；若服务端临时改价，一笔已接收任务的实际扣费可能高于估算，客户端检测到差异会保存已有成果并停止后续提交。其他应用在同一账户上的并发消费也无法由本脚本阻止。正式批量前需重新核对价格，并保留同一工作目录的账本。

**预算可覆盖上述候选与后处理次数，无法承诺所有成品一次生成成功。** 当前马包含骑手，炮包含炮手、炮身与弹药；底座、披风、武器也可能粘连。Rigging 说明页强调标准双足人形，而官方 OpenAPI 列有 `animation_type=biped/quadruped`，网页帮助也说明支持四足行走。四足 API 可作为待实测候选，不能承诺能直接处理坐骑与人物的复合模型；文字生成动作套用目前仅支持双足骨架。应先拆件、验证绑定和原生动作，再决定本地补充制作范围。详见[动画接口复核](MESHY_ANIMATION_API_REVIEW.md)。

## 4. 提供 Key 后的真实流程

将 `.env.example` 复制为根目录 `.env`（已存在则直接编辑），填写：

```dotenv
MESHY_API_KEY=你的真实Key
```

不要使用 `VITE_` 前缀；Key 只由 Python 读取，不进入网页包、请求预览、账本或 Git。真实 API 地址固定为 `https://api.meshy.ai/openapi/v1`。

```powershell
# 只读取余额，不生成
npm run meshy -- balance

# 已执行的单枚红帅样板命令；同参数重跑会复用已完成任务，不再新建
npm run meshy -- run --pieces general_red --texture-resolution 8k --save-source --target-polycount 20000

# 查看本地进度与已用/预留额，不联网
npm run meshy -- status

# 断网、超时、下载失败后，仅继续已有任务的查询与下载
npm run meshy -- resume

# 经查看确实要重新生成某一枚时，显式选择一个未用版本；新增 30
npm run meshy -- run --pieces horse_red --variant 2
```

`run` 默认已改为仅 `general_red`，当前仍应显式给出完整参数；验收前不要使用 `all` 或三枚 `pilot`。计划与 Demo 默认 `all`，均不会真实付费。实际生成顺序执行，默认每 10 秒查询一次，每个任务等待最多 1800 秒。`--wait-seconds` / `--poll-seconds` 可调整等待时间。退出或等待到期不取消远程任务；使用 `resume` 继续。后续批量须先在同一账本内实现限额并发，不能启动多个进程绕过文件锁。[官方限流](https://docs.meshy.ai/en/api/rate-limits)

输入会将本地的正面、侧面、背面编码为 `data:image/jpeg;base64,...`，通过一个 `POST /multi-image-to-3d` 提交；先保存返回的 `result` 任务 ID，再用 `GET /multi-image-to-3d/{id}` 查询。正面排首位；不会将三视图拼接图当成三个独立角度。[官方接口约定](https://docs.meshy.ai/en/api/multi-image-to-3d)

候选保存至 `assets/generated/meshy/<资产键>/v<版本>/`，包括：

- `model.glb`、接口返回的各张 PBR 贴图和预览图。
- 启用 `--save-source` 时额外保存 `source_pre_remeshed.glb`；本次高模无贴图，不能作为 8K 带材质模型使用。
- `task.json`：任务状态、消耗、到期时间及下载地址。
- `inspection.json`：容器、网格、材质/纹理/骨骼/动画数量及文件哈希；明确标记尚未通过正式验收。

底面原点、+Z 朝向、尺寸、面数、分件、纹理压缩、动画与性能须按[美术验收流程](PHASE_2_ART_PIPELINE.md)检查后再导入。脚本不会将原始候选直接覆盖当前 `public/assets/models/`。

API 资产通常最多保留三天，Enterprise 可有更长保留期；成功后脚本立即下载。签名链接过期时，`resume` 重新查询任务取得下载地址；如果资产已被服务器删除，查询不能恢复它，也不会自动重新付费生成。[资产保留说明](https://docs.meshy.ai/en/api/asset-retention)、[查询刷新签名地址](https://docs.meshy.ai/en/api/usage)

## 5. 重复扣费防护与异常恢复

真实账本固定为 `.meshy/live/ledger.json`，模拟账本在其他目录。**首次付费后请备份并保留真实账本，不要通过删除、复制旧账本或换工作目录来“重置”任务。** 客户端防重只覆盖这一个项目账本；随机任务名称用于核对，不是 Meshy 提供的幂等键。

| 情况 | 行为 |
| --- | --- |
| 重复运行相同资产键 + variant + 输入 | 已下载且哈希完整则跳过；进行中的任务继续查询 |
| 同一 variant 的参考图或参数改变 | 拒绝复用，要求改用尚未使用的 variant |
| 余额或批次累计预算不足 | 提交前停止；整批输入和总预算先检查 |
| GET 限流或临时服务故障 | 有界退避重试，最多四次 GET |
| POST 明确 400/401/402/403/429 拒绝等 | 停止；记录拒绝，不自动重试 |
| POST 超时、5xx、异常响应或提交中断 | 保留积分预留，阻止新付费任务，等待核对远程任务 |
| 任务失败或取消 | 停止批次；按明确报告的消耗记账，不自动重新生成 |
| 下载失败、损坏或哈希不符 | 保留已完成任务；`resume` 重试下载，不新建模型 |
| 进程并发 | 操作系统文件锁使同一项目只能有一个运行者；进程退出自动释放 |

当 `status` 显示 `UNKNOWN` 或 `RESERVED` 且没有 ID 时，查询任务列表，按账本中唯一的 `name` 寻找对应任务：

```powershell
npm run meshy -- tasks --page 1
npm run meshy -- reconcile --piece general_red --variant 1 --task-id 实际任务ID
npm run meshy -- resume
```

`reconcile` 会核对服务器返回的 ID 和名称，绝不发送新建请求。必要时查询后续页；如果查不到匹配记录，不能推断“没有扣费”，需进一步核对账户记录/服务支持。Demo 不提供强制清空未知扣费记录的快捷开关。

## 6. 本地验证记录

2026-09-05 在本项目 Windows / Python 3.13 / Node 24 环境验证：

- 14 个清单键覆盖运行时模型键；实际 42 张 JPG 输入均存在，通过类型、大小及 SHA-256 检查。
- 14 份完整请求已对照当日[官方 OpenAPI schema](https://docs.meshy.ai/openapi.json)检查字段、类型、枚举、范围和长度；本地记录为 `.meshy/contract-validation.json`。
- 本地 HTTP Demo 的 14 个任务走通提交、进度、下载；重启读取账本后同批重跑，额外 POST 为 0。
- 32 项自动化测试覆盖整批预算、实时余额变化、异常计费、退款、GET 429/503、POST 不重试、崩溃预留、未知任务核对、列表分页、断点续跑、损坏 GLB、下载鉴权隔离、并发锁，以及 8K=35 和重拓扑前高模归档。
- 项目既有 15 项测试、lint、生产构建通过；主 JS 产物仍约 1.27 MB（gzip 约 352 KB）。

以上为 2026-09-05 的首次验证记录。2026-09-06 已完成全部 62 个真实任务归档、54 项离线测试、19 项前端测试及加载回退检查；真实任务、费用、参数、输入和文件哈希见[去除签名地址的账本](asset-reports/ledger.json)。
