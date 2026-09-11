# 图片示例总览

## 新增多题材案例

下列入口包含实际输入、结果、参数与局限。工作流模拟不是实拍能力认证，待复核状态不被改写成通过。

| Skill | 多题材图片 |
|---|---|
| city-map-diorama | [案例与实际图片](city-map-diorama/examples/cases/README.md) |
| cyanotype-botanical-print | [案例与实际图片](cyanotype-botanical-print/examples/cases/README.md) |
| object-exploded-plate | [案例与实际图片](object-exploded-plate/examples/cases/README.md) |
| photo-bracket-fusion | [案例与实际图片](photo-bracket-fusion/examples/cases/README.md) |
| photo-color-grade | [案例与实际图片](photo-color-grade/examples/cases/README.md) |
| photo-composition-crop | [案例与实际图片](photo-composition-crop/examples/cases/README.md) |
| photo-cull | [案例与实际图片](photo-cull/examples/cases/README.md) |
| photo-focus-stacker | [案例与实际图片](photo-focus-stacker/examples/cases/README.md) |
| photo-geometry-corrector | [案例与实际图片](photo-geometry-corrector/examples/cases/README.md) |
| photo-light-sculptor | [案例与实际图片](photo-light-sculptor/examples/cases/README.md) |
| photo-miniature-diorama | [案例与实际图片](photo-miniature-diorama/examples/cases/README.md) |
| photo-output-preflight | [案例与实际图片](photo-output-preflight/examples/cases/README.md) |
| photo-panorama-stitcher | [案例与实际图片](photo-panorama-stitcher/examples/cases/README.md) |
| photo-print-layout | [案例与实际图片](photo-print-layout/examples/cases/README.md) |
| photo-privacy-redactor | [案例与实际图片](photo-privacy-redactor/examples/cases/README.md) |
| photo-repair | [案例与实际图片](photo-repair/examples/cases/README.md) |
| photo-series-editor | [案例与实际图片](photo-series-editor/examples/cases/README.md) |
| photo-to-3d | [案例与实际图片](photo-to-3d/examples/cases/README.md) |
| surreal-scale-cinema | [案例与实际图片](surreal-scale-cinema/examples/cases/README.md) |
| textile-storybook-scene | [案例与实际图片](textile-storybook-scene/examples/cases/README.md) |

新增能力另见[人工校准](photo-color-grade/examples/calibration/README.md)、[保护区域裁切](photo-composition-crop/examples/protected/README.md)和[人脸候选确认](photo-privacy-redactor/examples/candidate-review/README.md)。

### 人工校准示例

![人工校准](photo-color-grade/examples/calibration/portrait/output/input_calibration_preview.jpg)

### 新风格选览

![赤狐微缩](photo-miniature-diorama/examples/cases/fox/refined.png)

![巴黎地图](city-map-diorama/examples/cases/paris/candidate.png)

![钢笔组件](object-exploded-plate/examples/cases/pen/refined.png)

![布艺叙事](textile-storybook-scene/examples/cases/rainy-city/candidate.png)

![银杏蓝晒](cyanotype-botanical-print/examples/cases/ginkgo/candidate.png)

![尺度超现实](surreal-scale-cinema/examples/cases/snow-glasses/candidate.png)

## 基础案例


20个Skill，各自保留功能边界。以下处理图由原Python实现实际输出；生成式图片由生图工具产生。对照板只是排版，没有另行美化处理结果。

## 摄影处理与受控回归

### photo-cull

技术筛片。[输入、复现及限制](photo-cull/examples/README.md)。

![技术筛片](photo-cull/examples/comparison.jpg)

### photo-repair

噪声修复与纹理取舍。[输入、复现及限制](photo-repair/examples/README.md)。

![噪声修复与纹理取舍](photo-repair/examples/comparison.jpg)

### photo-color-grade

自动校色的边界案例。[输入、复现及限制](photo-color-grade/examples/README.md)。

![自动校色的边界案例](photo-color-grade/examples/comparison.jpg)

### photo-light-sculptor

花瓶主体局部光影。[输入、复现及限制](photo-light-sculptor/examples/README.md)。

![花瓶主体局部光影](photo-light-sculptor/examples/comparison.jpg)

### photo-composition-crop

同一主体的三种画幅。[输入、复现及限制](photo-composition-crop/examples/README.md)。

![同一主体的三种画幅](photo-composition-crop/examples/comparison.jpg)

### photo-series-editor

三图视觉节奏草案。[输入、复现及限制](photo-series-editor/examples/README.md)。

![三图视觉节奏草案](photo-series-editor/examples/comparison.jpg)

### photo-output-preflight

网页副本与GPS清理。[输入、复现及限制](photo-output-preflight/examples/README.md)。

![网页副本与GPS清理](photo-output-preflight/examples/comparison.jpg)

### photo-privacy-redactor

显式区域的实心遮挡。[输入、复现及限制](photo-privacy-redactor/examples/README.md)。

![显式区域的实心遮挡](photo-privacy-redactor/examples/comparison.jpg)

### photo-geometry-corrector

已知倾角校正。[输入、复现及限制](photo-geometry-corrector/examples/README.md)。

![已知倾角校正](photo-geometry-corrector/examples/comparison.jpg)

### photo-bracket-fusion

模拟曝光序列及风险警告。[输入、复现及限制](photo-bracket-fusion/examples/README.md)。

![模拟曝光序列及风险警告](photo-bracket-fusion/examples/comparison.jpg)

### photo-panorama-stitcher

已知重叠的拼接回归。[输入、复现及限制](photo-panorama-stitcher/examples/README.md)。

![已知重叠的拼接回归](photo-panorama-stitcher/examples/comparison.jpg)

### photo-focus-stacker

互补清晰区域的堆栈回归。[输入、复现及限制](photo-focus-stacker/examples/README.md)。

![互补清晰区域的堆栈回归](photo-focus-stacker/examples/comparison.jpg)

### photo-to-3d

手工深度驱动的2.5D视差。[输入、复现及限制](photo-to-3d/examples/README.md)。

![手工深度驱动的2.5D视差](photo-to-3d/examples/comparison.jpg)

### photo-print-layout

A4四格印刷拼版。[输入、复现及限制](photo-print-layout/examples/README.md)。

![A4四格印刷拼版](photo-print-layout/examples/comparison.jpg)

## 六种生成式风格

### photo-miniature-diorama

保留照片的场景关系，重建为独立微缩景观图片。不是深度图或3D网格。[提示与视觉复核](photo-miniature-diorama/README.md)。

![白底写实微缩景观](photo-miniature-diorama/examples/garden-poster.png)

### city-map-diorama

城市从复古地图连续升起，不是独立底座模型；不用于导航。[提示与视觉复核](city-map-diorama/README.md)。

![地图立体城市](city-map-diorama/examples/sydney-map-diorama.png)

### object-exploded-plate

突出共同装配轴、组件层级和材质，不作为真实工程结构。[提示与视觉复核](object-exploded-plate/README.md)。

![工业组件爆炸图](object-exploded-plate/examples/example.png)

### textile-storybook-scene

用毛毡、针脚和织物构成角色与场景，不是给照片套滤镜。[提示与视觉复核](textile-storybook-scene/README.md)。

![布艺刺绣故事](textile-storybook-scene/examples/example.png)

### cyanotype-botanical-print

深蓝底与浅色植物负像的平面接触印相，不是普通蓝调照片。[提示与视觉复核](cyanotype-botanical-print/README.md)。

![植物蓝晒印相](cyanotype-botanical-print/examples/example.png)

### surreal-scale-cinema

一个巨大日常物置于可信摄影环境，以尺度异常形成叙事。[提示与视觉复核](surreal-scale-cinema/README.md)。

![超现实尺度电影画面](surreal-scale-cinema/examples/example.png)
