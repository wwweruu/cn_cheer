# Meshy 动画接口复核

核对日期：2026-09-06。本文保留初次文档调查；随后用户授权在预算内直接生成，现已完成原生接口接入和实际调用，费用、候选样板与失败边界见[原生样板报告](MESHY_NATIVE_MOTION_SAMPLES.md)。

用户指出黑将武器和脚部错位、红士仅腹部蠕动、象步态不自然、骑手缺少动作、红炮人物头部扭曲、兵卒脚步扭曲。这些反馈说明当前动画尚未通过视觉验收；文件有效、存在动画轨道和播放正常不能代表动作合格。

## 已确认的接口

| 用途 | 请求 | 关键参数 |
| --- | --- | --- |
| 自动绑定 | `POST /openapi/v1/rigging` | `input_task_id` 或 `model_url`，`height_meters`，可选 `texture_image_url`；OpenAPI 另列 `animation_type: biped / quadruped` |
| 文字生成动作 | `POST /openapi/v1/text-to-motion` | `prompt`、`duration`、`mode` |
| 给模型应用动作 | `POST /openapi/v1/animations` | `rig_task_id`，以及二选一的 `action_id` / `motion_task_id` |
| 查询预设动作 | `GET /openapi/v1/animations/library` | 可按 `search`、`category`、`sub_category`、`action_ids` 过滤，查询免费 |

来源：[Rigging](https://docs.meshy.ai/en/api/rigging)、[OpenAPI](https://docs.meshy.ai/openapi.json)、[Text to Motion](https://docs.meshy.ai/en/api/text-to-motion)、[Animation](https://docs.meshy.ai/en/api/animation)、[预设库](https://docs.meshy.ai/en/api/animation-library)。

`prompt` 最多 400 字符。`duration` 必填，范围 2–10 秒，间隔 0.5 秒。`mode=prime` 默认采用较高质量模型，输出 FBX；`swift` 输出 BVH。生成结果是独立动作，需要另行套用到模型。

例如，为已经合格绑定的士兵制作行走候选，先向 `/openapi/v1/text-to-motion` 提交：

```json
{
  "prompt": "An armored soldier walks forward at a steady pace, holding a spear in the right hand, with natural alternating footfalls and restrained upper-body movement.",
  "mode": "prime",
  "duration": 4
}
```

用返回的任务 ID 查询 `GET /openapi/v1/text-to-motion/{id}`，成功后向 `/openapi/v1/animations` 提交：

```json
{
  "rig_task_id": "SUCCESSFUL_BIPED_RIG_TASK_ID",
  "motion_task_id": "SUCCESSFUL_TEXT_TO_MOTION_TASK_ID"
}
```

这是待验证的请求示例，提示词描述不构成动作质量保证。生成动作须在 3 天保留期内套用；`motion_task_id` 仅支持双足骨架。初次验证建议省略 `post_process`：该字段控制帧率、格式或骨架导出，不能修正蒙皮，且部分生成动作套用后只有 GLB。

## 四足能力与文档不一致

官方 OpenAPI 的 `RiggingRequest.animation_type` 明确包含 `quadruped`，因此不能断言原生 API 完全没有四足参数。但 Rigging 说明页仍强调标准双足人形。官方网页帮助说明四足绑定已有支持，四足动作目前只有行走；Smart Rig 的骨架尚不能使用动作库。[OpenAPI](https://docs.meshy.ai/openapi.json)、[Rigging 说明](https://docs.meshy.ai/en/api/rigging)、[网页绑定和动画帮助](https://help.meshy.ai/en/articles/16231707-how-to-create-3d-animation-with-auto-rigging)

OpenAPI 快照还没有列出 `Text to Motion`，其 `AnimationRequest` 仍把 `action_id` 设为必填；这与专门的 Text to Motion、Animation 说明页不一致。后续应分别验证新端点和四足请求的实际行为，不能只靠旧 schema 生成客户端，也不能把文档存在字段当作模型已通过实测。

你提供的[工作区页面](https://www.meshy.ai/zh/workspace?sidebar=animate)已尝试打开，但本轮浏览器读取超时，未取得具体控件；上述网页能力依据官方帮助文档，未声称读取到了账户内面板。

## 初次调查发现的实现缺口与返工方向

初次调查时，`scripts/meshy/motion_assets.py` 仅实现六个人形的自动绑定和 `action_id` 预设。随后新增的 `scripts/meshy/native_motion.py` 已补齐文字生成、`motion_task_id` 套用和独立部件绑定；`pipeline.py` 已允许 `/text-to-motion`，并下载校验独立 FBX/BVH。棋局中现有车辆及动物运行包仍来自本地局部关节；本次原生候选单独放在样板页中。

以下是依据用户反馈与实现方式提出的处理方向，具体错位根因仍需逐件检查：

| 反馈 | 处理方向 |
| --- | --- |
| 黑将武器和脚部错位；兵卒步态扭曲 | 先检查关节位置、蒙皮、武器挂点、输入朝向和肢体是否粘连；通过绑定检查后再验证原生动作 |
| 红士只有腹部蠕动 | 检查衣摆和躯干权重以及动作是否被过度限制，再试合适的预设或文字动作 |
| 红黑象步态不自然 | 分离象体与骑手，对单独象体验证 `animation_type=quadruped` 及返回的基础行走动作 |
| 马、象骑手缺少动作 | 骑手需要独立人体骨架、手部挂点及与坐骑同步的动作；未发现公开的多人/骑手与坐骑自动协同参数 |
| 红炮人物头部扭曲 | 炮手应单独绑定并检查头颈权重，再与刚性的炮身组合 |

当前公开请求参数中未发现逐关节定位、直接修正蒙皮权重、脚底锁定或武器约束的控制字段。模型输入要具备清楚的肢体结构；官方也建议对粘连、姿态和脚部问题先处理模型再绑定。[输入限制](https://docs.meshy.ai/en/api/rigging)、[绑定问题排查](https://help.meshy.ai/en/articles/16231707-how-to-create-3d-animation-with-auto-rigging)

后续实测已覆盖人物、骑手和四足输入：文字动作与双足套用成功，四足姿态估计失败。自动生成成功仍不能代表脚底接地、肢体形变、武器跟手和真实步态已经验收。

## 费用

当前官方价格：绑定 5 积分；文字动作 Prime 10、Swift 3；将动作套到模型另收 3。已有合格绑定时，一段 Prime 动作生成并应用为 13；从头绑定则为 18。独立动作可在适配前提下复用，但每次 API 套用另计费。[API 价格](https://docs.meshy.ai/en/api/pricing)

新端点继续使用既有账本、任务恢复、累计 1800 积分上限和 1200 余额下限；72 项离线测试通过。原生接口已实际调用，视觉问题仍按样板报告逐项列出，未宣称全部修复。
