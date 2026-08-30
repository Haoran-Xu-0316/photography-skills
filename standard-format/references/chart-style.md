# 统一图表规范

本文件定义所有交付格式共用的图表规则。颜色、字体和数字格式引用 `references/theme-style.md`。HTML必须用离线ECharts；Word、PPT、PDF使用可编辑图表、矢量图或高清PNG时，也必须保持同一套颜色、字号、图例、标签和降级规则。

## 通用硬规则

- 每张图必须有中文图表标题、横轴名称、纵轴名称、单位、图例或series说明、数据截止日、样本区间和来源说明。
- 图表标题说明对象和指标，不写“结果图”“数据图”“趋势展示”。
- 同一对象在全报告中颜色固定，按 `theme-style.md` 的图表序列颜色顺序执行。
- 图表坐标轴字体使用Arial，字号不低于11px或8.5磅。PPT主文图表坐标轴使用10到12磅。
- 图例默认置于图表上方，横向排列。1到3个series用普通图例，4到6个series用滚动图例或分组图例，超过6个series必须合并、拆图或转表。
- 网格背景默认关闭，只保留Y轴主网格线。热力图和矩阵图允许显示splitArea。
- 数据标签默认关闭，只标注起点、终点、极值点、当前参数、阈值、样本切分点或核心事件。
- 单张图全量label不得超过8个；四图页或四图组件中每张图label不得超过3个。
- tooltip只能补充信息，不能作为唯一信息来源。静态Word、PPT、PDF必须把核心口径写在标题、图注或来源说明中。
- 禁止三维图、立体柱、无意义雷达图、仪表盘、彩虹热力图、装饰性阴影和未说明的双轴。

## HTML ECharts默认工厂

HTML图表必须经过统一`normalizeChartOption`处理，不允许每张图散写完整option。

| 工厂函数 | 适用场景 | 固定规则 |
|---|---|---|
| createLineChart | 净值、价格、因子、权重时序 | showSymbol=false，smooth=false，lineWidth=2.0，观测点超过60开启inside和slider dataZoom |
| createDrawdownChart | 回撤路径 | 数据必须为0或负值，areaStyle.opacity=0.08，Y轴百分比，日期范围与净值图一致 |
| createBarChart | 年度收益、指标差值、单项贡献 | 类别不超过12个，正值SERIES_MAIN，负值SERIES_DEFENSE |
| createHorizontalBarChart | 贡献排序、长名称类别 | 按贡献或改善幅度排序，左边距80到120px，类别超过12个优先横向 |
| createStackedBarChart | 资产收益贡献、风险贡献 | 堆叠项不超过6类，资产颜色按固定映射，其他项合并为SERIES_NEUTRAL |
| createHeatmapChart | 相关矩阵、权重矩阵、二维敏感性 | 必须有visualMap，色阶用固定渐变，可见格不超过18×18 |
| createScatterChart | 风险收益、因子暴露 | 点必须有名称，点大小只绑定规模、成交、换手、样本量等真实变量 |
| createDonutChart | 静态结构占比 | 类别不超过6个，不用于收益贡献和时间变化 |
| createSensitivityChart | 单参数扰动 | 先放敏感性摘要表，再放收益、回撤、夏普或卡玛图 |

HTML ECharts固定option：

```js
const CHART_DEFAULTS={
  textStyle:{fontFamily:'Arial, "PingFang SC", "Microsoft YaHei", sans-serif',fontSize:12,color:THEME.INK},
  grid:{left:52,right:18,top:54,bottom:36,containLabel:true},
  tooltip:{confine:true,backgroundColor:'rgba(255,255,255,.96)',borderColor:THEME.GRID_LINE,borderWidth:1},
  legend:{top:4,itemWidth:16,itemHeight:8,textStyle:{fontSize:12,color:THEME.TEXT_SECONDARY}},
  axisLine:{lineStyle:{color:THEME.MUTED,width:1}},
  splitLine:{lineStyle:{color:THEME.GRID_LINE,type:'dashed',width:1}},
  dataZoomSlider:{height:16,bottom:8}
};
```

有slider dataZoom时，`grid.bottom`必须不低于58px。所有图表容器必须有明确高度，渲染后统一注册到`CHARTS`数组，窗口resize时150ms防抖统一resize。

## 图表类型矩阵

### 净值曲线

- 图形：折线图。
- 固定颜色：策略组合SERIES_MAIN，基准组合SERIES_BENCH，滚动或备选组合SERIES_ACCENT。
- HTML尺寸：主图420px，普通图360px，四图组件300px。
- Word尺寸：单栏宽14.5厘米，高7到8厘米；双图宽7.1厘米，高5.2到6厘米。
- PPT尺寸：单图页x=0.75英寸，y=1.45英寸，w=11.8英寸，h=4.85英寸；双图页单图w=5.55英寸，h=4.45英寸。
- PDF尺寸：单栏宽度不超过正文版心，高7到9厘米。
- 横轴最多显示8个主刻度。日频超过60个观测点必须启用HTML dataZoom；静态格式改为按月、季度或年度抽样显示。

### 回撤图

- 图形：面积折线图或折线图。
- 数据：必须为0或负值，Y轴使用百分比。
- 固定颜色：策略组合SERIES_MAIN，基准组合SERIES_BENCH，相对回撤差SERIES_DEFENSE。
- 面积透明度：HTML 0.08，静态图10%到15%。
- 必须和净值图使用相同日期范围。不得单独截短回撤区间。

### 年度收益柱状图

- 图形：纵向柱状图。
- 固定颜色：正收益SERIES_MAIN，负收益SERIES_DEFENSE，基准SERIES_BENCH。
- 类别不超过12个。超过12个转横向条形图或表格。
- label只显示柱顶值，保留1位百分比。标签超过8个时只标注最大、最小和最新年份。

### 横向贡献条形图

- 图形：横向条形图。
- 固定颜色：正贡献SERIES_MAIN，负贡献SERIES_DEFENSE，成本项SERIES_RISK。
- 排序：按贡献值或贡献绝对值降序，排序口径必须在图题或图注中说明。
- HTML左边距80到120px；长名称不旋转，允许换行。
- 类别超过24个必须转表格或分页。

### 堆叠贡献图

- 图形：堆叠柱状图或堆叠面积图。
- 固定颜色：权益SERIES_MAIN，债券SERIES_BENCH，黄金SERIES_ACCENT，现金SERIES_NEUTRAL，另类SERIES_RISK，防御SERIES_DEFENSE。
- 堆叠项不超过6类。超过6类合并到其他项。
- 必须说明贡献是否可加总、是否包含交易成本、是否包含舍入误差。

### 热力图

- 图形：矩阵热力图。
- 相关性固定色阶：HEATMAP_NEG、PANEL、HEATMAP_POS。
- 收益敏感性固定色阶：SERIES_MAIN由浅到深三档浓度。
- 回撤敏感性固定色阶：SERIES_DEFENSE由浅到深三档浓度。
- 可见格不超过18×18。超过324格关闭格内数字，只保留tooltip或附表。超过900格必须抽样、分组或转Excel矩阵表。
- 必须显示visualMap或静态色阶说明。

### 散点图

- 图形：散点图。
- 固定颜色：主组合SERIES_MAIN，对照组合SERIES_BENCH，分组可使用SERIES_ACCENT、SERIES_DEFENSE、SERIES_RISK。
- X轴和Y轴必须是同一观察粒度的数值变量。点大小只能绑定规模、成交额、换手率或样本量。
- 样本少于10个转表格或条形图。样本超过300个降低点透明度至0.35到0.55并关闭全量label。
- 每个点必须有名称字段，静态图中重点点不超过8个。

### 环图

- 图形：环形图。
- 固定用途：静态结构占比。
- 类别不超过6个。超过6个先合并其他，合并后仍超过6个转表格。
- 不用于收益贡献、风险贡献、时间变化或正负混合数据。
- 环宽固定为外半径68%、内半径46%。标签显示名称和占比。

### 敏感性图

- 图形：单参数用折线图或条形图，双参数用热力图。
- 必须先放敏感性摘要表，列为参数、当前值、收益最高、回撤最浅、夏普最高、结论。
- 单参数图必须标注当前参数值。HTML用markLine，PPT和PDF用SERIES_ACCENT竖线或边框。
- 参数值少于4个转表格，不画线。超过12个优先横向条形图、热力图或Excel完整表。

## 降级规则

- 折线点少于4个时用表格或柱状图。
- 时间序列超过60个点时HTML开启dataZoom；静态格式抽样到8个以内主刻度。
- 类别超过12个时优先横向条形图；超过24个时转表格或分页。
- 饼图和环图类别超过6个时合并其他；仍超过6个转表格。
- 热力图超过324格关闭label；超过900格转Excel或分组矩阵。
- 明细数据超过50行时HTML、Word、PPT、PDF只放摘要，完整数据交给Excel或CSV。
- 图表需要双轴时必须说明双轴对象和单位；如果无法清楚说明，拆成两张图。

## HTML颜色注入方式

- 颜色单一真源在HTML的`:root`。JS的`THEME`用`getComputedStyle`读取CSS变量，不在JS里另存HEX。
- `SERIES_PALETTE`按 `theme-style.md` 的序列顺序排列，`normalizeChartOption`在图表未显式指定`color`时自动注入，单图不重复写颜色数组。
- 只有需要脱离默认序列的图表才显式写`color`，例如单序列相对净值图指定SERIES_ACCENT、单序列回撤图指定SERIES_DEFENSE、相关性热力图指定双向色阶。
- 涨跌方向色用UP_TONE和DOWN_TONE，不用SERIES_MAIN和SERIES_DEFENSE代替。序列色标识对象身份，涨跌色标识数值方向。
- 图表内不得出现裸HEX，全部经THEME取值。

## 素墨方案的无彩区分

素墨方案下六条序列全为灰阶，颜色不再承担区分功能，必须叠加形态区分。

- HTML把模板的`ACHROMATIC`常量置为true，`normalizeChartOption`按序列索引自动轮换线型、标记形状和柱状描边，图表调用代码不改。
- 线型和标记的轮换顺序以 `theme-style.md` 素墨小节的对照表为准，不在图表侧另行指定。
- 折线一律显示标记点。数据点超过14个时按间隔抽样显示标记，避免密集重叠。
- 柱状和堆叠柱用INK描边加不同深浅的填充区分，不用纯灰阶明度差区分。
- 散点按序列轮换标记形状，不靠点的深浅区分。
- 热力图和色阶图不适用形态区分，素墨方案下改用数值标注，或改成表格呈现。

## 验收清单

- 颜色是否全部来自 `theme-style.md` token。
- 同一对象颜色是否全篇一致。
- 图表类型是否来自本文件矩阵。
- 标题、轴名、单位、图例、样本区间、来源是否齐全。
- label数量是否达标。
- 网格线、图例位置、字号、尺寸是否符合目标格式。
- HTML图表是否离线渲染，容器是否有明确高度，resize是否统一注册。
- 静态格式是否不依赖tooltip传递关键信息。
- 素墨方案下序列是否同时用线型和标记区分，折线是否显示标记点。
