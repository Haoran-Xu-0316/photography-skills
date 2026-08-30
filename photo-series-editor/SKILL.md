---
name: photo-series-editor
description: 为已经选中的多张照片建立组照顺序、视觉节奏、开场与收束结构，并输出编号联系表和序列清单。适用于摄影组照、旅行故事、活动回顾、作品集和社交轮播；不负责技术筛片、删除废片、调色、修图或移动原文件。
metadata:
  runtime: 需要Python3.10+及requirements.txt中的依赖；核心流程完全离线；最终叙事顺序要求执行环境能够查看完整编号联系表并记录人工确认。
---

# 组照叙事编辑

## 运行契约

- 核心入口是本目录的`SKILL.md`。`scripts`、`references`和`assets`路径必须相对本Skill根目录解析，不依赖特定模型、厂商工具名或提示词语法。
- 自动分析和排序需要Python3.10+和`requirements.txt`中的依赖。执行代理应将本Skill的`scripts`目录临时加入当前Python进程的模块搜索路径，再调用下述接口。
- 最终编辑需要查看完整编号联系表。无法查看整组照片的模型只能生成机械排序初稿，不能宣称叙事顺序已经完成。

## 定位

只处理多张照片之间的关系，回答“先放哪张、如何转场、怎样收束”。`photo-cull`判断技术废片，本skill假设输入已经完成筛选，不再判废。

## 策略

- `chronology`：严格尊重拍摄时间，并报告连续近似画面，不为节奏改写事实顺序。
- `visual-rhythm`：在颜色、明暗、横竖方向和边缘密度变化之间建立节奏。
- `manual`：按用户指定顺序生成编号、联系表和清单。

## 工作流

1. 读取照片时间、横竖方向、亮度、色彩、边缘密度和感知指纹。
2. 标记近似画面，但不删除或降级照片。
3. 生成初步序列和带编号联系表。
4. 执行代理必须观看联系表，再决定是否调整开场、转场和结尾。
5. 输出序列JSON、CSV、联系表和非破坏性文件清单。

## 接口

```python
from photo_series_editor import build_series

draft = build_series(input_paths, draft_output_dir, strategy="visual-rhythm")

# 观看draft["contact_sheet"]并按最终顺序重排路径后，写入新的输出目录。
reviewed = build_series(
    reviewed_input_paths,
    reviewed_output_dir,
    strategy="manual",
    visual_review_confirmed=True,
)
```

## 约束

- 原图不移动、不重命名、不删除。
- 相似照片不得机械判废，只避免无意连续重复。
- 自动顺序是初稿，不替代对人物表情、事件意义和叙事意图的视觉判断。
- 只有`manual`策略允许记录`visual_review_confirmed=True`。该值只能在执行代理实际查看完整联系表并确定最终路径顺序后传入；机械排序不能直接升级为已复核状态。
- 不在本skill内统一颜色；需要时先使用`photo-color-grade`。

叙事原则见[references/sequence.md](references/sequence.md)。
