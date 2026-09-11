# Photography Skills

一组面向摄影与图像创作的通用Agent Skills，覆盖照片处理、计算摄影、立体化、交付质检、印刷输出及具有独立视觉定位的生图风格。

这些Skill以开放目录结构组织，不绑定特定模型或厂商。每个目录提供面向读者的`README.md`和面向Agent的`SKILL.md`。14个Python处理类均附输入、实际输出、可复现函数、对照图与验证记录；6个生成式风格均附真实生成图片及提示，不添加空脚本。

直接浏览[20个Skill的图片示例](GALLERY.md)。新增动物、城市、人物42组处理案例，6种生图风格各有至少3例；另有人工校准、主体保护裁切及人脸候选确认示例。底图专门生成，既有庭园使用CC0摄影。模拟曝光、焦点序列、同图裁片和手工深度均明确标注，不冒充实拍或模型推理。

## Skill清单

| Skill | 功能定位 | 示例 |
|---|---|---|
| [`photo-cull`](photo-cull/README.md) | 基于清晰度、曝光和重复度完成技术筛片，确认后可写入XMP标记 | [图片与复现](photo-cull/examples/README.md) |
| [`photo-repair`](photo-repair/README.md) | 修复噪点、镜头暗角、横向色差、坏点和热噪点 | [图片与复现](photo-repair/examples/README.md) |
| [`photo-color-grade`](photo-color-grade/README.md) | 完成全局校色、创意调色、参考色彩匹配和系列色彩统一 | [图片与复现](photo-color-grade/examples/README.md) |
| [`photo-light-sculptor`](photo-light-sculptor/README.md) | 通过主体蒙版和局部EV调整完成非生成式光影塑形 | [图片与复现](photo-light-sculptor/examples/README.md) |
| [`photo-composition-crop`](photo-composition-crop/README.md) | 按显著性、焦点和目标比例生成可复核裁切方案 | [图片与复现](photo-composition-crop/examples/README.md) |
| [`photo-series-editor`](photo-series-editor/README.md) | 为已选照片建立组照顺序、视觉节奏和叙事结构 | [图片与复现](photo-series-editor/examples/README.md) |
| [`photo-output-preflight`](photo-output-preflight/README.md) | 检查尺寸、格式、色彩空间、透明度、元数据和文件完整性 | [图片与复现](photo-output-preflight/examples/README.md) |
| [`photo-privacy-redactor`](photo-privacy-redactor/README.md) | 对确认的敏感区域进行不可逆画面遮挡并生成复核材料 | [图片与复现](photo-privacy-redactor/examples/README.md) |
| [`photo-geometry-corrector`](photo-geometry-corrector/README.md) | 校正水平线、四点透视和基于标定参数的镜头畸变 | [图片与复现](photo-geometry-corrector/examples/README.md) |
| [`photo-bracket-fusion`](photo-bracket-fusion/README.md) | 对真实包围曝光序列进行配准、曝光融合和鬼影风险检测 | [图片与复现](photo-bracket-fusion/examples/README.md) |
| [`photo-panorama-stitcher`](photo-panorama-stitcher/README.md) | 拼接具有真实重叠区域的横向或纵向全景照片 | [图片与复现](photo-panorama-stitcher/examples/README.md) |
| [`photo-focus-stacker`](photo-focus-stacker/README.md) | 合成不同焦平面照片并报告运动和对焦呼吸风险 | [图片与复现](photo-focus-stacker/examples/README.md) |
| [`photo-to-3d`](photo-to-3d/README.md) | 从单张照片生成深度图、2.5D视差作品和浅浮雕模型 | [图片与复现](photo-to-3d/examples/README.md) |
| [`photo-miniature-diorama`](photo-miniature-diorama/README.md) | 将照片重建为白底写实微缩景观图片，可选原照对照海报，不输出3D网格 | [图片与说明](photo-miniature-diorama/README.md#实际图片示例) |
| [`city-map-diorama`](city-map-diorama/README.md) | 从城市主题生成与复古地图连续衔接的立体城市图片 | [图片与说明](city-map-diorama/README.md) |
| [`object-exploded-plate`](object-exploded-plate/README.md) | 工业产品组件爆炸图，突出结构层级与真实材质，不作为制造依据 | [图片与说明](object-exploded-plate/README.md) |
| [`textile-storybook-scene`](textile-storybook-scene/README.md) | 全画面以毛毡、布贴与刺绣表达角色动作和故事 | [图片与说明](textile-storybook-scene/README.md) |
| [`cyanotype-botanical-print`](cyanotype-botanical-print/README.md) | 深蓝与浅色植物负像的平面蓝晒印相，不是蓝色照片滤镜 | [图片与说明](cyanotype-botanical-print/README.md) |
| [`surreal-scale-cinema`](surreal-scale-cinema/README.md) | 一个尺度异常置于可信现实环境，形成宽幅电影叙事 | [图片与说明](surreal-scale-cinema/README.md) |
| [`photo-print-layout`](photo-print-layout/README.md) | 按物理纸张、边距、出血和装订安全区生成印刷拼版 | [图片与复现](photo-print-layout/examples/README.md) |

## 使用方式

选择所需Skill并复制完整目录到目标Agent运行时的Skills目录。不要只复制`SKILL.md`，否则脚本、参考资料和模板可能缺失。

运行时应满足对应`requirements.txt`和`SKILL.md`中的运行契约。多数图像处理流程可以完全离线执行；`photo-to-3d`自动估深需要本地模型权重，默认不主动联网下载。

没有图像查看或文档渲染能力时，可以生成诊断、配方或待复核产物，但不能将视觉质量标记为最终完成。

## 目录约定

- `SKILL.md`：能力边界、工作流、输入输出和验收规则
- `README.md`：面向GitHub读者的功能说明和使用入口
- `examples/`：程序类提供input、output、reproduce.py和验证记录；风格类提供提示与生成图
- `scripts/`：确定性处理脚本
- `references/`：算法、参数和操作规范
- `assets/`：离线模板与静态资源
- `requirements.txt`：Python依赖

跨模型兼容说明见[PORTABILITY.md](PORTABILITY.md)。

## 质量保证

发布前会在本地核对Skill清单、目录名与`name`一致性、运行契约、说明与图片示例完整性、资源引用、依赖声明、厂商绑定和机器路径绑定。测试源文件只保留在本地，不随仓库发布。

实测推动了人工校准、运动光度补偿、主体保护裁切、按画幅校验网格及检测依赖诊断等升级。检查输入哈希、实际图像、动画与PDF渲染，同时保留待复核和规格阻断状态。能力边界及未覆盖路径见[审计记录](AUDIT.md)。
