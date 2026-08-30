"""清晰度与模糊类型。

不用拉普拉斯方差。它是最常见的做法，但有两个致命问题：数值随画面
内容剧烈变化，杂乱背景的糊片能轻松超过干净背景的锐片；浅景深人像
全图方差很低，会被判成废片，而这恰恰是最该保留的片子。

改用边缘宽度。一条被模糊到w像素宽的边，其最大梯度约等于对比度除以w，
因此局部对比度除以梯度幅值就能反推出边缘宽度，单位是像素，且分子
分母同量纲，对比度被约掉，与画面内容基本无关。

再按方向分别测量，就能顺带区分抖动和失焦：运动模糊只沿运动方向展宽，
垂直于运动方向的边缘依然锐利，四个方向的宽度差异显著；失焦是各向
同性的，四个方向一样宽。两者的补救方式完全不同，抖动无解只能删，
轻度失焦有时还能靠锐化抢救。
"""

import cv2
import numpy as np

# 0度、45度、90度、135度四个采样方向
_DIRS = (0, 45, 90, 135)


def _line_kernel(angle, reach=4):
    """按空间距离构造方向核，保证各方向的测量跨度相同。

    早期版本按像素步数构造，对角方向每步跨1.414像素，导致45度和135度的
    测量窗口比0度和90度长四成。后果是所有图的模糊角都报45度，各向异性
    有0.17的虚假本底，抖动判别完全失效。方向核必须按空间距离等距。
    """
    size = int(reach) * 2 + 1
    k = np.zeros((size, size), np.uint8)
    c = size // 2
    rad = np.deg2rad(angle)
    dx, dy = np.cos(rad), -np.sin(rad)
    for t in np.arange(-reach, reach + 1e-9, 0.25):
        x, y = int(round(c + dx * t)), int(round(c + dy * t))
        if 0 <= x < size and 0 <= y < size:
            k[y, x] = 1
    return k


_KERNELS = {(a, r): _line_kernel(a, r) for a in _DIRS for r in (4, 10)}


def _siemens_star(size=513, spokes=48, softness=0.6):
    """西门子星，各朝向等概率出现，是标准分辨率靶。

    用单条直边标定不准。方形像素对斜向边缘的采样本就更差，而单条参考边
    只能反映一个朝向的情况，标出来的系数在自然图像上仍留有三成残余偏差。
    星形靶各朝向均匀覆盖，标定后四组读数才真正对齐。
    """
    c = size // 2
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32)
    dx, dy = xx - c, yy - c
    theta = np.arctan2(dy, dx)
    radius = np.hypot(dx, dy)
    wave = np.sin(theta * spokes)
    star = 1.0 / (1.0 + np.exp(-wave * radius / (softness * spokes)))
    # 中心辐条汇聚处必然混叠，外圈超出画面，都要排除
    ring = (radius > size * 0.22) & (radius < size * 0.46)
    img = np.where(ring, star * 0.8 + 0.1, 0.5).astype(np.float32)
    return img, ring


def _calibrate(edge_percentile=90, strong_percentile=80):
    """标定各方向的宽度基准，使完美锐边在四个方向读数一致。"""
    img, ring = _siemens_star()
    gx = cv2.Sobel(img, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(img, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    mag = np.hypot(gx, gy)
    strong = ring & (mag > np.percentile(mag[ring], strong_percentile))
    orient = np.degrees(np.arctan2(-gy, gx)) % 180.0
    bin_idx = np.round(orient / 45.0).astype(np.int32) % 4

    floors = {}
    for i, angle in enumerate(_DIRS):
        wm, valid = _width_map(img, angle, reach=4, min_contrast=0.02)
        sel = strong & (bin_idx == i) & valid
        vals = wm[sel]
        floors[angle] = (
            float(np.percentile(vals, 100 - edge_percentile))
            if vals.size >= 100
            else 2.0
        )
    return floors


_FLOORS = None


def _floors():
    global _FLOORS
    if _FLOORS is None:
        _FLOORS = _calibrate()
    return _FLOORS


def _directional_derivative(gray, angle):
    rad = np.deg2rad(angle)
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    return gx * np.cos(rad) - gy * np.sin(rad)


def _width_map(gray, angle, reach=4, min_contrast=0.06):
    """沿指定方向的边缘宽度图，单位像素。无有效边缘处为NaN。"""
    k = _KERNELS[(angle, reach)]
    hi = cv2.dilate(gray, k)
    lo = cv2.erode(gray, k)
    contrast = hi - lo
    grad = np.abs(_directional_derivative(gray, angle))

    valid = (contrast > min_contrast) & (grad > 1e-4)
    width = np.full(gray.shape, np.nan, np.float32)
    width[valid] = contrast[valid] / grad[valid]
    # 宽度上限取测量跨度。超过说明这条边比窗口还宽，测不准，
    # 保留为上限值而非丢弃，否则严重失焦的图会因为无有效边缘被判为锐
    return np.clip(width, 0.5, float(2 * reach + 1)), valid


def measure(
    gray, tiles=12, edge_percentile=90, strong_percentile=88, min_tile_edges=40
):
    """返回清晰度与模糊类型指标。

    每条边沿它自己的法线方向测量，再按法线朝向分四组比较，而不是沿四个
    固定方向扫全图。后者有严重的内容耦合：横平竖直的场景在45度方向根本
    找不到垂直于它的边，只能测到斜着切过的边，宽度天然偏大，结果就是
    模糊角恒定报45度，各向异性有三成的虚假本底。

    按法线分组之后，各组测的都是各自朝向上最优的宽度，组间差异才真正
    反映方向性模糊。运动模糊沿运动方向展宽，法线平行于运动方向的那组
    边缘变宽，垂直的那组不变；失焦则四组一致。
    """
    h, w = gray.shape
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3) / 8.0
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3) / 8.0
    mag = np.hypot(gx, gy)

    strong_thr = float(np.percentile(mag, strong_percentile))
    strong = mag > max(strong_thr, 1e-4)
    if strong.sum() < 500:
        return _empty("画面缺乏有效边缘，可能是纯色、极端过曝或完全失焦")

    # 边缘法线朝向，0到180度，量化到四个方向
    orient = np.degrees(np.arctan2(-gy, gx)) % 180.0
    bin_idx = np.round(orient / 45.0).astype(np.int32) % 4

    width_maps, valid_maps = {}, {}
    for i, angle in enumerate(_DIRS):
        wm, valid = _width_map(gray, angle, reach=4)
        floor = _floors()[angle]
        width_maps[angle] = wm / floor
        valid_maps[angle] = valid

    # 各方向按其法线朝向分组统计。大窗重测必须在分块统计之前完成并同步
    # 更新宽度图: 小窗的测量上限是9像素，重度模糊会整片撞顶，若分块网格
    # 仍用小窗数据，峰值宽度就被截断在上限附近，分不出"很糊"和"糊到没法看"，
    # 连拍组内的排序也会失真
    per_bin = {}
    for i, angle in enumerate(_DIRS):
        sel = strong & (bin_idx == i) & valid_maps[angle]
        vals = width_maps[angle][sel]
        if vals.size < 150:
            per_bin[angle] = np.nan
            continue
        val = float(np.percentile(vals, 100 - edge_percentile))
        if val * _floors()[angle] > 0.75 * 9:
            wm2, valid2 = _width_map(gray, angle, reach=10)
            wm2 = wm2 / _floors()[angle]
            sel2 = strong & (bin_idx == i) & valid2
            vals2 = wm2[sel2]
            if vals2.size >= 150:
                width_maps[angle], valid_maps[angle] = wm2, valid2
                val = float(np.percentile(vals2, 100 - edge_percentile))
        per_bin[angle] = val

    widths = np.array([per_bin[a] for a in _DIRS], np.float64)
    if not np.isfinite(widths).any():
        return _empty("有效边缘数量不足")

    global_width = float(np.nanmin(widths))
    wmax, wmin = float(np.nanmax(widths)), float(np.nanmin(widths))
    anisotropy = float((wmax - wmin) / wmax) if wmax > 1e-6 else 0.0

    # 分块统计。每块每方向各存一个读数，后面要靠块内的方向差异
    # 把浅景深和抖动区分开
    ys = np.linspace(0, h, tiles + 1).astype(int)
    xs = np.linspace(0, w, tiles + 1).astype(int)
    grids = {a: np.full((tiles, tiles), np.nan, np.float32) for a in _DIRS}
    for gi, angle in enumerate(_DIRS):
        wmap = width_maps[angle]
        sel_full = strong & (bin_idx == gi) & valid_maps[angle]
        for i in range(tiles):
            for j in range(tiles):
                sub = wmap[ys[i] : ys[i + 1], xs[j] : xs[j + 1]]
                m = sel_full[ys[i] : ys[i + 1], xs[j] : xs[j + 1]]
                vals = sub[m]
                if vals.size >= min_tile_edges:
                    grids[angle][i, j] = float(
                        np.percentile(vals, 100 - edge_percentile)
                    )

    stack = np.stack([grids[a] for a in _DIRS])
    tile_min = np.full(stack.shape[1:], np.nan, np.float32)
    finite_tiles = np.isfinite(stack).any(axis=0)
    if finite_tiles.any():
        tile_min[finite_tiles] = np.nanmin(stack[:, finite_tiles], axis=0)

    if np.isfinite(tile_min).any():
        flat = tile_min[np.isfinite(tile_min)]
        peak = float(np.percentile(flat, 5))
        idx = np.unravel_index(
            int(np.argmin(np.where(np.isfinite(tile_min), tile_min, np.inf))),
            tile_min.shape,
        )
        focus_y = round(float((idx[0] + 0.5) / tiles), 3)
        focus_x = round(float((idx[1] + 0.5) / tiles), 3)
        sharp_ratio = float(np.mean(flat < peak * 1.25))

        # 局部各向异性: 只在最锐的一批块里比较方向差异。
        # 这是区分浅景深与抖动的关键。浅景深的主体区域各方向都锐，
        # 只是画面别处虚化；抖动则是连最锐的区域也带方向性。
        # 用全图各向异性会把浅景深误判成抖动，实测浅景深能到0.45，
        # 与真实抖动完全重叠
        cutoff = float(np.percentile(flat, 20))
        mask = np.isfinite(tile_min) & (tile_min <= max(cutoff, peak * 1.15))
        local = []
        for angle in _DIRS:
            vals = grids[angle][mask & np.isfinite(grids[angle])]
            local.append(float(np.median(vals)) if vals.size >= 3 else np.nan)
        local = np.asarray(local)
        if np.isfinite(local).sum() >= 3:
            lmax, lmin = float(np.nanmax(local)), float(np.nanmin(local))
            local_aniso = (lmax - lmin) / lmax if lmax > 1e-6 else 0.0
            blur_angle = int(_DIRS[int(np.nanargmax(local))])
        else:
            local_aniso, blur_angle = anisotropy, int(_DIRS[int(np.nanargmax(widths))])
    else:
        peak, focus_x, focus_y, sharp_ratio = global_width, None, None, 0.0
        local_aniso, blur_angle = anisotropy, int(_DIRS[int(np.nanargmax(widths))])

    return {
        "edge_width": round(global_width, 3),
        "peak_edge_width": round(peak, 3),
        "anisotropy": round(float(local_aniso), 3),
        "global_anisotropy": round(anisotropy, 3),
        "blur_angle": blur_angle,
        "direction_widths": {
            str(a): (round(float(per_bin[a]), 3) if np.isfinite(per_bin[a]) else None)
            for a in _DIRS
        },
        "focus_x": focus_x,
        "focus_y": focus_y,
        "sharp_tile_ratio": round(sharp_ratio, 3),
        "note": "",
    }


def _empty(note):
    return {
        "edge_width": None,
        "peak_edge_width": None,
        "anisotropy": None,
        "blur_angle": None,
        "direction_widths": {},
        "focus_x": None,
        "focus_y": None,
        "sharp_tile_ratio": 0.0,
        "note": note,
    }


def classify(metrics, sharp_width=0.75, soft_width=1.15, anisotropy_thr=0.35):
    """把宽度与各向异性翻译成模糊类型。

    方向性优先判定。这里的各向异性是在最锐区域内部算的，已经排除了浅景深
    的干扰，可以放心作为首要判据。抖动的片子总有一个方向是锐的，若先按
    锐度判定，抖动会被整批放过，实测九像素抖动的峰值宽度只有0.68，与清晰
    图没有区别，但局部各向异性高达0.60。

    阈值单位是归一化边缘宽度，1.0对应西门子星标定的完美锐边。在长边1400的
    工作分辨率下实测：清晰0.65到0.70，轻度失焦0.76，中度0.93，重度1.31。
    """
    w = metrics.get("peak_edge_width")
    if w is None:
        return "unknown"
    if (metrics.get("anisotropy") or 0.0) >= anisotropy_thr:
        return "motion_blur"
    if w <= sharp_width:
        return "sharp"
    if w >= soft_width:
        return "defocus"
    return "soft"
