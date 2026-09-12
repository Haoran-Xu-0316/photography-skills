# 已知重叠的拼接回归

新增[动物、城市、人物案例](cases/README.md)，含输入、实际输出和复现函数。

## 目的与输入

从1152×768底图切出两个768×768视图，水平偏移384像素，重叠50%。使用planar模型。两张只是同图裁片，不是相机转动产生的独立视角。

工作台底图是2026-09-12专为本仓库生成的合成摄影测试素材，不是相机实拍。输入随Skill保存在[input/](input/)，调用不依赖仓库外的本机文件。
## 可复现调用

在本Skill根目录的Python会话中执行；依赖见上一级requirements.txt。输出目录必须尚不存在。

```python
import runpy

example = runpy.run_path("examples/reproduce.py")
result = example["reproduce_example"]("example-review")
```

[reproduce.py](reproduce.py)是随附图片的完整参数调用；[basic_usage.py](basic_usage.py)保留通用接口演示。两者调用原有处理实现，没有用生成图充当处理后的结果。多帧模拟仅限受控测试，实际使用仍须遵守Skill的真实输入要求。

## 实际输出与复核

SIFT匹配经RANSAC保留1208对内点，估计重叠约49.995%。输出恢复主要画面，已检查中央接缝，没有明显断裂。此例不覆盖视差、移动物体、圆柱投影或真实多机位。

![输入与实际结果](comparison.jpg)

[拼接结果](output/panorama_preview.jpg)；[完整输出](output/)。

处理输出在2026-09-12实际生成。验证数据覆盖本例，不是所有模式的质量认证；程序中的待人工复核状态不被擅自升级。随附JSON和CSV中的文件路径按报告所在目录相对化，原始数值及警告保留。
