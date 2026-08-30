# 自有Skill跨模型兼容说明

## 兼容目标

本目录的15个自有Skill以Agent Skills开放目录格式为共同核心。每个Skill都以`SKILL.md`为入口，按需携带`scripts`、`references`、`assets`和`requirements.txt`。

每个`SKILL.md`都在标准`metadata`映射中提供字符串型`runtime`说明，用于声明Python、离线资源和视觉验收能力。运行时可以读取该字段，也可以忽略它并按正文的“运行契约”执行。

这里的“通用”是能力通用，不是声称任何纯文本模型都能直接处理本地图片。运行时至少需要读取Skill目录和用户文件；需要实际处理图片时，还要能够执行Python；需要完成视觉验收时，还要能够查看原图和输出预览。

## 核心与适配层

- 通用核心：`SKILL.md`、`scripts`、`references`、`assets`、`requirements.txt`。
- OpenAI适配层：`agents/openai.yaml`。它只提供显示名称、简介和默认提示，不参与核心工作流。
- 其他运行时：读取通用核心即可；不识别`agents/openai.yaml`时应忽略该目录，不需要改写Skill正文。

通用核心不得出现厂商专属工具名、专属提示词变量、用户机器绝对路径或隐式联网要求。任何资源引用都应相对当前Skill根目录解析。

## 能力分组

| 能力组 | Skill | 最低运行能力 | 完成条件 |
|---|---|---|---|
| 照片分析与非生成式处理 | `photo-cull`、`photo-repair`、`photo-color-grade`、`photo-light-sculptor`、`photo-composition-crop`、`photo-series-editor`、`photo-output-preflight`、`photo-privacy-redactor`、`photo-geometry-corrector` | 读取本地文件、Python3.10+、对应依赖 | 实际报告与视觉证据通过复核 |
| 多帧计算摄影 | `photo-bracket-fusion`、`photo-panorama-stitcher`、`photo-focus-stacker` | 读取多张本地图片、Python3.10+、OpenCV与对应依赖 | 配准、风险图和最终图通过复核 |
| 单图立体化 | `photo-to-3d` | 读取本地图片、Python3.10+、对应依赖；自动估深需要本地模型权重 | 深度、视差或网格结果通过复核 |
| 印刷页面 | `photo-print-layout` | 读取本地图片、Python3.10+、PDF生成与渲染能力 | PDF渲染页通过物理尺寸和视觉检查 |
| 专业交付格式 | `standard-format` | 目标格式的读取、编辑和渲染能力 | 实际渲染的HTML、Excel、Word、PPT或PDF通过验收 |

## 打包与安装规则

1. 必须复制完整Skill目录，不能只复制`SKILL.md`，否则脚本、参考资料和模板会丢失。
2. 目录名必须与`SKILL.md`中的`name`完全一致。
3. 安装到不同运行时时，只改变安装位置或增加运行时适配文件，不修改通用核心的业务边界。
4. Python依赖按各Skill的`requirements.txt`安装到运行时允许使用的既有环境，不在Skill内创建私有环境。
5. `photo-to-3d`默认只使用本地模型缓存。下载模型、联网或写入外部位置必须先取得用户明确许可。
6. 没有视觉查看能力时，可以生成诊断、配方或待复核产物，但不能把视觉质量状态写成完成。

## 自有Skill清单

1. `photo-cull`
2. `photo-repair`
3. `standard-format`
4. `photo-color-grade`
5. `photo-light-sculptor`
6. `photo-composition-crop`
7. `photo-series-editor`
8. `photo-output-preflight`
9. `photo-privacy-redactor`
10. `photo-geometry-corrector`
11. `photo-bracket-fusion`
12. `photo-to-3d`
13. `photo-panorama-stitcher`
14. `photo-focus-stacker`
15. `photo-print-layout`
