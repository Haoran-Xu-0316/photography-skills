---
name: standard-format
description: 统一专业文档与研究交付物的输出格式，同时支持新建和存量文件标准化改造。适用于HTML报告、Excel工作簿、Word文档、PPT、PDF、图表、表格、公式和文字结论，尤其适用于金融研究及固定模板整改；不用于照片像素处理、ICC或EXIF检查、照片渠道副本和摄影文件交付质检。
metadata:
  runtime: 需要目标格式对应的读取、编辑和渲染能力；模板和离线依赖必须随交付物复制；没有实际渲染能力时只能给出整改方案，不能声明验收完成。
---

# 标准输出格式

## 运行契约

- 核心入口是本目录的`SKILL.md`。`references`和`assets`路径必须相对本Skill根目录解析，不依赖特定模型、厂商工具名或提示词语法。
- 执行代理必须具备目标格式对应的读取、编辑和渲染能力。没有相应能力时，只能给出整改方案，不能声称已经修改或验收文件。
- 新建或整改后的HTML、Excel、Word、PPT和PDF必须以实际渲染结果验收，不能用源文件存在或导出成功代替视觉检查。
- 模板和离线依赖必须复制到交付目录后再通过相对路径引用。最终文件不得引用本Skill安装位置、绝对本机路径或联网资源。

## 工作流程

把本skill作为交付物的最后格式层。先完成分析逻辑和结果计算，再套用对应的输出规范。

先判断任务属于哪条路径：没有原文件，要产出新交付物，走路径A；已有文件，要求改成标准格式、按模板重做、套用统一样式、格式对齐、格式整改、风格统一或检查是否符合规范，走路径B。

## 路径A 新建交付物

1. 判断目标交付物类型：HTML、Excel、Word、PPT、PDF、图表表格或纯文字结论。
2. 任何交付物都必须先读取 `references/writing-style.md`。文字口径、分析结构、标题表达、结论写法、标点和括号规则只以该文件为准。
3. 涉及任何视觉展示时必须读取 `references/theme-style.md`。颜色、字体、线条、数字格式和默认主题只以该文件为准，所有颜色必须使用token和HEX代码。
4. 涉及任何图表时必须读取 `references/chart-style.md`。图表类型、配色、尺寸、图例、标签、网格、缩放和降级规则只以该文件为准。
5. 涉及任何表格时必须读取 `references/table-style.md`。表格类型、列顺序、字号、线条、行列上限和数字格式只以该文件为准。
6. 再读取当前任务需要的展示形式参考文件：
   - HTML报告：`references/html-report.md`
   - Excel工作簿：`references/excel-report.md`
   - Word文档：`references/word-report.md`
   - PowerPoint或PPT：`references/ppt-report.md`
   - PDF报告：`references/pdf-report.md`
7. 按统一文字规范处理内容，再按统一主题、统一图表、统一表格和对应格式规范处理结构、字体、配色、图片、公式、注释和间距。
8. 新建独立HTML报告时，优先复制 `assets/html-template/standard-html-template.html` 和 `assets/echarts.min.js` 到新的交付目录，替换标题、结论、图表数据、表格和公式，并把模板中的脚本地址改为交付目录内的相对路径。不能让最终HTML回指本Skill目录。
9. 新建Word报告时，优先复制 `assets/word-template/standard-word-template.docx`，再按 `references/word-report.md` 替换标题、结论、图表和数据。
10. 新建PPT时，优先复制 `assets/ppt-template/standard-ppt-template.pptx`，再按 `references/ppt-report.md` 替换页型内容和图表数据。
11. 新建Excel工作簿时，优先复制 `assets/excel-template/standard-excel-template.xlsx`，再按 `references/excel-report.md` 替换Sheet内容、公式和图表。
12. 新建PDF时，先按 `references/pdf-report.md` 判断TeX PDF、Word PDF或HTML PDF路径；需要PDF样式参考时查看 `assets/pdf-template/standard-pdf-template.pdf`。需要复用生成脚本时以程序方式调用`assets/pdf-template/build_pdf_template.py`的`build`函数，并显式提供当前系统可用字体，不能依赖固定操作系统路径。
13. 如需沉淀复杂案例或验收样例，只能放入项目 `result` 目录；本skill的 `assets` 只保留可复用模板。
14. 必须做结构或视觉校验。HTML报告必须检查左侧目录、ECharts离线渲染、公式展示、章节编号和响应式布局；Word、PPT和PDF必须检查标题层级、图表编号、表格格式、页边距或版式一致性。

## 路径B 存量文件标准化

1. 必须先读取 `references/normalize.md`。诊断标准、整改顺序、迁移判定和验收方式只以该文件为准。
2. 读取原文件，识别交付物类型，再按路径A第2步到第6步读取对应的文字、主题、图表、表格和格式规范。规范文件是判定依据，不重复另立标准。
3. 输出诊断表，逐项标注阻断项、修正项和建议项。
4. 按内容层、结构层、主题层、组件层、交付层的固定顺序整改。阻断项达到迁移阈值时，直接以标准模板为骨架迁移内容，不在原文件上逐条修补。
5. 只改格式层。不修改数据、指标计算结果和分析结论，发现错误单独提示。
6. 保留原文件，输出新文件，命名加 `_std` 后缀或按格式规范重新命名。
7. 按对应格式规范的必做检查逐项验收，输出验收清单和整改说明。

## 核心规则

- 文字和内容规则是全格式统一层，HTML、Excel、Word、PPT、PDF只是展示形式，不得在各格式文件里另起一套文风标准。
- 写作口径要像专业量化金融分析师：简洁、直接、基于证据、先给结论。
- 避免AI味、空泛铺垫、装饰性标点、夸张形容和不专业标签。
- 正文、标题、图表名、表头和PPT要点禁用竖线分隔符。少用括号，能改成短句、逗号或表格列时不要用括号。括号只用于公式、单位、缩写首次定义、必要文件扩展名或引用。
- 报告标题要短而明确。标题下不要堆样本区间、方法、数据列表等冗余小字。
- 层级统一使用 `1.`、`1.1`、`1.2`；中文报告使用中文章节标题。
- 配色共5套方案，默认朱墨。方案名和取值见 `references/theme-style.md`：朱墨用于常规研究，靛青用于宏观和对外材料，松墨用于配置和风险，赭石用于路演，素墨用于黑白打印和送审。
- token名称是角色标识不是颜色名称。切换方案只替换HEX映射，不改token名称、图表类型、表格结构和编号体系。同一交付物只用一套方案。
- 序列色标识对象身份，UP_TONE和DOWN_TONE标识数值方向，两者不得互相替代。
- 全格式表格统一使用黑色三线表，线色一律RULE_BLACK #000000，不随配色方案变化。
- 字体统一限定为宋体、TimesNewRoman和Arial。Word、PDF、Excel的中文标题和正文一律宋体，标题靠字号和加粗区分层级；英文和数字正文用TimesNewRoman，图表坐标轴、PPT和Excel数字用Arial。HTML为屏幕阅读格式，正文和数字改用无衬线字体栈，标题用宋体衬线栈，具体取值见 `references/theme-style.md` 的HTML屏幕例外，不得类推到其他格式。
- assets只放可复用模板、离线脚本、字体和图标；result只放最终输出、复杂样例和验收样例；不要把result混入assets。
- 交付物尽量自包含。HTML报告必须使用离线ECharts，优先使用本skill的 `assets/echarts.min.js`。
- 公式必须以数学公式形式展示，不能放在代码块里。
- PDF必须先明确源文件。TeX PDF以tex为源头，Word PDF以docx为源头，HTML PDF只用于归档或打印。

## 格式选择

- 用户要求HTML、网页报告或报告页面时，默认使用HTML规范。
- 用户要求电子表格、工作簿、数据表或Excel输出时，使用Excel规范。
- 用户要求正式书面报告、备忘录或 `.docx` 时，使用Word规范。
- 用户要求演示材料、路演材料、汇报稿、PPT或 `.pptx` 时，使用PPT规范。
- 用户要求PDF、TeX PDF、LaTeX报告、Word导出PDF或网页打印PDF时，使用PDF规范。
- 同时要求多种格式时，先套用统一写作规则，再分别套用各格式规范。
- 若某类格式还没有详细规范，按核心规则处理，保持克制、清晰、金融研究风格。
