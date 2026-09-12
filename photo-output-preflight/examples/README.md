# 网页副本与GPS清理

新增[动物、城市、人物案例](cases/README.md)，含输入、实际输出和复现函数。

## 目的与输入

1536×1024生成图加入虚构作者字段及经纬度均为0的测试GPS字段，先做web检查，再生成长边960像素副本并移除GPS。虚构坐标不代表摄影地点。

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

副本实测960×640；源文件含测试GPS，输出不含GPS，源文件哈希保持不变。已对照画面。本例不覆盖印刷ICC、CMYK、坏文件或全部元数据隐私风险。

![输入与实际结果](comparison.jpg)

[交付报告](output/copies/web_export_report.json)；[完整输出](output/)。

处理输出在2026-09-12实际生成。验证数据覆盖本例，不是所有模式的质量认证；程序中的待人工复核状态不被擅自升级。随附JSON和CSV中的文件路径按报告所在目录相对化，原始数值及警告保留。
