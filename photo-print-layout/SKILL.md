---
name: photo-print-layout
description: 将已经定稿的照片按毫米纸张、网格、边距、出血和装订安全区放入可印刷物理页面，输出拼版预览、印刷尺寸PDF、高分辨率页面图和放置清单。适用于照片墙、摄影集内页、联系印样和多图印刷拼版；不用于审美裁切、单图交付质检、报告或演示文档排版。
metadata:
  runtime: 需要Python3.10+及requirements.txt中的依赖；核心流程完全离线；最终拼版验收要求执行环境能够渲染并查看PDF页面图。
---

# 照片印刷拼版

## 运行契约

- 核心入口是本目录的`SKILL.md`。`scripts`、`references`和`assets`路径必须相对本Skill根目录解析，不依赖特定模型、厂商工具名或提示词语法。
- 自动分析和拼版需要Python3.10+和`requirements.txt`中的依赖。执行代理应将本Skill的`scripts`目录临时加入当前Python进程的模块搜索路径，再调用下述接口。
- 最终验收需要将PDF实际渲染为页面图并检查裁切标记、边距、槽位、分页和清晰度。无法查看渲染页的模型不能宣称印刷拼版完成。

## 定位

只回答“这些已定稿照片如何落在物理页面上”。页面几何以毫米定义，照片内容视为不可编辑资产。

以下任务应转交其他Skill：

- 重新选择画面范围或改善构图：`photo-composition-crop`。
- 判断单张照片能否满足网页、印刷或归档规格：`photo-output-preflight`。
- 制作报告、PPT、正文文档或信息图：转交相应的文档排版或数据可视化Skill。
- 调色、修复、加减光或生成内容：对应照片处理Skill。

## 开始前必须确认

- 成品纸张宽高，单位为毫米。
- 网格行列、页边距、图间距和背景色。
- `fit_strategy`：`contain`完整保留，或明确的`cover-center`、`cover-top`、`cover-bottom`裁切策略。
- 是否需要出血、裁切标记及装订安全区。
- 目标输出DPI和最低可接受有效PPI。

用户没有明确`fit_strategy`时，不得猜测是否允许裁切。需要满版时通常使用`cover-*`；需要完整保留画面时使用`contain`。

## 程序化接口

```python
from photo_print_layout import analyze_print_layout, create_print_layout

plan = analyze_print_layout(
    input_paths,
    paper_size_mm=(210, 297),
    grid=(2, 2),
    fit_strategy="contain",
)

result = create_print_layout(
    input_paths,
    output_dir,
    paper_size_mm=(210, 297),
    grid=(2, 2),
    fit_strategy="contain",
    margins_mm=(15, 15, 18, 20),
    gap_mm=6,
    bleed_mm=3,
    binding_edge="left",
    binding_safe_mm=8,
)
```

脚本位于`scripts/photo_print_layout.py`，供Python调用，不提供面向用户的命令行界面。

## 输出

- 每页高分辨率PNG，像素尺寸与指定DPI和物理页面一致。
- 多页印刷尺寸PDF。
- 带成品线、槽位和装订区提示的低分辨率预览。
- JSON和CSV清单，记录毫米坐标、像素坐标、源图裁切框、有效PPI、哈希和警告。

## 硬约束

- 原图只读；运行前后核对SHA-256，不覆盖任何已有输出。
- 不自动旋转构图、不重新排序、不移动或删除源文件。
- 只有明确的`cover-*`策略可以裁掉源图边缘；`contain`绝不裁图。
- 有效PPI低于最低阈值时默认中止。只有调用方显式设置`allow_low_ppi=True`才可带醒目警告继续。
- `output_basename`只能是文件名主体，不能包含路径分隔符或平台保留字符；所有交付物必须留在指定输出目录内。
- 输出DPI高于源图有效PPI只会增加采样像素，不会增加真实细节，必须在清单中披露。
- 脚本使用RGB工作页，不完成印厂ICC、CMYK、专色、油墨限制或软打样转换；交印前仍需按印厂规范复核。
- 每次生成PDF后必须渲染成PNG检查裁切标记、边距、槽位、分页和清晰度。

物理坐标、出血和风险判定见[references/print_geometry.md](references/print_geometry.md)。
