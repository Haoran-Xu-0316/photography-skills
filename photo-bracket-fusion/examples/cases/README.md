# 多题材处理案例

同一画面在线性光中模拟-1、0、+1EV，提供模拟曝光比。经逐通道光度补偿，三例静态运动比例均为0；不代表真实多次拍摄HDR或所有运动场景已验证。

## 输入与复现

[动物](animal/comparison.jpg)、[城市](city/comparison.jpg)、[人物](portrait/comparison.jpg)使用本仓库专门生成的合成摄影素材。每组input目录保存实际输入，output保存程序实际结果。对照板只缩放排版，不修饰处理结果。本地测试记录不随Skill发布。

在独立Python会话中加载[reproduce.py](reproduce.py)，调用reproduce_case("animal", 新输出目录)。case_name也可为city或portrait；依赖使用本Skill的requirements.txt，输出目录不得已存在。

![三题材实际对照](comparison.jpg)

报告中的review、blocked和警告均保留；退出码为0不等于所有业务条件通过。本案例仅覆盖本页说明的输入与处理模式，不代表全部能力验收。
