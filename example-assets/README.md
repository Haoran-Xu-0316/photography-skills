# 图片示例资源

新增[赤狐](diverse/animal.png)、[运河城市](diverse/city.png)与[虚构成人肖像](diverse/portrait.png)，各1536×1024。实际生成提示分别保存在diverse/animal-prompt.txt、city-prompt.txt和portrait-prompt.txt。这些不是实拍、真实地理记录或真人肖像。

`workbench-generated.png`是2026-09-12专为本仓库生成的1536×1024合成摄影测试底图，内容为陶器工作台、窗户、植物和布料。它不是相机实拍，也不证明真实传感器噪声、镜头焦点或曝光信息。

完整生成规格见[prompt.txt](prompt.txt)。本轮使用已有生图能力，接口没有暴露模型版本选择，因此不标为已指定某一模型版本。保存提示可复现方向，不保证逐像素重现。

14个Python处理示例在各自examples/input中保留完整输入，包括受控噪声、偏色、倾斜、遮挡标签、模拟曝光序列、互补模糊序列及手工蒙版。示例参数、真值边界和局限见各自examples/README.md，不需要依赖本目录才能独立运行。

旧程序绘制的sample_scene.png及其旧结果已移出工作目录并保留恢复备份，不再用它们冒充摄影实测。
