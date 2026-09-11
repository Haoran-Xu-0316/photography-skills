# 多题材处理案例

展示原有焦点驱动的三比例草案，其中部分画幅会切断尾部或头顶，不能直接作为安全裁切成片。新增[保护区域案例](../protected/README.md)使用硬约束避免该问题。

## 输入与复现

[动物](animal/comparison.jpg)、[城市](city/comparison.jpg)、[人物](portrait/comparison.jpg)使用本仓库专门生成的合成摄影素材。每组input目录保存实际输入，output保存程序实际结果，verification.json记录源文件哈希与执行情况。对照板只缩放排版，不修饰处理结果。

在独立Python会话中加载[reproduce.py](reproduce.py)，调用reproduce_case("animal", 新输出目录)。case_name也可为city或portrait；依赖使用本Skill的requirements.txt，输出目录不得已存在。

![三题材实际对照](comparison.jpg)

报告中的review、blocked和警告均保留；退出码为0不等于所有业务条件通过。复核范围见[仓库审计](../../../AUDIT.md)。
