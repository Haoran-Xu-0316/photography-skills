# photo-panorama-stitcher

## 功能定位

将两张及以上具有真实重叠、共同扩展视场的照片拼接为全景图。它不进行生成式扩图，也不处理完全相同视场的曝光包围。

## 两种投影

- `planar`：普通窄幅、平面主体和以相机旋转为主的场景
- `cylindrical`：宽视角旋转拍摄，可使用已知像素焦距

## 输入与输出

输入照片必须按空间相邻顺序排列。输出TIFF、JPEG预览、有效区域蒙版、接缝图、联系表和JSON报告。

## 使用示例

平面投影和阻断检查示例见[`examples/basic_usage.py`](examples/basic_usage.py)：

```python
result = run_example(ordered_paths, "panorama-review")
```

## 验收重点

- 相邻照片必须同时存在可靠重叠和新增视场
- 明显视差、移动主体和近距离多平面场景需要人工复核
- 禁止生成填充、镜像边缘和无来源像素外推
- 必须查看重影、弯曲直线和接缝亮度跳变

完整拼接契约和失败阈值见[`SKILL.md`](SKILL.md)。

