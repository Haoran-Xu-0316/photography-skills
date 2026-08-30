---
name: photo-light-sculptor
description: 基于主体蒙版对单张照片进行非生成式局部加减光，通过空间性的同通道EV调整引导视线。适用于主体与背景的局部亮度分配和已有明暗层次强化；不用于全局曝光曲线、白平衡调色、镜头暗角修复、构图裁切、深度估计或生成新光源。
metadata:
  runtime: 需要Python3.10+及requirements.txt中的依赖；核心流程完全离线；最终光影验收要求执行环境能够查看主体蒙版、EV光照图和结果对照。
---

# 照片光影塑形

## 运行契约

- 核心入口是本目录的`SKILL.md`。`scripts`、`references`和`assets`路径必须相对本Skill根目录解析，不依赖特定模型、厂商工具名或提示词语法。
- 自动分析和处理需要Python3.10+和`requirements.txt`中的依赖。执行代理应将本Skill的`scripts`目录临时加入当前Python进程的模块搜索路径，再调用下述接口。
- 最终验收需要查看原图、主体蒙版、EV光照图和结果对照。无法查看图像的模型只能输出待复核结果，不能宣称视觉塑形完成。

## 定位

只改变空间性的局部亮度分布，回答“哪里应该亮、哪里应该暗、视线落在哪里”。原图只读，不改变综合色彩、物体内容和光源方向。

## 模式

- `focus`：主体轻微提亮、背景压暗，建立视觉中心。
- `depth`：沿用照片已有明暗关系，强化主体内部局部明暗纹理；这是亮度模式，不输出深度图。
- `balance`：缓和局部过亮、过暗和左右失衡，不把画面拉平。

## 工作流

1. 读取原图并分析亮度、剪切和主体候选区。
2. 用户蒙版优先；没有蒙版时使用确定性显著性蒙版，并报告置信度。
3. 低置信度时停止自动处理并要求用户提供蒙版，不把不可靠显著性结果称为主体。
4. 生成原图、蒙版、EV光照图和结果对照。
5. 输出成片、蒙版、16bit光照图、配方和验证JSON；技术阻断项写入验证结果，视觉验收前状态保持为待复核。

## 接口

```python
from photo_light_sculptor import analyze_light, sculpt_photo

analysis = analyze_light(input_path, subject_mask_path=None)
result = sculpt_photo(input_path, output_dir, mode="focus", strength=1.0)
```

## 约束

- 在场景线性RGB中对三个通道施加相同EV增益，避免色相漂移。
- 默认EV范围为负0.35至正0.25，硬上限为负0.60至正0.45。
- 不创建轮廓光、投影、眼神光和照片中不存在的照明。
- 不覆盖原图；输出已存在时失败。
- 全局曝光、曲线和颜色交给`photo-color-grade`；镜头径向暗角及其他技术缺陷交给`photo-repair`；相对深度和视差交给`photo-to-3d`。

详细方法见[references/method.md](references/method.md)。
