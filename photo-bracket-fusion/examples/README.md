# 模拟曝光序列及风险警告

新增[动物、城市、人物案例](cases/README.md)，含输入、实际输出和复现函数。

## 目的与输入

从同一sRGB底图转到线性RGB，分别乘0.5、1、2后重新编码为sRGB，模拟-1EV、0EV、+1EV。传入0.005、0.01、0.02秒仅表示模拟曝光比例，不是真实拍摄EXIF。

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

完成配准及Mertens融合，3帧平移均为0。旧检测曾将静态曝光变化误判为13.35%高风险；改为逐通道单调光度补偿后已重新执行。本例静态风险为low，另用新增局部运动与伽马变化回归确认没有简单关闭运动告警。本例不能证明高动态范围恢复，不能代替实拍包围曝光。

![输入与实际结果](comparison.jpg)

[实际风险图](output/ghost_risk_mask.png)；[完整输出](output/)。

处理输出在2026-09-12实际生成。验证数据覆盖本例，不是所有模式的质量认证；程序中的待人工复核状态不被擅自升级。随附JSON和CSV中的文件路径按报告所在目录相对化，原始数值及警告保留。
