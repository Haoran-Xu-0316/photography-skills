# photo-to-3d

## 功能定位

把单张照片转换为相对深度图、2.5D视差作品、循环动画和正面浅浮雕网格。它不声称恢复真实尺寸、隐藏表面或完整360度几何。

## 四种输出

- `depth`：16bit相对深度图和检查图
- `parallax`：交互HTML与循环GIF
- `relief`：带纹理OBJ、MTL和纹理图
- `bundle`：同时生成全部结果

## 输入与输出

输入为单张照片，可选用户深度图。用户深度图路径完全离线；自动估深默认只读本地模型缓存，任何下载都需要明确许可。

## 使用示例

使用用户深度图的离线示例见[`examples/basic_usage.py`](examples/basic_usage.py)：

```python
result = run_example("photo.jpg", "parallax-output", "depth.png")
```

## 图片示例

[输入、参数、实际输出及验证边界](examples/README.md)。随附[可复现调用](examples/reproduce.py)，不是只有调用占位符。

![输入与实际处理结果](examples/comparison.jpg)

## 验收重点

- 深度图必须与照片保持逐像素对应和同一宽高比
- 白色默认表示近，黑色表示远
- 人脸、文字、栏杆、树叶和透明体需要重点检查
- OBJ只是正面高度场，不能描述为完整3D扫描

完整模式说明和单图限制见[`SKILL.md`](SKILL.md)。
