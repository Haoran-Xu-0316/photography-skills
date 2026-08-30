"""高ISO降噪。

两个关键设计:

一是亮度与色度分开。色度噪声(彩色斑块)去掉后画面干净度提升最明显，
且几乎不损失细节，可以下重手。亮度噪声承载着大量真实纹理，力度稍大
就是塑料感，只能轻降。二者用同一个参数控制是常见的翻车原因。

二是强度由实测噪声驱动而非ISO。同样ISO 6400，正常曝光和欠曝两档
后期提亮的片子，噪声水平差一倍以上。ISO只在测量失败时作为先验兜底。

细节回补: 降噪残差中包含被误伤的真实纹理，按边缘强度加权把这部分
残差还回去，flat区域保持干净，边缘区域保留锐度。
"""

import cv2
import numpy as np
from io_utils import linear_to_srgb, srgb_to_linear


def _nlm(channel, sigma, h_factor, patch=5, distance=6):
    """优先用skimage的浮点NLM，避免8位量化在16位工作流上造成断层。"""
    if sigma <= 1e-6:
        return channel
    try:
        from skimage.restoration import denoise_nl_means

        return denoise_nl_means(
            channel,
            h=h_factor * sigma,
            sigma=sigma,
            patch_size=patch,
            patch_distance=distance,
            fast_mode=True,
            channel_axis=None,
        ).astype(np.float32)
    except Exception:
        lo, hi = float(channel.min()), float(channel.max())
        rng = max(hi - lo, 1e-6)
        u8 = np.clip((channel - lo) / rng * 255, 0, 255).astype(np.uint8)
        den = cv2.fastNlMeansDenoising(
            u8, None, float(np.clip(h_factor * sigma / rng * 255, 1, 40)), patch, 21
        )
        return (den.astype(np.float32) / 255.0 * rng + lo).astype(np.float32)


def _bm3d(channel, sigma):
    import bm3d

    return bm3d.bm3d(
        channel, sigma_psd=sigma, stage_arg=bm3d.BM3DStages.ALL_STAGES
    ).astype(np.float32)


def _edge_mask(gray, low=0.02, high=0.12):
    grad = np.hypot(
        cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3),
        cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3),
    )
    grad = cv2.GaussianBlur(grad, (0, 0), 1.2)
    return np.clip((grad - low) / max(high - low, 1e-6), 0.0, 1.0).astype(np.float32)


def apply(rgb_linear, noise, cfg, iso_prior=None):
    """在gamma编码空间的Lab下降噪，返回(线性光结果, 信息字典)。"""
    sigma_l = float(noise.get("luma_sigma", 0.0))
    sigma_c = float(noise.get("chroma_sigma", 0.0))
    if iso_prior:
        # 测量值明显低于ISO预期时说明测量落在了非典型区域，取较大者兜底
        sigma_l = max(sigma_l, iso_prior * float(cfg.get("iso_prior_weight", 0.6)))

    lu_scale = float(cfg.get("luma_strength", 0.9))
    ch_scale = float(cfg.get("chroma_strength", 3.0))
    floor = float(cfg.get("sigma_floor", 0.0022))

    if sigma_l * lu_scale < floor and sigma_c * ch_scale < floor:
        return rgb_linear, {
            "applied": False,
            "reason": "噪声低于处理阈值",
            "luma_sigma": round(sigma_l, 5),
            "chroma_sigma": round(sigma_c, 5),
        }

    enc = linear_to_srgb(np.clip(rgb_linear, 0, 1)).astype(np.float32)
    lab = cv2.cvtColor(enc, cv2.COLOR_RGB2Lab)
    L = (lab[..., 0] / 100.0).astype(np.float32)
    A = (lab[..., 1] / 255.0).astype(np.float32)
    B = (lab[..., 2] / 255.0).astype(np.float32)

    info = {
        "applied": True,
        "luma_sigma": round(sigma_l, 5),
        "chroma_sigma": round(sigma_c, 5),
    }

    # 色度: 降采样处理再插值回去，色度噪声空间频率低，几乎无损且快4倍
    if sigma_c > 1e-5 and ch_scale > 0:
        ds = int(cfg.get("chroma_downscale", 2))
        if ds > 1:
            small_a = cv2.resize(
                A, None, fx=1 / ds, fy=1 / ds, interpolation=cv2.INTER_AREA
            )
            small_b = cv2.resize(
                B, None, fx=1 / ds, fy=1 / ds, interpolation=cv2.INTER_AREA
            )
            da = _nlm(small_a, sigma_c * ds * 0.5, ch_scale, patch=5, distance=7)
            db = _nlm(small_b, sigma_c * ds * 0.5, ch_scale, patch=5, distance=7)
            da = cv2.resize(da, (A.shape[1], A.shape[0]), interpolation=cv2.INTER_CUBIC)
            db = cv2.resize(db, (B.shape[1], B.shape[0]), interpolation=cv2.INTER_CUBIC)
        else:
            da = _nlm(A, sigma_c, ch_scale, patch=5, distance=7)
            db = _nlm(B, sigma_c, ch_scale, patch=5, distance=7)
        A, B = da, db
        info["chroma_h"] = round(ch_scale * sigma_c, 5)

    # 亮度
    if sigma_l > 1e-5 and lu_scale > 0:
        method = str(cfg.get("luma_method", "nlm")).lower()
        if method == "bm3d":
            try:
                dL = _bm3d(L, sigma_l * lu_scale)
            except Exception:
                method = "nlm"
                dL = _nlm(L, sigma_l, lu_scale)
        elif method == "bilateral":
            dL = cv2.bilateralFilter(L, 0, sigma_l * lu_scale * 6, 3.0)
        else:
            dL = _nlm(
                L,
                sigma_l,
                lu_scale,
                patch=int(cfg.get("patch_size", 5)),
                distance=int(cfg.get("patch_distance", 6)),
            )
        info["luma_method"] = method
        info["luma_h"] = round(lu_scale * sigma_l, 5)

        recover = float(cfg.get("detail_recovery", 0.35))
        if recover > 0:
            mask = _edge_mask(dL)
            dL = dL + (L - dL) * mask * recover
            info["detail_recovery"] = recover
        L = dL

    lab_out = np.stack(
        [
            np.clip(L, 0, 1) * 100.0,
            np.clip(A, -0.55, 0.55) * 255.0,
            np.clip(B, -0.55, 0.55) * 255.0,
        ],
        axis=2,
    ).astype(np.float32)
    out_enc = np.clip(cv2.cvtColor(lab_out, cv2.COLOR_Lab2RGB), 0, 1)
    return srgb_to_linear(out_enc).astype(np.float32), info
