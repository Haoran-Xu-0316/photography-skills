---
name: photo-focus-stacker
description: 对同一场景、同一视点、不同焦平面的多张照片进行刚性配准、局部清晰来源选择、边缘融合，并报告主体运动与对焦呼吸风险。适用于微距、静物和风光景深合成；不用于筛片、单张去模糊、包围曝光融合、全景拼接或生成所有输入帧都没有记录的细节。
metadata:
  runtime: 需要Python3.10+及requirements.txt中的依赖；核心流程完全离线；最终堆栈验收要求执行环境能够查看来源地图、置信度图、风险蒙版和合成结果。
---

# 照片焦点堆栈

## 运行契约

- 核心入口是本目录的`SKILL.md`。`scripts`、`references`和`assets`路径必须相对本Skill根目录解析，不依赖特定模型、厂商工具名或提示词语法。
- 自动分析和合成需要Python3.10+和`requirements.txt`中的依赖。执行代理应将本Skill的`scripts`目录临时加入当前Python进程的模块搜索路径，再调用下述接口。
- 最终验收需要查看来源地图、低置信度区域、风险蒙版和合成结果。无法查看图像的模型只能输出待复核结果，不能宣称焦点堆栈通过。

## 定位

只处理同一场景、同一视点、焦点位置依次变化的一组真实照片，回答“这些帧能否进行景深合成、各区域应从哪一帧取清晰信息、哪里存在运动或对焦呼吸风险”。

本Skill不评星、不淘汰照片，也不判断哪张作品更好。它把多张不同焦平面组合成一张结果；单张照片的失焦修复不属于本Skill。

## 工作流

1. 锁定至少两张不同原始文件，记录尺寸与SHA-256。
2. 调用`scripts.photo_focus_stacker.analyze_focus_stack`检查尺寸、重复内容、刚性配准、焦平面多样性、曝光差异、运动与呼吸效应风险。
3. 阻断项存在时停止，不通过自由形变、生成式补全或强锐化掩盖输入问题。
4. 调用`scripts.photo_focus_stacker.stack_focus`计算局部清晰度来源、焦点地图与置信度，并只在实际输入帧之间进行边缘融合。
5. 查看来源地图、低置信度区域和运动/呼吸风险蒙版。状态为`review_required`时不能只凭合成预览宣称成功。
6. 交付16bit TIFF、JPEG预览、来源地图、置信度图、风险蒙版、配准联系表与JSON报告。

## 程序化接口

不提供面向用户的命令行入口。把`scripts`目录加入Python路径后调用：

```python
from photo_focus_stacker import analyze_focus_stack, stack_focus

analysis = analyze_focus_stack(input_paths)
result = stack_focus(
    input_paths,
    output_dir,
    reference_index=None,
    blend_radius=7,
)
```

`reference_index=None`时使用输入序列的中间帧作为配准参考，不代表它在审美或技术上优于其他帧。`blend_radius`只控制真实来源帧之间的边缘过渡，不会生成新纹理。

## 核心约束

- 输入必须是同一视点、构图基本一致、焦平面不同的真实多帧照片。
- 原图只读；输出路径不得与输入相同；已存在输出不得覆盖。
- 只允许旋转和平移的刚性配准。尺度变化只作为对焦呼吸风险报告，不用自由形变强行消除。
- 局部清晰度只决定从哪张真实帧取样。任何输入帧都没有记录的纹理、遮挡后内容和裁切外内容不得补造。
- 主体运动、风吹叶片、水面变化、严重呼吸效应和低置信度接缝必须在报告中显式标记。
- 不使用整体锐度为照片评级或淘汰帧。筛片交给`photo-cull`。
- 不从单张照片恢复失焦内容。单张技术缺陷修复交给`photo-repair`。
- 不利用曝光差异扩展动态范围。曝光包围序列交给`photo-bracket-fusion`。
- 不做创意调色、局部加减光、审美裁切或全景拼接。

算法、阈值、输出解释与失败边界见[references/stack-contract.md](references/stack-contract.md)。
