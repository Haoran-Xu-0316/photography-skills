"""筛片专用的快速读取层。

筛片要处理的是几百到几千张，全量解码RAW不现实，一张45MP的RAW完整
demosaic要两三秒，两千张就是一个多小时。相机在RAW里都嵌了一张全尺寸
或接近全尺寸的JPEG预览，机内已经过完整处理，用来判断对焦、构图、
曝光完全够用，读取只要几十毫秒，快两个数量级。

预览只用于评估，不用于输出。筛片的产物是XMP边车文件和报告，原始
文件一个字节都不动。
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
    ".3fr",
    ".iiq",
}
LDR_EXT = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".webp", ".bmp", ".heic"}
SUPPORTED = RAW_EXT | LDR_EXT

# 所有度量都在统一长边下计算。清晰度指标本质是以像素为单位的，
# 不统一尺度就无法跨图比较。实测1400与2000的峰值宽度读数差异在0.3%以内，
# 但耗时差三倍，两千张的批量下这个差别是十分钟和半小时的区别
WORK_LONG_SIDE = 1400


# 本工具与photo-repair的输出目录名。扫描时必须排除，否则第二次运行会把
# 上一次生成的废片印象图当成输入，统计数越跑越多
EXCLUDE_DIRS = {"cull", "repaired", "selected_export", ".cache"}


def list_images(target, exclude_dirs=None):
    if os.path.isfile(target):
        return [target]
    exclude = set(exclude_dirs or EXCLUDE_DIRS)
    out = []
    for root, dirs, files in os.walk(target):
        dirs[:] = [d for d in dirs if d not in exclude and not d.startswith(".")]
        for name in sorted(files):
            if name.startswith("."):
                continue
            if os.path.splitext(name)[1].lower() in SUPPORTED:
                out.append(os.path.join(root, name))
    return sorted(out)


def read_exif(path):
    meta = {"path": path, "name": os.path.basename(path)}
    # 时间戳先用文件修改时间兜底。缺少EXIF时间会让连拍分组退化成纯哈希匹配，
    # 同一场景的不同构图会被错误合并成一组
    try:
        meta["timestamp"] = os.path.getmtime(path)
        meta["time_source"] = "mtime"
    except OSError:
        pass
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

    def ratio(tag):
        try:
            v = tag.values[0]
            return float(v.num) / float(v.den)
        except Exception:
            try:
                return float(tag.values[0])
            except Exception:
                return None

    def grab(*names):
        for n in names:
            if n in tags:
                return tags[n]
        return None

    t = grab("EXIF DateTimeOriginal", "Image DateTime")
    if t is not None:
        meta["datetime"] = str(t)
        ts = _parse_time(str(t))
        if ts:
            meta["timestamp"] = ts
            meta["time_source"] = "exif"

    iso = grab("EXIF ISOSpeedRatings", "EXIF PhotographicSensitivity")
    if iso is not None:
        try:
            meta["iso"] = int(str(iso).split(",")[0].strip("[] "))
        except Exception:
            pass

    model, make = grab("Image Model"), grab("Image Make")
    if model is not None:
        meta["camera"] = f"{make} {model}".strip() if make else str(model)
    lens = grab("EXIF LensModel", "MakerNote LensType")
    if lens is not None:
        meta["lens"] = str(lens).strip()

    f = grab("EXIF FocalLength")
    if f is not None:
        v = ratio(f)
        if v:
            meta["focal"] = int(round(v))
    a = grab("EXIF FNumber")
    if a is not None:
        v = ratio(a)
        if v:
            meta["aperture"] = round(v, 1)
    s = grab("EXIF ExposureTime")
    if s is not None:
        meta["shutter"] = str(s)
        meta["shutter_sec"] = _parse_shutter(str(s))
    return meta


def _parse_time(text):
    import datetime

    for fmt in ("%Y:%m:%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.datetime.strptime(text.strip(), fmt).timestamp()
        except ValueError:
            continue
    return None


def _parse_shutter(text):
    text = text.strip()
    try:
        if "/" in text:
            a, b = text.split("/")
            return float(a) / float(b)
        return float(text)
    except Exception:
        return None


def load_gray(path, long_side=WORK_LONG_SIDE):
    """返回(灰度float32 0-1, BGR缩略图uint8, 来源标记)。"""
    ext = os.path.splitext(path)[1].lower()
    bgr, source = None, "file"

    if ext in RAW_EXT:
        bgr = _raw_preview(path)
        source = "embedded_preview"
        if bgr is None:
            bgr = _raw_halfsize(path)
            source = "half_demosaic"
    if bgr is None:
        bgr = cv2.imread(path, cv2.IMREAD_COLOR)
        source = "file"
    if bgr is None:
        if ext == ".heic":
            raise OSError(
                f"OpenCV不支持HEIC: {os.path.basename(path)}。"
                f"先用系统工具批量转为JPEG，或安装pillow-heif"
            )
        raise OSError(f"读取失败: {path}")

    h, w = bgr.shape[:2]
    scale = long_side / max(h, w)
    if scale < 1.0:
        # 缩小统一用INTER_AREA。用INTER_LINEAR会引入混叠，
        # 把混叠产生的高频当成锐度，糊片反而可能得高分
        bgr = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    elif scale > 1.0:
        # 预览图本身偏小的情况不放大，放大不会凭空产生细节，
        # 只会让边缘宽度指标整体偏大，破坏跨图可比性
        scale = 1.0

    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32) / 255.0
    return (
        gray,
        bgr,
        {
            "source": source,
            "work_scale": round(float(scale), 4),
            "orig_size": f"{w}x{h}",
        },
    )


def _raw_preview(path):
    try:
        import rawpy

        with rawpy.imread(path) as raw:
            thumb = raw.extract_thumb()
        if thumb.format == rawpy.ThumbFormat.JPEG:
            arr = np.frombuffer(thumb.data, np.uint8)
            return cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if thumb.format == rawpy.ThumbFormat.BITMAP:
            return cv2.cvtColor(thumb.data, cv2.COLOR_RGB2BGR)
    except Exception:
        return None
    return None


def _raw_halfsize(path):
    """没有内嵌预览时的回退，半尺寸解码仍比全解码快数倍。"""
    try:
        import rawpy

        with rawpy.imread(path) as raw:
            rgb = raw.postprocess(
                half_size=True, use_camera_wb=True, no_auto_bright=False, output_bps=8
            )
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    except Exception:
        return None
