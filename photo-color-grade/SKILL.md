---
name: photo-color-grade
description: 对照片进行非生成式全局影调与颜色处理，包括技术校色、创意调色、参考图色彩关系匹配和系列色彩统一。适用于整体曝光、白平衡、曲线、综合色偏、饱和度以及高光阴影色彩关系；不用于空间蒙版加减光、降噪修复、构图裁切、人物美化、生成式改图或抽象海报。
metadata:
  runtime: 需要Python3.10+及requirements.txt中的依赖；核心流程完全离线；最终调色验收要求执行环境能够查看原图、预览对照板和成片。
---

# 照片调色

## 运行契约

- 核心入口是本目录的`SKILL.md`。`scripts`、`references`和`assets`路径必须相对本Skill根目录解析，不依赖特定模型、厂商工具名或提示词语法。
- 自动分析和调色需要Python3.10+和`requirements.txt`中的依赖。执行代理应将本Skill的`scripts`目录临时加入当前Python进程的模块搜索路径，再调用下述接口。
- 最终验收需要查看原图、预览对照板和调色结果。无法查看图像的模型只能输出配方或待复核结果，不能宣称视觉调色完成。

## 目标

建立可解释、可复现、非破坏性的照片调色流程。结果应当看得出画面更完整、更统一，但看不出机械套用预设。

调色只改变全局或颜色分区的影调与色彩关系，不设计“画面哪里应亮或暗”的空间性局部光照。原始文件始终只读，不改变尺寸、方向、人物身份、物体结构和画面内容，不使用图像生成工具重绘照片。

## 模式选择

- `correct`：技术校色。修正无意的曝光偏差、白平衡偏差、综合色偏和不合理的动态范围，不主动建立风格。
- `calibrate_photo`：人工校准。已知曝光偏差、通道增益或经确认的中性采样区时，使用显式参数校准；不依赖自动中性色猜测。
- `look`：创意调色。在技术底片之上建立明确的明暗、色温、饱和度和高光阴影关系。
- `match`：参考图匹配。迁移参考图的影调和色彩关系，不复制参考图的主体、局部亮度或逐像素RGB分布。
- `series`：系列统一。以用户确认的锚片为基准，在同一光线组内统一照片，同时保留时间和现场光线变化。

用户没有给出创意方向时，只执行`correct`或先生成预览，不擅自选择风格。批量处理前必须先用一张代表性照片生成锚片预览并取得确认。

## 工作流

1. 读取原图、EXIF、位深和ICC信息，确认格式与依赖是否支持。
2. 调用`scripts.photo_color_grade.analyze_photo`诊断亮度、剪切、综合色偏、饱和度和潜在肤色区域。没有可靠中性色时，只报告疑似色偏，不强行中和。
3. 技术缺陷先交给`photo-repair`。完整照片链路通常是筛片、技术修复、全局调色、局部光影、构图裁切和交付质检；只执行当前任务实际需要的环节。
4. 调用`scripts.photo_color_grade.build_preview`输出原图、技术校色和目标强度70%、100%、130%的对照板。
5. 用户确认方向后，调用`scripts.photo_color_grade.grade_photo`。系列照片调用`grade_series`，锚片必须是用户确认版本对应的原片。
6. 检查验证报告。阻断项不通过时不得把结果称为完成；只允许针对失败原因调整一次参数后重做，不无限重试。
7. 交付调色成片、预览对照板、配方JSON和验证JSON。原图不得覆盖或移动。

## 程序化接口

将本Skill的`scripts`目录加入当前Python进程的模块搜索路径后导入接口。本Skill不提供面向用户的命令行工具：

```python
from photo_color_grade import analyze_photo, build_preview, grade_photo, grade_series, calibrate_photo

analysis = analyze_photo(input_path)
preview = build_preview(input_path, output_dir, mode="look", look="natural-clean")
result = grade_photo(input_path, output_dir, mode="correct")
calibrated = calibrate_photo(input_path, calibration_dir, exposure_stops=0.5)
series = grade_series(input_paths, output_dir, anchor_path, look="warm-documentary")
```

实际模块位于`scripts/photo_color_grade.py`。执行代理负责在当前Python进程中完成临时路径配置，用户无需输入命令。

## 关键约束

- 技术校色和创意调色必须分层记录。创意参数不能伪装成技术修复。
- 自动白平衡只在检测到足够可靠的低饱和中间调时启用，并限制最大通道增益。
- 不把所有肤色拉到一个固定目标。肤色蒙版只用于限制相对漂移和避免局部断层。
- 不把日落、舞台灯、霓虹和室内暖光错误中和为白光。
- 不使用全局直方图完全匹配。参考匹配只迁移关系，并设置强度和变化上限。
- 不新增明显高光溢出、暗部死黑、色阶断层、光晕和越界颜色。
- 任何输出路径与输入路径相同都必须失败。已存在输出默认不覆盖。
- RAW缺少`rawpy`时必须明确报告依赖缺失，不得把内嵌JPEG预览称为RAW调色结果。
- JPEG、PNG和TIFF可使用内置确定性引擎。专业RAW、XMP和完整显示变换按需读取色彩管理规范。

## 按需读取

- 执行`correct`或人工校准时读取[references/correction.md](references/correction.md)。
- 执行`look`时读取[references/creative-grading.md](references/creative-grading.md)。
- 执行`match`或`series`时读取[references/reference-matching.md](references/reference-matching.md)。
- 涉及RAW、16bit TIFF、ICC、网页或印刷输出时读取[references/color-management.md](references/color-management.md)。

## 质量标准

- 技术校色：白色与灰色无无意色偏，高光有过渡，暗部有密度，肤色不脏，现场光线意图得到保留。
- 创意调色：主色温、强调色和高光阴影关系明确，主体优先，色彩克制，不出现预设堆叠感。
- 系列统一：同一光线组连续一致，不同时间和场景仍保留合理差异。
- 工程交付：尺寸不变、原图只读、配方可复现、验证结果可追溯。
