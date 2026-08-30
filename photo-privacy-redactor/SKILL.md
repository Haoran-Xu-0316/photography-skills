---
name: photo-privacy-redactor
description: 对照片画面中由用户矩形、用户蒙版或已确认人脸候选指定的敏感区域进行不可逆遮挡，并输出遮挡副本、二值蒙版、候选预览和漏检复核清单。适用于公开分享前的画面内容脱敏；自动检测只提示人脸候选，不自动确认，也不承诺识别车牌、屏幕、票据或全部敏感内容。本skill不处理GPS、EXIF及其他元数据隐私。
metadata:
  runtime: 需要Python3.10+及requirements.txt中的依赖；核心流程完全离线；最终遮挡状态要求执行环境能够查看原图和预览并完成人工漏检复核。
---

# 照片画面隐私遮挡

## 运行契约

- 核心入口是本目录的`SKILL.md`。`scripts`、`references`和`assets`路径必须相对本Skill根目录解析，不依赖特定模型、厂商工具名或提示词语法。
- 自动候选检测和遮挡输出需要Python3.10+和`requirements.txt`中的依赖。执行代理应将本Skill的`scripts`目录临时加入当前Python进程的模块搜索路径，再调用下述接口。
- 最终状态依赖原始分辨率的人工漏检复核。无法查看原图和预览的模型只能输出候选与待复核副本，不能把状态升级为`content-redaction-reviewed`。

## 定位

只处理照片像素中的已确认敏感区域，回答“哪些可见内容需要被实心遮挡”。原图只读，自动人脸检测只生成候选框；没有用户确认时不得把候选写入最终遮挡蒙版。

GPS、拍摄地点、相机信息和其他EXIF风险由`photo-output-preflight`检查，本skill不检查、不删除，也不声称处理过元数据隐私。

## 两阶段工作流

1. 使用`detect_face_candidates`生成自动人脸候选。候选仅供复核，可能误报或漏报。
2. 用户矩形和用户蒙版直接进入遮挡区域，优先级最高。
3. 对每个人脸候选记录`redact`或`reject`决定。未决定的候选保持`pending`，不得自动遮挡。
4. 使用`redact_photo`输出无损PNG实心遮挡副本、二值蒙版、带标记预览和复核JSON。输入带透明通道时先合成到不透明白底，避免透明像素中的隐藏内容在导出时意外显现。
5. 执行代理必须查看预览，并按原始分辨率复核侧脸、小脸、遮挡脸和画面边缘。只有用户确认已完成漏检复核后，才能把状态记录为`content-redaction-reviewed`。

## 程序化接口

```python
from photo_privacy_redactor import detect_face_candidates, redact_photo

candidates = detect_face_candidates(input_path)
result = redact_photo(
    input_path,
    output_dir,
    rectangles=[{"left": 0.10, "top": 0.20, "right": 0.35, "bottom": 0.55, "unit": "normalized"}],
    mask_paths=[mask_path],
    candidate_decisions={"face-001": "redact", "face-002": "reject"},
    manual_review_confirmed=False,
)
```

坐标、候选决定和状态定义见[references/review-policy.md](references/review-policy.md)。

## 不可突破的边界

- 遮挡方式固定为完全不透明的实心填充；不使用模糊、马赛克、半透明块或可逆编辑层。
- 遮挡副本固定输出为无损PNG，不沿用JPEG等有损格式，避免压缩在遮挡边缘重新混入相邻像素。
- 自动能力仅检测正面人脸候选。不声称自动识别车牌、屏幕、票据、住址、证件、二维码或文字。
- 未解决自动候选时状态必须为`needs-candidate-review`。
- 未确认漏检复核时状态最多为`needs-manual-review`，不能称为完成或绝对安全。
- 即使状态为`content-redaction-reviewed`，也只表示指定画面区域及本次人工复核已经处理，不代表不存在全部隐私风险。
- 原图不覆盖、不移动、不删除；任何输出文件已存在时失败。
- 输出副本除将方向标签规范化为1和将透明通道合成到白底外，保留源EXIF和ICC；元数据隐私必须另行检查。
