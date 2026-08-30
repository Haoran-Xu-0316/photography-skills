---
name: photo-output-preflight
description: 检查照片用于网页、印刷或归档时的尺寸、分辨率、格式、ICC色彩空间、透明通道、元数据隐私和文件完整性，并生成渠道质检清单与机械性网页副本。适用于照片文件交付前检查；不用于特定社交平台规格、审美调色、技术修复、构图裁切或画面内容隐私遮挡。
metadata:
  runtime: 需要Python3.10+及requirements.txt中的依赖；核心检查完全离线；生成副本后的方向、透明度和可读性验收要求执行环境能够查看图像。
---

# 照片交付质检

## 运行契约

- 核心入口是本目录的`SKILL.md`。`scripts`、`references`和`assets`路径必须相对本Skill根目录解析，不依赖特定模型、厂商工具名或提示词语法。
- 自动检查和机械性导出需要Python3.10+和`requirements.txt`中的依赖。执行代理应将本Skill的`scripts`目录临时加入当前Python进程的模块搜索路径，再调用下述接口。
- 文件级结论必须来自实际解析结果。若生成网页或印刷副本，还需要具备图像查看能力的执行代理检查方向、透明通道和可读性。

## 定位

只判断照片文件是否适合目标渠道，回答“能不能交、缺什么、风险在哪里”。不修改摄影内容，不把成功导出等同于视觉合格。

## 目标

- `web`：检查长边、文件体积、格式、sRGB兼容、透明通道和GPS隐私。
- `print`：根据成品尺寸计算有效PPI，检查位深和ICC；没有印厂ICC时不声称完成印刷色彩转换。
- `archive`：记录哈希、格式、尺寸、元数据和重复文件名风险，不重压缩母版。

## 接口

```python
from photo_output_preflight import inspect_delivery, prepare_web_copies

report = inspect_delivery(input_paths, output_dir, target="web")
exports = prepare_web_copies(input_paths, output_dir, long_edge=2400, remove_gps=True)
```

## 约束

- 原图只读，所有导出写入独立目录。
- 网页副本只做尺寸、色彩空间兼容和元数据处理，不做审美调色。
- 透明通道包括RGBA、LA以及带调色板透明信息的图像。网页模式必须把透明通道列为复核项；导出时保留透明度并使用PNG，不能静默转为JPEG。
- 没有嵌入源ICC时只能标记“配置缺失”，不能猜测准确源色彩空间。
- 印刷模式必须提供宽高厘米；没有目标ICC时只报告，不转换CMYK。
- 删除GPS只作用于导出副本，不修改原文件。

渠道标准见[references/targets.md](references/targets.md)。
