# Photography Skills

一组面向摄影工作流的通用Agent Skills，覆盖照片筛选、技术修复、调色、构图、计算摄影、单图立体化、交付质检与印刷输出。

这些Skill以开放目录结构组织，不绑定特定模型或厂商。每个目录均提供面向读者的`README.md`、无命令行Python示例和面向Agent的`SKILL.md`，并按需附带离线脚本、参考规则、资源模板、依赖声明与测试。`agents/openai.yaml`仅作为可选的OpenAI和Codex界面适配层，不参与通用核心流程。

## Skill清单

| Skill | 功能定位 | 示例 |
|---|---|---|
| [`photo-cull`](photo-cull/README.md) | 基于清晰度、曝光和重复度完成技术筛片，确认后可写入XMP标记 | [Python](photo-cull/examples/basic_usage.py) |
| [`photo-repair`](photo-repair/README.md) | 修复噪点、镜头暗角、横向色差、坏点和热噪点 | [Python](photo-repair/examples/basic_usage.py) |
| [`photo-color-grade`](photo-color-grade/README.md) | 完成全局校色、创意调色、参考色彩匹配和系列色彩统一 | [Python](photo-color-grade/examples/basic_usage.py) |
| [`photo-light-sculptor`](photo-light-sculptor/README.md) | 通过主体蒙版和局部EV调整完成非生成式光影塑形 | [Python](photo-light-sculptor/examples/basic_usage.py) |
| [`photo-composition-crop`](photo-composition-crop/README.md) | 按显著性、焦点和目标比例生成可复核裁切方案 | [Python](photo-composition-crop/examples/basic_usage.py) |
| [`photo-series-editor`](photo-series-editor/README.md) | 为已选照片建立组照顺序、视觉节奏和叙事结构 | [Python](photo-series-editor/examples/basic_usage.py) |
| [`photo-output-preflight`](photo-output-preflight/README.md) | 检查尺寸、格式、色彩空间、透明度、元数据和文件完整性 | [Python](photo-output-preflight/examples/basic_usage.py) |
| [`photo-privacy-redactor`](photo-privacy-redactor/README.md) | 对确认的敏感区域进行不可逆画面遮挡并生成复核材料 | [Python](photo-privacy-redactor/examples/basic_usage.py) |
| [`photo-geometry-corrector`](photo-geometry-corrector/README.md) | 校正水平线、四点透视和基于标定参数的镜头畸变 | [Python](photo-geometry-corrector/examples/basic_usage.py) |
| [`photo-bracket-fusion`](photo-bracket-fusion/README.md) | 对真实包围曝光序列进行配准、曝光融合和鬼影风险检测 | [Python](photo-bracket-fusion/examples/basic_usage.py) |
| [`photo-panorama-stitcher`](photo-panorama-stitcher/README.md) | 拼接具有真实重叠区域的横向或纵向全景照片 | [Python](photo-panorama-stitcher/examples/basic_usage.py) |
| [`photo-focus-stacker`](photo-focus-stacker/README.md) | 合成不同焦平面照片并报告运动和对焦呼吸风险 | [Python](photo-focus-stacker/examples/basic_usage.py) |
| [`photo-to-3d`](photo-to-3d/README.md) | 从单张照片生成深度图、2.5D视差作品和浅浮雕模型 | [Python](photo-to-3d/examples/basic_usage.py) |
| [`photo-print-layout`](photo-print-layout/README.md) | 按物理纸张、边距、出血和装订安全区生成印刷拼版 | [Python](photo-print-layout/examples/basic_usage.py) |

## 使用方式

选择所需Skill并复制完整目录到目标Agent运行时的Skills目录。不要只复制`SKILL.md`，否则脚本、参考资料和模板可能缺失。

运行时应满足对应`requirements.txt`和`SKILL.md`中的运行契约。多数图像处理流程可以完全离线执行；`photo-to-3d`自动估深需要本地模型权重，默认不主动联网下载。

没有图像查看或文档渲染能力时，可以生成诊断、配方或待复核产物，但不能将视觉质量标记为最终完成。

## 目录约定

- `SKILL.md`：能力边界、工作流、输入输出和验收规则
- `README.md`：面向GitHub读者的功能说明和使用入口
- `examples/`：调用真实程序接口的无命令行Python示例
- `scripts/`：确定性处理脚本
- `references/`：算法、参数和操作规范
- `assets/`：离线模板与静态资源
- `requirements.txt`：Python依赖
- `tests/`：独立测试
- `agents/openai.yaml`：可选OpenAI和Codex界面适配

跨模型兼容说明见[PORTABILITY.md](PORTABILITY.md)。

## 质量保证

仓库级测试会核对Skill清单、目录名与`name`一致性、运行契约、说明与示例完整性、资源引用、依赖声明、厂商绑定和机器路径绑定。每个包含脚本的Skill同时保留独立功能测试。
