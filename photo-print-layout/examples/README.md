# A4四格印刷拼版

新增[动物、城市、人物案例](cases/README.md)，含输入、实际输出和复现函数。

## 目的与输入

使用生成工作台、CC0庭园照片及各自的正方形取景，共4张输入。A4、2×2网格、contain、300dpi、3mm出血、左侧8mm装订安全区，最低有效PPI为240。

工作台底图是2026-09-12专为本仓库生成的合成摄影测试素材，不是相机实拍。输入随Skill保存在[input/](input/)，调用不依赖仓库外的本机文件。
庭园摄影作者XxTechnicianxX，作品[Shofu-en Japanese Garden Pond](https://commons.wikimedia.org/wiki/File:Shofu-en_Japanese_Garden_Pond.jpg)，[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)。这里的庭园输入为缩小及裁切副本，不是原始文件。

## 可复现调用

在本Skill根目录的Python会话中执行；依赖见上一级requirements.txt。输出目录必须尚不存在。

```python
import runpy

example = runpy.run_path("examples/reproduce.py")
result = example["reproduce_example"]("example-review")
```

[reproduce.py](reproduce.py)是随附图片的完整参数调用；[basic_usage.py](basic_usage.py)保留通用接口演示。两者调用原有处理实现，没有用生成图充当处理后的结果。多帧模拟仅限受控测试，实际使用仍须遵守Skill的真实输入要求。

## 实际输出与复核

实际生成1页PDF、页面PNG和清单，并用独立PDF渲染器栅格化后目视检查。四格均放置图像，保留原比例，包含裁切标记。输出为未标记RGB，存在缺少ICC的警告，不属于印厂CMYK或色彩打样验收。庭园来源见下方许可。

![输入与实际结果](comparison.jpg)

[实际PDF](output/photo_print_layout.pdf)；[完整输出](output/)；[验证数据与输入哈希](verification.json)。

处理输出在2026-09-12实际生成。验证数据覆盖本例，不是所有模式的质量认证；程序中的待人工复核状态不被擅自升级。随附JSON和CSV中的文件路径按报告所在目录相对化，原始数值及警告保留。
