# photo-composition-crop

## 功能定位

根据显著性、边缘密度、目标比例和用户焦点生成可复现的裁切方案。它只决定保留范围，不调色、不修图，也不生成画外内容。

## 三种模式

- `single`：为一个比例提供主方案和备选
- `set`：同时生成多个常用比例
- `safe-area`：只输出构图框和安全区，不生成裁切副本

## 输入与输出

输入为单张照片，可选0至1归一化焦点坐标。输出包括坐标JSON、构图叠加图和非覆盖裁切副本。

## 使用示例

多比例裁切示例见[`examples/basic_usage.py`](examples/basic_usage.py)：

```python
result = run_example("source.jpg", "crop-review", focus_point=(0.55, 0.40))
```

## 验收重点

- 必须查看叠加图和实际裁切结果
- 人物照片重点检查头顶、下巴和肢体边界
- 自动视觉中心置信度较低时需要人工指定焦点
- 不允许放大或生成式补边

完整评分逻辑和执行边界见[`SKILL.md`](SKILL.md)。

