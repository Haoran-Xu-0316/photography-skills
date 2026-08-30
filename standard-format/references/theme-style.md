# 统一主题规范

本文件定义所有交付格式共用的颜色、字体、线条、间距和数字口径。HTML、Excel、Word、PPT、PDF不得另起一套颜色系统。用户要求更换主题时，只替换本文件的主题token和对应模板变量，不改图表类型、表格结构、标题层级和编号体系。

## 固定字体

- 中文：宋体。Word、PDF、Excel的标题和正文一律宋体，标题靠字号和加粗区分层级，不靠更换字体。
- 英文和数字正文：TimesNewRoman。
- 图表坐标轴、图例、PPT正文、Excel数字和界面控件：Arial。
- 公式：使用目标格式的可编辑数学公式；公式中的英文变量和数字保持TimesNewRoman风格。
- 不得引入其他字体名称。系统生成文件中的底层字体内部名除外，但可见字体体系必须对应以上三类。

### HTML屏幕例外

HTML是屏幕阅读格式，与Word、PPT、Excel、PDF的打印或投影场景不同，正文和表格文字改用无衬线中文字体栈以提升小字号可读性，此例外只适用于HTML，不得类推到其他格式。

- HTML中文正文和表格：`"PingFang SC","Microsoft YaHei","Source Han Sans SC",sans-serif`，不再使用宋体。
- HTML英文和数字正文：Arial优先，`"Arial","PingFang SC","Microsoft YaHei",sans-serif`，不再使用TimesNewRoman。
- HTML标题（h1、h2、h3、`.part-head`、`.serif`）：使用衬线中文字体栈 `"Source Han Serif SC","Songti SC","STSong",serif`，与无衬线正文形成层级对比，同时与Word和PDF的宋体体系保持一致。
- HTML公式块 `.eq`：保留TimesNewRoman和衬线数学字体不变，这是数学排版的通行惯例，不随正文改动。

## 默认颜色token

所有颜色必须用token和HEX代码表达，不得只写颜色泛称。

token名称是角色标识，不是颜色名称。切换配色方案时token名称不变，只替换HEX映射。下表HEX为默认方案朱墨的取值。

| token | 角色 | 朱墨HEX |
|---|---|---:|
| SERIES_MAIN | 增强策略、核心组合、核心结论、重点箭头 | #C8102E |
| SERIES_MAIN_DEEP | Hero深色端、一级标题强调、重要边框 | #9E0B24 |
| SERIES_BENCH | 基准组合、原策略、对照项、债券资产 | #2A6FB0 |
| SERIES_BENCH_DEEP | 页眉深色端、图表深色辅助线 | #174A7C |
| SERIES_ACCENT | 章节号、样本切分、滚动训练、黄金资产 | #D99A2B |
| SERIES_ACCENT_DEEP | 流程节点强调、图表事件标记、重点标签边框 | #B07818 |
| SERIES_DEFENSE | 风险下降、防御资产 | #1F8A5B |
| SERIES_RISK | 风险因子、另类资产、异常暴露、压力情景 | #6B2E8A |
| SERIES_NEUTRAL | 现金、其他项、合并项、低优先级图例 | #B4A897 |
| UP_TONE | 正收益、正贡献、上涨 | #C8102E |
| DOWN_TONE | 负收益、亏损、下跌、回撤收窄 | #1F8A5B |
| INK | 正文主文字 | #1E1B18 |
| TEXT_SECONDARY | 段落解释、表格首列、图注正文 | #5A5148 |
| MUTED | 图注、来源、脚注、坐标轴标签 | #8C8073 |
| GRID_LINE | HTML卡片边框、图表网格线 | #EBE3D6 |
| GRID_LINE_STRONG | 章节分隔线 | #D8C9B2 |
| RULE_BLACK | 全格式三线表的顶线、表头下线、底线、分组线 | #000000 |
| FOCUS | HTML键盘焦点态描边 | #C8102E |
| PAPER | HTML页面背景、PDF浅底 | #FBF8F3 |
| PANEL | 卡片、表格、页面主面板 | #FFFFFF |
| NOTE_BG | HTML说明块浅底 | #FAF4EA |
| ROW_HOVER | HTML表格悬停底色 | #FCF8F1 |
| INPUT_FILL | Excel参数输入区 | #FFF2CC |
| CALC_FILL | Excel公式计算区 | #DDEBF7 |
| SOURCE_FILL | Excel数据来源区、注释区 | #F2F2F2 |
| WARNING_FILL | 风险阈值、异常提示浅底 | #FCE4D6 |
| MISSING_GREY | 缺失值、不可得值 | #A6A6A6 |
| FORMULA_BG | HTML公式块浅底 | #FAF7F1 |
| HEATMAP_NEG | 相关性热力图负向端 | #E9F2FA |
| HEATMAP_POS | 相关性热力图正向端 | #F7DCE1 |

## 配色方案

共5套方案，默认朱墨。用户指定方案名或用途时切换，只替换token的HEX映射，不改token名称、图表类型、表格结构和编号体系。同一交付物只允许使用一套方案，不得跨方案取色。

| token | 朱墨 | 靛青 | 松墨 | 赭石 | 素墨 |
|---|---:|---:|---:|---:|---:|
| SERIES_MAIN | #C8102E | #1F4E79 | #1F6F54 | #B4531F | #1C1A17 |
| SERIES_MAIN_DEEP | #9E0B24 | #143A5C | #14513C | #8A3E15 | #000000 |
| SERIES_BENCH | #2A6FB0 | #C8871B | #A33B4A | #2F7B7D | #423E38 |
| SERIES_BENCH_DEEP | #174A7C | #A06A11 | #822F3B | #205859 | #2A2723 |
| SERIES_ACCENT | #D99A2B | #B0344F | #C0902B | #33518F | #696259 |
| SERIES_ACCENT_DEEP | #B07818 | #8C2740 | #9C7420 | #263E6E | #4E4842 |
| SERIES_DEFENSE | #1F8A5B | #2E8B72 | #3E7CB1 | #4E7A3C | #8E867B |
| SERIES_RISK | #6B2E8A | #7A5EA6 | #8A5A83 | #7E5A8C | #AFA9A1 |
| SERIES_NEUTRAL | #B4A897 | #A8A29B | #A8A399 | #ADA79E | #CBC8C2 |
| UP_TONE | #C8102E | #C8102E | #C8102E | #C8102E | #1C1A17 |
| DOWN_TONE | #1F8A5B | #1F8A5B | #1F8A5B | #1F8A5B | #696259 |
| FOCUS | #C8102E | #1F4E79 | #1F6F54 | #B4531F | #1C1A17 |
| INK | #1E1B18 | #16202A | #1C211D | #221A14 | #1E1B18 |
| TEXT_SECONDARY | #5A5148 | #44515E | #4C544C | #574737 | #4E4B46 |
| MUTED | #8C8073 | #7C8894 | #7E857C | #8A7967 | #86827B |
| GRID_LINE | #EBE3D6 | #E1E7ED | #E3E6DF | #EAE2D7 | #E4E1DB |
| GRID_LINE_STRONG | #D8C9B2 | #C7D0D9 | #CBD0C6 | #D6C7B3 | #CBC7C0 |
| PAPER | #FBF8F3 | #F7F9FB | #F8F8F4 | #FCF9F5 | #FFFFFF |
| PANEL | #FFFFFF | #FFFFFF | #FFFFFF | #FFFFFF | #FFFFFF |
| NOTE_BG | #FAF4EA | #F1F5F9 | #F2F4EE | #FAF3EA | #F5F4F1 |
| ROW_HOVER | #FCF8F1 | #F6F9FC | #F6F8F3 | #FCF6EF | #F8F7F5 |
| WARNING_FILL | #FCE4D6 | #FBE3D2 | #F6E6D2 | #FAE3D3 | #EDEAE5 |
| FORMULA_BG | #FAF7F1 | #F4F7FA | #F5F7F2 | #FAF6F0 | #F7F6F3 |
| HEATMAP_NEG | #E9F2FA | #E6F0F7 | #E8F1EC | #E6F1F1 | #EFEEEB |
| HEATMAP_POS | #F7DCE1 | #FBE7D6 | #F6EAD6 | #F8E2D4 | #DCD8D2 |

RULE_BLACK、MISSING_GREY、INPUT_FILL、CALC_FILL、SOURCE_FILL在全部方案中固定，不随方案变化。三线表线色任何方案下都是RULE_BLACK #000000。

### 方案定位

- 朱墨：默认方案。红蓝金融主题，适用于策略研究、因子分析、业绩归因等常规研究报告。
- 靛青：冷底方案。主体深蓝，对照琥珀，辅助绛红，三色互相拉开色相，适用于宏观研究、行业比较和对外正式材料。
- 松墨：低饱和方案。主体墨绿，对照绛红，辅助秋金，适用于资产配置、风险管理和长文本为主的报告。
- 赭石：暖底方案。主体陶红，对照青绿，辅助靛蓝，暖主体配冷对照，适用于路演材料和需要区别于常规研究风格的展示场景。
- 素墨：无彩方案。全部序列色为黑白灰，适用于黑白打印、送审稿和监管报送。序列必须同时用线型或标记区分，不得只靠灰阶。HTML中把模板的`ACHROMATIC`开关置为true，`normalizeChartOption`会自动按序列索引轮换线型、标记形状和柱状描边；Word、PPT、Excel和PDF需手工按下表指定。

素墨方案的序列区分手段固定如下，按序列顺序取用：

| 序列 | 线型 | 标记形状 | 柱状区分 |
|---|---|---|---|
| 1 | 实线 | 圆形 | 实心 |
| 2 | 长虚线 | 方形 | 描边加浅填充 |
| 3 | 点线 | 三角形 | 描边加中填充 |
| 4 | 点划线 | 菱形 | 描边加深填充 |
| 5 | 长划线 | 圆角方形 | 描边加中填充 |
| 6 | 短虚线 | 水滴形 | 描边加浅填充 |

- 素墨方案下所有折线必须显示标记点，不得用无标记折线；数据点超过14个时按间隔抽样显示，避免标记重叠成一片。

### 配色设计约束

新增或修改方案时必须满足以下条件，否则序列在图表中不可分辨。

- 五个有彩序列色SERIES_MAIN、SERIES_BENCH、SERIES_ACCENT、SERIES_DEFENSE、SERIES_RISK的相邻色相间隔不低于35度，暖色区不得同时放置两个高饱和序列。
- SERIES_NEUTRAL与SERIES_MAIN的色相差不低于40度，或饱和度差不低于35个百分点，避免被读成同一序列的深浅变体。
- 同一方案内序列色明度差控制在45个百分点以内，不允许出现一条极浅一条极深的组合。
- 素墨方案六档灰阶按明度10、24、38、52、66、78铺开，相邻明度差不低于12个百分点，最浅档不高于78个百分点。六档在白底上无法同时满足更大间隔，因此素墨必须叠加线型和标记区分，不得只靠灰阶。
- UP_TONE和DOWN_TONE不得与任一序列色重复，素墨方案下两者也不得落在序列灰阶的相邻档位。

### 涨跌语义色

- UP_TONE和DOWN_TONE与序列色分离。序列色标识对象身份，涨跌色标识数值方向，两者不得互相替代。
- 默认中国市场口径，涨为红跌为绿。用户要求国际口径时，UP_TONE换为#1F8A5B，DOWN_TONE换为#C8102E，全报告同步替换。
- 素墨方案下涨跌不用颜色区分，改用正负号、箭头符号或加粗。

### 渐变和色阶

各方案的渐变端点由本方案的token推导，不另取色。

- Hero渐变：`linear-gradient(120deg, SERIES_MAIN_DEEP 0%, SERIES_MAIN 55%, SERIES_ACCENT 140%)`。
- 正向单色渐变：SERIES_MAIN的10%浓度到SERIES_MAIN。
- 负向或风险改善渐变：SERIES_DEFENSE的10%浓度到SERIES_DEFENSE。
- 相关性双向色阶固定为HEATMAP_NEG、PANEL、HEATMAP_POS三点。
- 敏感性收益色阶为SERIES_MAIN的三档浓度，敏感性回撤色阶为SERIES_DEFENSE的三档浓度。
- 热力图不得使用彩虹色、荧光色或方案外色阶。

### 切换方式

- HTML：只改`:root`的CSS变量一处。JS的`THEME`对象必须用`getComputedStyle`从`:root`读取，不得在JS里另存一份HEX，否则页面配色和图表配色会分家且不报错。图表颜色由`SERIES_PALETTE`统一提供，`normalizeChartOption`在图表未显式指定`color`时自动注入，单图不逐张写颜色。
- Word、PPT、Excel：只改模板主题色板，不逐个对象改填充。
- PDF：在源文件层切换，TeX改颜色定义块，Word PDF和HTML PDF随源文件。
- 切换后必须复查：同一对象在全报告是否仍为同一颜色，三线表是否仍为RULE_BLACK，涨跌色是否与序列色混用。

## 图表序列颜色顺序

同一报告内多序列颜色顺序固定。不能因为换了一张图就改变同一对象颜色。

1. 基准组合、原策略、对照项：SERIES_BENCH。
2. 策略组合、增强策略、核心资产：SERIES_MAIN。
3. 滚动训练、备选策略、样本切分：SERIES_ACCENT。
4. 防御资产、风险下降、回撤改善：SERIES_DEFENSE。
5. 风险因子、压力情景、另类资产：SERIES_RISK。
6. 现金、其他项、合并项：SERIES_NEUTRAL。

资产类别固定映射：

| 资产类别 | token |
|---|---|
| 权益 | SERIES_MAIN |
| 债券 | SERIES_BENCH |
| 黄金 | SERIES_ACCENT |
| 现金 | SERIES_NEUTRAL |
| 另类 | SERIES_RISK |
| 防御或低波资产 | SERIES_DEFENSE |

## 线条和背景

- 图表坐标轴线：MUTED，宽度1px或0.75磅。
- 图表主网格线：GRID_LINE，虚线，宽度1px或0.5磅。
- 图表零线：TEXT_SECONDARY，实线，宽度1px或0.75磅。
- HTML卡片边框：GRID_LINE，1px。
- 全格式表格统一使用黑色三线表，线色一律RULE_BLACK #000000，不因格式改色。
- 顶线和底线1.5磅或1.5px，表头下线0.75磅或1px，分组线0.5磅或1px。
- 表格不画竖线，正文行之间不画横线。分组线全表最多3条。
- 表头无底色。仅HTML滚动容器内的sticky表头允许使用PANEL，用途是遮挡滚动内容，不作为表头样式。
- PPT页脚分隔线：GRID_LINE，0.5磅。

## 数字格式

- 收益率、波动率、回撤、权重、贡献率：默认1位百分比，Excel底层可保留2位百分比。
- 净值、指数点位：净值3位小数，指数点位2位小数。
- 夏普、卡玛、相关系数、胜率、换手：2位小数。
- 回归系数、因子暴露：3位小数。
- 金额：千分位，2位小数。
- 日期：YYYY-MM-DD。
- 缺失值写NA，不适用写不适用，零值写0。
