# 动作修整与后续方案

2026-09-06。承接用户“继续修整，想想还有什么方案”的反馈，本轮采用已有 Meshy 动作加本地绑定、接触和循环修正，没有新增 API 扣费。项目累计仍为 **1395/1800**，剩余项目额度 **405**。

入口：[动作修整样板](http://127.0.0.1:4175/native-motion-gallery.html?asset=horse_red&clip=idle)。页面支持“本轮修整 / 上一轮样板”切换、暂停、慢放、四个细节视角和 GLB 下载。这里是候选检视，不代表全部攻击、受击和退场动作已经通过美术验收；棋局资源清单保持原版本。

## 本轮修整

| 范围 | 修改及原因 |
| --- | --- |
| 红黑马、炮手、象背人物 | 修复原生骨架装配时的朝向丢失。新建的零长度编辑骨骼不能可靠保留旋转，现先设置有效方向，再复制原生坐标轴。 |
| 红黑马骑手 | 给持枪手和左手分别设置落点，使用两段肢体求解约束肩、肘、腕；保留原生头部与上身动作。 |
| 黑将 | 将旗枪作为独立刚性部件；局部弯曲原始手指表面并用手臂约束拟合握持点。披风根据位置与粗糙度贴图分离权重，降低对膝、踝动作的错误跟随。 |
| 黑卒 | 从原高模补回上传代理裁切掉的鞋面；修正“小腿顶点跟随大腿”的错误权重，平滑脚踝，处理内侧衣摆。 |
| 红兵、黑卒、黑将、红仕 | 行进从实际腿部姿态寻找完整周期，循环首尾一致；对闭合后的脚底高度再次校正。红仕保留完整衣袍和原生观察动作。 |
| 红黑象 | 新建四腿、脚掌、头、鼻、尾骨骼；分支撑与抬脚阶段设置落脚轨迹，保持背架刚性，保留弓手原生动作。用到各条腿的距离分配蒙皮，减少跨腿衣甲被拉开；尾巴独立控制。 |

象的行进是本地制作的四足动画。此前三次四足 API 输入仍未成功，本轮没有把旧的局部摆动或新作的四足步态标为 API 生成。

## 验证口径

检查真正导出的 2K GLB，而非仅检查 Blender 中的骨骼目标：包括四足支撑阶段的脚底表面高度、固定底座顶点漂移、循环首尾的顶点差以及局部边长拉伸。浏览器检查动作加载、图像变化、版本对照和控制台错误。

技术指标不是自然度验收。黑卒的内侧衣摆、黑将的披风边缘和近景手指仍值得继续处理；象的独立落脚已建立，但步幅、重心和背上人物的协调仍需要按最终镜头调整。当前检视只开放 14 个待机/行进片段，下载包中的其他动作沿用对应版本的基础动作，尚未全部复核。

实际版本、哈希和本轮验证摘要见 [refinement/summary.json](asset-reports/native-motion/refinement/summary.json)。逐项表面检查在同目录 `*-contacts.json`；网页证据在 [browser](asset-reports/native-motion/browser/)。

原始静态高模、纹理、API 下载和上一轮候选保留。新版本 Blender 文件保存完整运行材质，网页导出为约 2 万面、2K WebP 纹理的 GLB。

## 还有哪些方案

| 方案 | 适合处理的问题 | 判断 |
| --- | --- | --- |
| 原生动作 + 本地接触约束 | 手跟武器、骑手坐姿、脚底接地、循环接缝 | 本轮已经采用。可继续复用已有生成结果，适合当前棋子。 |
| 制作干净的低面数动画网格，再转移原图与权重 | 衣摆粘腿、披风连接错误、薄片和关节拓扑不适合弯曲 | 作为进一步提升质量的优先方向。需要真正整理衣甲与身体的连接关系，单纯增加生成次数无法替代这一步。 |
| 使用标准四足控制骨架，再重定向或制作步态 | 马、象的步态、支撑和重心 | 可建立更方便手工调整的长期制作工具。Rigify 提供基础四足和马的预设骨架，但仍需按原模型摆放骨骼并处理蒙皮。 |
| Meshy 网页四足面板 | 验证不同于本次 API 输入的自动绑定路径 | 官方网页工具支持四足；仍需要实际成功结果才能评价。现有 API 三次失败不能证明网页路径必然失败，也不能保证改走网页就能得到自然动作。 |

这些是结合现有资产问题作出的制作判断。Blender 的 IK 用目标位置驱动骨链，Data Transfer 可在不同网格间传递 UV 与顶点组；Rigify 提供预设骨架，Meshy 官方另有网页四足绑定流程。[IK 官方说明](https://docs.blender.org/manual/en/4.4/animation/constraints/tracking/ik_solver.html)、[Data Transfer 官方说明](https://docs.blender.org/manual/en/4.3/modeling/modifiers/modify/data_transfer.html)、[Rigify 官方说明](https://docs.blender.org/manual/en/latest/addons/rigging/rigify/basics.html?highlight=pose+mode)、[Meshy 网页绑定](https://docs.meshy.ai/en/webapp/guides/3d-model/rigging)。

## 复现入口

- `blender/build_native_humanoid.py`：原生人物蒙皮、装备与循环修正。
- `blender/build_native_composite.py`：按正确坐标轴装配原生骑手。
- `blender/refine_native_composite.py`：骑手手部约束和本地四足步态。
- `blender/refine_general_grip.py`：黑将握持拟合。
- `blender/audit_native_contacts.py`：检查导出后的实际表面。
- `scripts/stage_native_motion_samples.py`：发布明确版本的检视资源与上一轮对照。
- `scripts/check_native_motion_gallery.mjs`：验证所有开放片段及版本切换。

生成脚本要求新的版本号，不覆盖已有版本。制作步骤和源文件哈希写入各版本 `runtime.json`。本轮未改变游戏的 `public/assets/motion-manifest.json`。
