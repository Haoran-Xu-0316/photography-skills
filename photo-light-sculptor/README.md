# photo-light-sculptor

## 功能定位

利用主体蒙版和同通道EV调整重新分配局部亮度，引导视线并强化照片已有光影。它不会生成新光源，也不改变全局综合色彩。

## 三种模式

- `focus`：主体轻微提亮，背景适度压暗
- `depth`：强化照片已有的局部明暗纹理
- `balance`：缓和局部过亮、过暗和左右失衡

## 输入与输出

输入为单张照片，可选用户蒙版。输出成片、主体蒙版、16bit EV光照图、对照板、配方和验证报告。

## 使用示例

用户蒙版优先的示例见[`examples/basic_usage.py`](examples/basic_usage.py)：

```python
result = run_example("portrait.jpg", "light-review", "subject-mask.png")
```

## 图片示例

[输入、参数、实际输出及验证边界](examples/README.md)。随附[可复现调用](examples/reproduce.py)，不是只有调用占位符。

![输入与实际处理结果](examples/comparison.jpg)

## 验收重点

- 自动蒙版置信度不足时必须停止
- 查看主体蒙版是否漏选或误选
- EV调整不得产生明显光晕和色相漂移
- 视觉检查前结果只能标记为待复核

完整执行规范和方法说明见[`SKILL.md`](SKILL.md)。
