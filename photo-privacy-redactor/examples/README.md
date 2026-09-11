# 显式区域的实心遮挡

新增[动物、城市、人物案例](cases/README.md)，含输入、实际输出和复现函数。

## 目的与输入

底图左下角叠加虚构联系标签，内容使用保留的无效域名demo@example.invalid。明确遮挡像素矩形left=70、top=560、right=510、bottom=700。

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

61600个遮挡像素全部为黑色，区域外像素逐点不变；已查看标签完整覆盖。当前环境自动人脸候选检测不可用，且manual_review_confirmed仍为false，不可把矩形测试当作自动隐私扫描或发布批准。

![输入与实际结果](comparison.jpg)

[无损遮挡结果](output/fictional-label_redacted.png)；[完整输出](output/)；[验证数据与输入哈希](verification.json)。

处理输出在2026-09-12实际生成。验证数据覆盖本例，不是所有模式的质量认证；程序中的待人工复核状态不被擅自升级。随附JSON和CSV中的文件路径按报告所在目录相对化，原始数值及警告保留。
