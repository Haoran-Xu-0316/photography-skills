# photo-privacy-redactor

## 功能定位

对用户确认的画面敏感区域进行不可逆实心遮挡。自动能力只提出正面人脸候选，不自动确认，也不承诺发现车牌、屏幕、票据或全部隐私内容。

## 两阶段流程

1. 检测候选、加入用户矩形或用户蒙版
2. 逐项确认候选后生成无损PNG，并人工检查漏检

## 输入与输出

输入为照片、矩形、蒙版和候选决策。输出遮挡PNG、二值蒙版、标记预览和复核JSON。GPS和EXIF风险不属于本Skill。

## 使用示例

用户矩形遮挡示例见[`examples/basic_usage.py`](examples/basic_usage.py)：

```python
result = run_example("source.jpg", "redaction-review")
```

## 验收重点

- 模糊、马赛克和半透明块均不符合不可逆要求
- 未处理候选时状态必须保持`needs-candidate-review`
- 未完成人工漏检检查时不得标记完成
- 透明输入会先合成到不透明白底

完整候选决策和状态定义见[`SKILL.md`](SKILL.md)。

