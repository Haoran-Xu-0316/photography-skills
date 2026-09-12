---
name: photo-bracket-fusion
description: 对同一机位拍摄的多张包围曝光照片进行有效性检查、平移配准、曝光融合、运动与鬼影风险检测，并输出可复现报告。适用于真实曝光包围序列；不用于单张HDR风格、局部加减光、创意调色、全景拼接或虚构照片中不存在的动态范围。
metadata:
  runtime: 需要Python3.10+及requirements.txt中的依赖；核心流程完全离线；最终融合验收要求执行环境能够查看配准联系表、鬼影风险蒙版和融合结果。
---

# 照片包围曝光融合

## 运行契约

- 核心入口是本目录的`SKILL.md`。`scripts`、`references`和`assets`路径必须相对本Skill根目录解析，不依赖特定模型、厂商工具名或提示词语法。
- 自动分析和融合需要Python3.10+和`requirements.txt`中的依赖。执行代理应将本Skill的`scripts`目录临时加入当前Python进程的模块搜索路径，再调用下述接口。
- 最终验收需要查看配准联系表、鬼影风险蒙版和融合结果。无法查看图像的模型只能输出待复核结果，不能宣称融合通过。

## 定位

只处理同一场景、同一机位、多次曝光形成的一组照片，回答“这些帧是否属于可融合的曝光包围、如何对齐、哪里存在运动鬼影、融合结果如何复现”。

本Skill默认生成显示参考型曝光融合图，不把它称为场景线性HDR、辐射亮度图或新增动态范围。没有真实多帧输入时停止，不允许复制单张照片、套HDR滤镜或生成不存在的高光与暗部细节。

## 工作流

1. 锁定至少两张不同的原始文件，记录尺寸、SHA-256和曝光时间来源。
2. 调用`scripts.photo_bracket_fusion.analyze_bracket`检查尺寸一致性、重复内容、曝光跨度、同视点相似度和所需平移量。
3. 阻断项存在时停止，不通过强制融合掩盖输入问题。
4. 调用`scripts.photo_bracket_fusion.fuse_bracket`执行MTB平移配准和Mertens曝光融合。
5. 检测对齐后的时间差异，生成鬼影风险蒙版。默认在风险区域使用参考曝光帧，避免多重轮廓；这只能降低风险，不能证明运动内容被完整恢复。
6. 交付16bit TIFF、JPEG预览、风险蒙版、配准联系表和JSON报告。报告为`review_required`时必须人工查看蒙版与预览。

## 程序化接口

不提供面向用户的命令行入口。把`scripts`目录加入Python路径后调用：

```python
from photo_bracket_fusion import analyze_bracket, fuse_bracket

analysis = analyze_bracket(
    input_paths,
    exposure_times=[0.25, 0.5, 1.0],
)
result = fuse_bracket(
    input_paths,
    output_dir,
    exposure_times=[0.25, 0.5, 1.0],
    motion_handling="reference-frame",
)
```

`exposure_times`单位为秒。省略时读取EXIF；EXIF也缺失时只能通过图像亮度判断是否像曝光包围，报告必须标记曝光时间未经验证。

## 核心约束

- 输入必须是同一机位、同一视场的真实多帧照片。全景、手持大幅换位、不同主体和不同构图不属于本Skill。
- 原图只读，输出路径不得与输入相同，已存在输出不得覆盖。
- 曝光跨度不足、重复内容、尺寸不一致、配准位移过大或同视点置信度过低均为阻断项。
- 只允许平移配准，不用自由形变强行把视差场景对齐。
- 输出融合图是显示参考型曝光融合结果，不是经相机响应标定的物理辐射图。
- 不调整白平衡、HSL、分离色调或创意曲线。
- 不基于主体蒙版重新设计局部明暗。
- 不恢复所有帧都已剪切的高光或所有帧都没有记录的暗部信息。

算法、判定阈值和报告含义见[references/fusion-contract.md](references/fusion-contract.md)。
