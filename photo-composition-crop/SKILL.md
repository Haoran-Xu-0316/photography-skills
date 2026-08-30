---
name: photo-composition-crop
description: 根据显著性、边缘密度和用户焦点生成不同画幅比例的裁切草案、预览与可复现坐标。适用于头像、社交媒体、网站横幅、打印画幅和同图多比例适配；人物裁切需要视觉复核，不用于生成式扩图、调色、修复、主体重绘或自动删除画面元素。
metadata:
  runtime: 需要Python3.10+及requirements.txt中的依赖；核心流程完全离线；最终裁切验收要求执行环境能够查看构图叠加图和实际裁切结果。
---

# 照片构图裁切

## 运行契约

- 核心入口是本目录的`SKILL.md`。`scripts`、`references`和`assets`路径必须相对本Skill根目录解析，不依赖特定模型、厂商工具名或提示词语法。
- 自动分析和裁切需要Python3.10+和`requirements.txt`中的依赖。执行代理应将本Skill的`scripts`目录临时加入当前Python进程的模块搜索路径，再调用下述接口。
- 最终验收需要查看构图叠加图和实际裁切结果，人物画面还必须复核头顶、下巴和肢体边界。无法查看图像的模型不能宣称裁切通过。

## 定位

只处理取景范围和画幅比例，回答“保留哪里、裁掉哪里”。原图只读，不做生成式补边和内容感知填充。

## 模式

- `single`：针对一个比例输出最佳裁切和两个备选。
- `set`：同时输出1:1、4:5、3:4、16:9等多比例安全裁切。
- `safe-area`：只输出构图框和安全区，不实际生成裁切副本。

## 工作流

1. 计算显著性、边缘密度、自动视觉中心和用户焦点。
2. 在保持最大可用面积的前提下搜索裁切位置。
3. 同时评估显著内容保留、主体切断、边缘拥挤和三分线关系。
4. 输出坐标JSON、构图叠加图和非覆盖裁切副本。

## 接口

```python
from photo_composition_crop import analyze_composition, create_crop_set

analysis = analyze_composition(input_path, focus_point=None)
result = create_crop_set(input_path, output_dir, aspect_ratios=("1:1", "4:5", "16:9"))
```

## 约束

- 用户焦点使用0至1归一化坐标，优先级高于自动显著性。
- 高显著区域触及裁切边界时降低评分；当前不含人脸或人体关键点检测，人物头顶、下巴和肢体必须人工检查。
- 不放大超过原图分辨率，不改颜色，不覆盖原图。
- 需要扩图时应切换到专门生成式扩图能力，不能在本skill内静默补造内容。

评分规则见[references/scoring.md](references/scoring.md)。
