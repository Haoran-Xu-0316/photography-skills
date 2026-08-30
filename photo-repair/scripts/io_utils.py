"""统一的图像读写层。

对外只暴露两个概念：
    Image  : float32 RGB, 值域0-1, 线性光(未经gamma编码)
    Meta   : 拍摄参数与来源信息

所有修复模块都在线性光下工作，只有降噪和锐化在gamma编码后进行，
原因是人眼对噪声的感知发生在感知均匀的空间，在线性光下降噪会
过度处理暗部而放过亮部。
"""

import os

import cv2
import numpy as np

RAW_EXT = {
    ".arw",
    ".cr2",
    ".cr3",
    ".nef",
    ".nrw",
    ".dng",
    ".raf",
    ".orf",
    ".rw2",
    ".pef",
    ".srw",
    ".raw",
    ".3fr",
    ".iiq",
}
LDR_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp"}


class Meta(dict):
    """拍摄参数容器，缺失字段一律为None，调用方需自行判空。"""

    @property
    def iso(self):
        return self.get("iso")

    @property
    def is_raw(self):
        return self.get("is_raw", False)

    def describe(self):
        parts = []
        for key, fmt in (
            ("camera", "{}"),
            ("lens", "{}"),
            ("focal", "{}mm"),
            ("aperture", "f/{}"),
            ("shutter", "{}s"),
            ("iso", "ISO{}"),
        ):
            val = self.get(key)
            if val:
                parts.append(fmt.format(val))
        return "  ".join(parts) if parts else "无EXIF信息"


def srgb_to_linear(x):
    x = np.clip(x, 0.0, None)
    return np.where(x <= 0.04045, x / 12.92, ((x + 0.055) / 1.055) ** 2.4)


def linear_to_srgb(x):
    x = np.clip(x, 0.0, None)
    return np.where(x <= 0.0031308, x * 12.92, 1.055 * x ** (1 / 2.4) - 0.055)


def luminance(rgb):
    """Rec.709亮度，输入线性光RGB。"""
    return rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722


def _read_exif(path):
    meta = Meta()
    try:
        import exifread
    except ImportError:
        meta["exif_status"] = "dependency_unavailable"
        return meta
    try:
        with open(path, "rb") as fh:
            tags = exifread.process_file(fh, details=False)
    except Exception:
        return meta

    def grab(*names):
        for name in names:
            if name in tags:
                return tags[name]
        return None

    def ratio_to_float(tag):
        try:
            val = tag.values[0]
            return float(val.num) / float(val.den)
        except Exception:
            try:
                return float(tag.values[0])
            except Exception:
                return None

    iso = grab("EXIF ISOSpeedRatings", "EXIF PhotographicSensitivity")
    if iso is not None:
        try:
            meta["iso"] = int(str(iso).split(",")[0].strip("[] "))
        except Exception:
            pass

    model = grab("Image Model")
    make = grab("Image Make")
    if model is not None:
        meta["camera"] = f"{make} {model}".strip() if make else str(model)

    lens = grab("EXIF LensModel", "MakerNote LensType")
    if lens is not None:
        meta["lens"] = str(lens).strip()

    focal = grab("EXIF FocalLength")
    if focal is not None:
        val = ratio_to_float(focal)
        if val:
            meta["focal"] = int(round(val))

    aperture = grab("EXIF FNumber")
    if aperture is not None:
        val = ratio_to_float(aperture)
        if val:
            meta["aperture"] = round(val, 1)

    shutter = grab("EXIF ExposureTime")
    if shutter is not None:
        meta["shutter"] = str(shutter)

    return meta


def load(path, raw_cfg=None):
    """读取任意格式，返回(线性光float32 RGB, Meta)。"""
    raw_cfg = raw_cfg or {}
    ext = os.path.splitext(path)[1].lower()
    meta = _read_exif(path)
    meta["path"] = path
    meta["ext"] = ext

    if ext in RAW_EXT:
        import rawpy

        with rawpy.imread(path) as raw:
            rgb16 = raw.postprocess(
                gamma=(1, 1),  # 输出线性光，gamma由本流水线末端统一施加
                no_auto_bright=True,  # 关闭自动亮度，否则每张片子基准不一致
                output_bps=16,
                use_camera_wb=raw_cfg.get("use_camera_wb", True),
                output_color=rawpy.ColorSpace.sRGB,
                demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
                median_filter_passes=0,  # 禁用libraw自带处理，避免与本流水线叠加
                fbdd_noise_reduction=rawpy.FBDDNoiseReductionMode.Off,
            )
        img = rgb16.astype(np.float32) / 65535.0
        meta["is_raw"] = True
        meta["bit_depth"] = 16

        if raw_cfg.get("auto_exposure", True):
            pct = float(raw_cfg.get("exposure_percentile", 99.5))
            ref = np.percentile(luminance(img), pct)
            if ref > 1e-6:
                scale = float(np.clip(1.0 / ref, 0.2, 64.0))
                img = img * scale
                meta["auto_exposure_gain"] = round(scale, 3)
        return np.clip(img, 0.0, 1.0), meta

    if ext not in LDR_EXT:
        raise ValueError(f"不支持的格式: {ext}")

    bgr = cv2.imread(
        path, cv2.IMREAD_UNCHANGED | cv2.IMREAD_ANYDEPTH | cv2.IMREAD_COLOR
    )
    if bgr is None:
        raise OSError(f"读取失败: {path}")
    if bgr.dtype == np.uint16:
        arr = bgr.astype(np.float32) / 65535.0
        meta["bit_depth"] = 16
    else:
        arr = bgr.astype(np.float32) / 255.0
        meta["bit_depth"] = 8
    rgb = cv2.cvtColor(arr, cv2.COLOR_BGR2RGB)
    meta["is_raw"] = False
    meta["encoded_input"] = True
    return srgb_to_linear(rgb).astype(np.float32), meta


def resolve_output_path(path, meta, out_cfg=None):
    """根据来源与输出配置解析最终扩展名，不写文件。"""
    out_cfg = out_cfg or {}
    fmt = out_cfg.get("format", "auto")
    if fmt == "auto":
        fmt = "tiff" if meta.get("is_raw") else "jpg"
    base = os.path.splitext(path)[0]
    if fmt in ("tiff", "tif", "png"):
        return f"{base}.{'tif' if fmt.startswith('tif') else 'png'}"
    if fmt in ("jpg", "jpeg"):
        return f"{base}.jpg"
    raise ValueError(f"不支持的输出格式: {fmt}")


def save(path, rgb_linear, meta, out_cfg=None):
    """写出结果。RAW来源默认16位TIFF，JPEG来源沿用JPEG。"""
    out_cfg = out_cfg or {}
    target = resolve_output_path(path, meta, out_cfg)
    source = meta.get("path")
    if source and os.path.realpath(source) == os.path.realpath(target):
        raise ValueError("修复输出路径不得与源图相同")
    if os.path.exists(target):
        raise FileExistsError(f"拒绝覆盖既有修复输出: {target}")

    encoded = linear_to_srgb(np.clip(rgb_linear, 0.0, 1.0))
    os.makedirs(os.path.dirname(os.path.abspath(target)) or ".", exist_ok=True)
    if target.lower().endswith((".tif", ".png")):
        out = (np.clip(encoded, 0, 1) * 65535.0 + 0.5).astype(np.uint16)
        written = cv2.imwrite(target, cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
    else:
        out = (np.clip(encoded, 0, 1) * 255.0 + 0.5).astype(np.uint8)
        quality = int(out_cfg.get("jpeg_quality", 95))
        written = cv2.imwrite(
            target,
            cv2.cvtColor(out, cv2.COLOR_RGB2BGR),
            [cv2.IMWRITE_JPEG_QUALITY, quality],
        )
        if out_cfg.get("copy_exif", True) and meta.get("ext") in (".jpg", ".jpeg"):
            meta["exif_copy_status"] = _copy_exif(meta["path"], target)
        else:
            meta["exif_copy_status"] = "not_applicable"
    if not written:
        raise OSError(f"写入修复输出失败: {target}")
    return target


def _copy_exif(src, dst):
    try:
        import piexif

        exif = piexif.load(src)
        has_metadata = any(
            exif.get(section) for section in ("0th", "Exif", "GPS", "Interop", "1st")
        ) or bool(exif.get("thumbnail"))
        if not has_metadata:
            return "not_present"
        exif.pop("thumbnail", None)
        exif["1st"] = {}
        piexif.insert(piexif.dump(exif), dst)
        return "preserved"
    except Exception as exc:
        return f"failed: {type(exc).__name__}: {exc}"


def to_encoded_u8(rgb_linear):
    return (
        np.clip(linear_to_srgb(np.clip(rgb_linear, 0, 1)), 0, 1) * 255 + 0.5
    ).astype(np.uint8)
