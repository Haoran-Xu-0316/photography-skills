# photo-cull

## 功能定位

对一批照片进行客观技术筛选，识别明显失焦、相机抖动、曝光溢出和连拍重复。它不判断构图、表情、氛围或作品价值。

## 适用场景

- 活动、旅行、野生动物和人像拍摄后的第一轮筛片
- 从连拍组中找出技术质量最好的候选
- 为Lightroom、Capture One或Bridge准备可复核的XMP星级

不适用于组照排序、调色、修复和审美选片。

## 输入与输出

输入为照片目录。分析阶段输出CSV、JSON和废片联系表，不修改原图。只有人工看过报告后，才能另行调用XMP写入接口。

## 使用示例

安全示例见[`examples/basic_usage.py`](examples/basic_usage.py)。示例只生成分析报告，不写XMP：

```python
result = run_example("photos", "review/cull-report")
```

## 图片示例

[输入、参数、实际输出及验证边界](examples/README.md)。随附[可复现调用](examples/reproduce.py)，不是只有调用占位符。

![输入与实际处理结果](examples/comparison.jpg)

## 验收重点

- 必须查看废片联系表，防止误杀
- `review`照片不能自动当作废片
- 写入XMP前必须取得明确确认
- 原图不得移动、删除或覆盖

完整执行规范、阈值和预设见[`SKILL.md`](SKILL.md)。
