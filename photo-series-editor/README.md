# photo-series-editor

## 功能定位

为已经完成筛选的多张照片建立顺序、节奏、开场、转场和收束。它不判废片、不调色，也不移动或重命名原文件。

## 三种策略

- `chronology`：严格按拍摄时间排列
- `visual-rhythm`：根据色彩、明暗、方向和纹理建立机械初稿
- `manual`：按人工确认顺序生成最终清单

## 输入与输出

输入为已选照片列表。输出包括编号联系表、序列JSON、CSV和非破坏性文件清单。

## 使用示例

初稿和人工确认示例见[`examples/basic_usage.py`](examples/basic_usage.py)：

```python
draft = run_example(selected_paths, "series-draft")
reviewed = finalize_reviewed_example(ordered_paths, "series-final")
```

## 图片示例

[输入、参数、实际输出及验证边界](examples/README.md)。随附[可复现调用](examples/reproduce.py)，不是只有调用占位符。

![输入与实际处理结果](examples/comparison.jpg)

## 验收重点

- 自动排序只能是`draft-review-required`
- 必须查看完整编号联系表
- 只有人工确认顺序才能使用`manual`并记录已复核状态
- 近似照片只提示，不自动删除

完整叙事规则和状态契约见[`SKILL.md`](SKILL.md)。
