---
name: photo-panorama-stitcher
description: 将两张及以上真实重叠、扩展视场的照片拼接为单张全景图，并报告特征匹配、投影、接缝、曝光过渡和失败置信度。适用于横向或纵向全景；不用于同视场包围曝光、单张生成式扩图、组照排序或没有真实重叠的照片。
metadata:
  runtime: 需要Python3.10+及requirements.txt中的依赖；核心流程完全离线；最终全景验收要求执行环境能够查看联系表、接缝过渡图和全景结果。
---

# 照片全景拼接

## 运行契约

- 核心入口是本目录的`SKILL.md`。`scripts`、`references`和`assets`路径必须相对本Skill根目录解析，不依赖特定模型、厂商工具名或提示词语法。
- 自动分析和拼接需要Python3.10+和`requirements.txt`中的依赖。执行代理应将本Skill的`scripts`目录临时加入当前Python进程的模块搜索路径，再调用下述接口。
- 最终验收需要查看联系表、接缝过渡图和全景结果。无法查看图像的模型只能输出待复核结果，不能宣称无缝拼接完成。

## 定位

只处理两张及以上从相邻机位或相邻朝向拍摄、具有真实重叠区域并共同扩展视场的照片，回答“这些照片能否可靠拼接、采用什么投影、接缝与曝光过渡是否可信、结果如何复现”。

只拼接具有真实重叠和新增视场的照片，不补造未拍摄区域，也不进行同视场曝光融合、叙事排序或生成式扩图。

## 工作流

1. 锁定至少两张不同的源文件，要求用户按空间相邻顺序提供；记录尺寸和SHA-256。
2. 根据视角选择`planar`或`cylindrical`投影。普通窄幅、平面主体优先`planar`；宽视角旋转拍摄可选`cylindrical`。
3. 调用`scripts.photo_panorama_stitcher.analyze_panorama`检查特征数量、相邻匹配、RANSAC内点率、重叠比例和新增视场比例。
4. 存在阻断项时停止。不得用强制配准、生成式填充或复制边缘掩盖失败。
5. 调用`scripts.photo_panorama_stitcher.stitch_panorama`完成共同画布变换、重叠区亮度增益估计、距离羽化接缝和有效矩形裁切。
6. 交付TIFF、JPEG预览、有效区域蒙版、接缝过渡图、联系表和JSON报告。`review_required`必须目视检查重影、弯曲直线和接缝亮度跳变。

## 程序化接口

不提供面向用户的命令行入口。把`scripts`目录加入Python路径后调用：

```python
from photo_panorama_stitcher import analyze_panorama, stitch_panorama

analysis = analyze_panorama(
    input_paths,
    projection="planar",
)
result = stitch_panorama(
    input_paths,
    output_dir,
    projection="planar",
)
```

`projection`只能是`planar`或`cylindrical`。圆柱投影可通过`focal_length_px`使用已知像素焦距；省略时采用有明确报告标记的经验估计，不得描述为相机标定值。

## 核心约束

- 输入必须是两张及以上不同源文件，并按空间相邻顺序排列。Skill不自动改写用户的叙事或时间顺序。
- 相邻照片必须同时具有可验证重叠和新增视场。完全重合的同视场照片不是全景输入。
- 原图只读；输出路径不得与输入相同，已存在交付文件不得覆盖。
- 只使用源照片记录的像素。画布中没有任何源图覆盖的区域保持无效并在裁切时去除。
- 单应模型适合以相机旋转为主、景物相对较远的拍摄。明显视差、移动主体、波浪或近距离多平面场景必须标记人工复核，不能宣称无缝。
- `planar`不会被称为镜头标定；经验圆柱焦距不会被称为真实相机内参。
- 自动曝光过渡只估计重叠区的标量亮度增益，不进行白平衡、HSL、创意曲线或局部光影设计。
- 禁止生成式扩图、内容感知填充和镜像边缘；禁止把黑边裁掉后的像素外推称为真实画面。

判定阈值、模型含义和报告字段见[references/stitching-contract.md](references/stitching-contract.md)。
