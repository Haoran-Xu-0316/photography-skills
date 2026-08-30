# 参数参考

配置文件在`assets/default.yaml`。程序化接口通过`overrides`字典覆盖点路径参数，`auto=False`关闭自动推荐并严格使用配置与覆盖值。

## 覆盖示例

```python
result = repair_photos(
    input_paths,
    output_directory,
    preset="wildlife",
    overrides={
        "denoise.luma_strength": 0.6,
        "vignette.strength": 0.85,
        "sharpen.amount": 0.5,
    },
)
```

## raw

仅对RAW输入生效。

| 参数 | 默认 | 说明 |
|---|---|---|
| use_camera_wb | true | 用相机白平衡，false则用自动白平衡 |
| auto_exposure | true | 线性解码后按分位数归一化亮度。关闭则输出很暗，因为未施加自动提亮 |
| exposure_percentile | 99.5 | 调低画面变亮，调高变暗。欠曝素材可调到98 |

RAW解码时已关闭libraw自带的中值滤波与FBDD降噪，避免与本流水线叠加。

## output

| 参数 | 默认 | 说明 |
|---|---|---|
| format | auto | auto表示RAW出16位TIFF、JPEG出JPEG。可强制jpg、tiff、png |
| jpeg_quality | 95 | 低于92开始出现可见压缩痕迹 |
| copy_exif | true | 仅JPEG到JPEG时生效 |

## hotpixel

| 参数 | 默认 | 说明 |
|---|---|---|
| enabled | true | |
| k | 8.0 | 判定阈值，单位是局部噪声尺度的倍数。调小抓得多但误伤增加 |
| max_fix_ratio | 0.0008 | 单通道最多修复的像素比例，防止误伤星点等细小高光 |

星空题材务必用`astro`预设，它把k提到14、上限压到0.0002，否则会把暗星当热噪点抹掉。

## ca

横向色差。

| 参数 | 默认 | 说明 |
|---|---|---|
| enabled | true | |
| strength | 1.0 | 校正比例，1.0为完全校正 |
| min_shift_px | 0.4 | 边角位移低于此值不处理，肉眼不可见 |

诊断报告里的边角位移低于0.4像素时自动推荐会关闭该模块。

## vignette

| 参数 | 默认 | 说明 |
|---|---|---|
| enabled | true | |
| strength | 1.0 | 1.0完全拉平。0.85到0.9通常更自然，全补会让画面显得平 |
| max_gain | 3.5 | 增益上限。极端暗角全补会把边角噪声放大到不可用 |
| min_confidence | 0.35 | 置信度低于此值判定为构图明暗不均而非暗角 |
| use_lens_profile | true | 优先使用平场校准模型 |
| auto_strength | true | 置信度不足时按置信度衰减校正强度，而非直接放弃 |

置信度由方向性对称性与拟合残差加权得出。侧光、天空亮地面暗这类构图会拉低置信度，此时校正强度自动衰减。想强制全量校正，同时设`vignette.auto_strength=false`和`vignette.min_confidence=0`。

## denoise

| 参数 | 默认 | 说明 |
|---|---|---|
| enabled | true | |
| luma_method | nlm | nlm、bilateral、bm3d。bilateral快一个量级但保边差，bm3d质量最好但慢且需另装 |
| luma_strength | 0.9 | 超过1.2出现塑料感 |
| chroma_strength | 3.0 | 可以给到4以上，几乎不损细节 |
| detail_recovery | 0.35 | 按边缘强度回补被误伤的纹理，0到1 |
| chroma_downscale | 2 | 色度降采样倍数，提速用，画质影响可忽略 |
| iso_prior_weight | 0.6 | 实测噪声与ISO先验的兜底权重 |
| sigma_floor | 0.0022 | 噪声低于此值直接跳过降噪 |
| patch_size | 5 | NLM块尺寸 |
| patch_distance | 6 | NLM搜索半径，调大更干净但明显变慢 |

自动推荐按实测亮度sigma分四档：

| 实测sigma | luma_strength | chroma_strength | detail_recovery |
|---|---|---|---|
| < 0.006 | 0.0 | 1.5 | 默认 |
| 0.006到0.014 | 0.75 | 2.5 | 0.45 |
| 0.014到0.030 | 0.95 | 3.2 | 0.35 |
| > 0.030 | 1.15 | 4.0 | 0.25 |

## sharpen

| 参数 | 默认 | 说明 |
|---|---|---|
| enabled | true | |
| amount | 0.35 | 0关闭，0.6以上易出白边 |
| radius | 1.0 | 高斯半径。长焦细节多时用0.8 |
| threshold | 0.008 | 弱于此强度的边缘不锐化，避免放大残留噪声 |

自动推荐按`0.25 + 实测sigma × 6`给出，钳制在0.25到0.6。降噪越重越需要补锐。

## 预设

| 预设 | 场景 | 主要改动 |
|---|---|---|
| high_iso | 室内夜间手持 | 亮度1.1，色度4.0，回补0.25，锐化0.45 |
| landscape | 低感风光 | 亮度0.5，色度2.0，回补0.55，暗角0.8，锐化0.4 |
| astro | 星空 | 坏点k=14上限0.0002，亮度0.8，色度5.0，回补0.15，暗角1.0增益上限5.0，关锐化 |
| wildlife | 打鸟 | 亮度0.85，色度3.5，回补0.5，锐化0.5半径0.8 |

预设定义在`assets/default.yaml`末尾，可直接增改。
