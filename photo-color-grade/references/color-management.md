# 色彩管理与格式

## 工作空间

内置引擎把常见JPEG、PNG和TIFF视为sRGB编码数据进行确定性处理。存在ICC配置时原样保留，但内置版本不执行跨配置文件的精确显示变换。

需要严格Adobe RGB、Display P3、相机DCP、ACES或印刷ICC工作流时，应安装OpenColorIO或调用可靠的色彩管理程序，并在报告中记录输入、工作和输出色彩空间。没有实际转换时不得声称完成了色彩管理。

## 位深

- JPEG以8bit处理和输出，保留EXIF与ICC，默认最高质量和4:4:4采样。
- 16bit PNG与TIFF尽量保持16bit输出，避免中间反复量化。
- RAW使用`rawpy`进行完整解码时输出16bit TIFF，并记录相机白平衡和解码参数。
- 缺少`rawpy`时直接失败，不使用内嵌JPEG冒充RAW处理。

## 非破坏性

原图始终只读。输出文件使用`_corrected`、`_graded`或`_matched`后缀，同时生成配方和验证JSON。输出已存在时默认失败，只有用户明确授权后才能覆盖。

Lightroom或Adobe Camera Raw的XMP、Capture One调整和DCP配置并不等价。没有针对目标软件验证时，只交付通用配方JSON，不生成声称兼容的伪XMP。

## 导出建议

- 网站与普通屏幕：sRGB JPEG，质量95以上。
- 后续精修：16bit TIFF，保留ICC。
- 印刷：根据印厂ICC进行软打样和转换，不能仅改变文件扩展名。
- 存档：保留原RAW、配方JSON和最终16bit母版。

