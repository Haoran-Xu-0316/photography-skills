# photo-bracket-fusion

## 功能定位

融合同一机位、同一视场的真实包围曝光序列，并报告配准和运动鬼影风险。它不会把单张照片套HDR滤镜，也不生成未被任何帧记录的细节。

## 适用场景

- 静态风光和室内空间的包围曝光
- 需要检查树叶、行人、水面等运动鬼影的多曝光序列
- 需要保留可复现配准与融合报告的摄影流程

## 输入与输出

输入至少两张不同曝光照片，可显式提供秒为单位的曝光时间。输出16bit TIFF、JPEG预览、风险蒙版、配准联系表和JSON报告。

## 使用示例

带输入阻断检查的示例见[`examples/basic_usage.py`](examples/basic_usage.py)：

```python
result = run_example(input_paths, "fusion-review", [0.25, 0.5, 1.0])
```

## 图片示例

[输入、参数、实际输出及验证边界](examples/README.md)。随附[可复现调用](examples/reproduce.py)，不是只有调用占位符。

![输入与实际处理结果](examples/comparison.jpg)

## 验收重点

- 曝光跨度、尺寸、同视点关系和重复内容必须先通过检查
- 只进行平移配准，不用自由形变掩盖视差
- 必须查看鬼影风险蒙版和配准联系表
- 结果是显示参考型曝光融合图，不是物理辐射图

完整融合契约和阈值见[`SKILL.md`](SKILL.md)。
