# photo-output-preflight

## 功能定位

检查照片文件是否适合网页、印刷或归档，重点覆盖尺寸、格式、有效PPI、ICC、透明通道、GPS元数据和文件完整性。它不修改摄影内容。

## 三种目标

- `web`：网页尺寸、体积、sRGB兼容、透明度和GPS风险
- `print`：成品尺寸、有效PPI、位深和ICC完整性
- `archive`：哈希、格式、尺寸、元数据和文件名冲突

## 输入与输出

输入为照片列表和目标渠道。输出结构化质检报告；网页模式还可以生成机械性缩放和元数据处理副本。

## 使用示例

网页交付示例见[`examples/basic_usage.py`](examples/basic_usage.py)：

```python
result = run_example(input_paths, "web-delivery")
```

## 图片示例

输入：[`sample_scene.png`](../example-assets/sample_scene.png)

![网页副本示例](examples/output/web-copy.png)

## 验收重点

- 导出成功不代表视觉合格
- 透明图片必须保留Alpha并使用PNG
- 没有ICC时只报告缺失，不猜测源色彩空间
- GPS删除只作用于副本

完整渠道标准和执行规范见[`SKILL.md`](SKILL.md)。
