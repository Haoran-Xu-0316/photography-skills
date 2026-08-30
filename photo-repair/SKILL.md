---
name: photo-repair
description: 诊断并修复照片采集阶段的技术缺陷，包括高ISO噪点、镜头径向暗角、横向色差、坏点和热噪点，支持RAW与常见位图。当用户明确要求降噪、去镜头暗角、修色差、去坏点或批量技术缺陷修复时使用；不处理全局调色、局部审美加减光、构图或含义不明的一般性修片。
metadata:
  runtime: 需要Python3.10+及requirements.txt中的依赖；核心流程完全离线；最终修复验收要求执行环境能够查看100%裁切对照。
---

# 照片缺陷修复

## 运行契约

- 核心入口是本目录的`SKILL.md`。`scripts`、`references`和`assets`路径必须相对本Skill根目录解析，不依赖特定模型、厂商工具名或提示词语法。
- 自动诊断和修复需要Python3.10+和`requirements.txt`中的依赖。执行代理应将本Skill的`scripts`目录临时加入当前Python进程的模块搜索路径，再调用下述接口。
- 最终验收需要查看100%裁切预览和修复结果。无法查看像素级对照的模型只能生成诊断或待复核输出，不能宣称视觉修复完成。

## 概述

按诊断结果自动定参的照片技术修复流水线。先量化测量缺陷程度，再据此决定处理强度，避免过度处理。

处理范围仅限技术缺陷。全局调色、局部光影和构图裁切不在范围内，应在本流水线之后交给对应的专用流程。

## 工作流程

### 第一步 诊断

任何修复任务都先诊断，不要跳过直接修。诊断输出量化指标，据此判断该修什么、修多重。

```python
from photo_repair import diagnose_photos

diagnosis = diagnose_photos(input_paths)
```

输出包含亮度与色度噪声sigma、暗角边角中心比与置信度、色差边角位移、高光溢出与暗部死黑比例。把这些指标翻译成用户能理解的结论，不要直接甩数字。

### 第二步 预览调参

修复前先出预览，让用户确认力度。这一步不能省，降噪力度是主观偏好，不同题材差别很大。

```python
from photo_repair import build_repair_preview

preview = build_repair_preview(input_path, preview_directory)
```

生成中心、边缘、边角三处100%裁切的修复前后对比图。只对裁切块做耗时运算，一轮几秒。把生成的图展示给用户看。

### 第三步 修复

```python
from photo_repair import repair_photos

result = repair_photos(
    input_paths,
    output_directory,
    preset="high_iso",
)
```

输出必须写入调用方明确指定的独立目录。RAW输出16位TIFF；JPEG输出JPEG并尝试保留EXIF，复制状态写入JSON报告，失败时不得声称已保留。既有输出默认拒绝覆盖。

## 参数

默认自动定参。预设和`overrides`字典指定的参数优先级最高，自动推荐只填用户没显式指定的项。

四套预设：`high_iso`高感手持，`landscape`低感风光，`astro`星空，`wildlife`打鸟。

最常调的三个参数：

- `denoise.luma_strength` 亮度降噪，超过1.2出现塑料感，细节丰富的题材压到0.6到0.8
- `denoise.detail_recovery` 细节回补，降噪重时调高
- `vignette.strength` 暗角校正比例，0.85到0.9通常比全补自然

完整参数表见`references/parameters.md`，需要精细调参时读取。

## 暗角精确校正

单张估计暗角有原理上的局限，场景若存在旋转对称的亮度分布则无法与暗角区分。精确解是平场校准：

```python
from photo_repair import build_lens_profile

profile = build_lens_profile(
    flat_field_paths,
    profile_store_path,
    allow_update=False,
)
```

配置文件按镜头、焦段、光圈三级索引写入调用方明确指定的位置。更新已有配置必须显式设置`allow_update=True`。用户反馈暗角校正不准或不生效时，建议走这条路。详见`references/calibration.md`。

## 关键约束

处理顺序是坏点、色差、暗角、降噪、锐化，不能改。暗角校正给边角施加数倍增益会同步放大噪声，先降噪后校正边角会明显比中心脏。

亮度与色度降噪必须分开控制。色度可以给到3到5几乎不损细节，亮度超过1.2就是塑料感。用一个参数控制两者是常见的翻车原因。

降噪强度由实测噪声驱动，不由ISO决定。同样ISO 6400，正常曝光和欠曝两档后期提亮的片子噪声差一倍以上。

原图始终只读。输出路径不得与输入相同，既有预览、修复图或报告不得覆盖；批量输入产生同名输出时必须先拆分目录或调整文件名。

## 已知限制

紫边即纵向色差成因是离焦，不处理。镜头畸变未实现。高光溢出的像素信息已丢失，只报告不恢复。JPEG因机内已降噪并压缩，可操作空间比RAW小一个档次。

## 参考文档

按需读取，不要预先全部加载。

- `references/parameters.md` 全部参数含义、取值范围、预设定义
- `references/algorithms.md` 各模块算法原理、设计取舍、实测精度
- `references/calibration.md` 平场校准的拍摄要求与操作流程
