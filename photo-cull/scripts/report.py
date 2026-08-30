"""报告输出。

CSV给人看和二次筛选用，JSON给程序用。另外生成一张废片印象图，把所有
被判废的缩略图拼成一张，用户扫一眼就能确认有没有误杀。这一步不能省，
自动判废必须给出可复核的证据面。
"""

import csv
import json
import os

import cv2
import numpy as np

CSV_FIELDS = [
    "name",
    "verdict",
    "blur_type",
    "peak_edge_width",
    "anisotropy",
    "highlight_clip_pct",
    "shadow_crush_pct",
    "face_count",
    "burst_group",
    "burst_rank",
    "burst_size",
    "rating",
    "label",
    "iso",
    "shutter",
    "aperture",
    "focal",
    "reasons",
]


def write_csv(records, path):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for r in records:
            row = {
                "name": r["name"],
                "verdict": r["verdict"],
                "blur_type": r["blur_type"],
                "peak_edge_width": r["sharpness"].get("peak_edge_width"),
                "anisotropy": r["sharpness"].get("anisotropy"),
                "highlight_clip_pct": r["exposure"]["highlight_clip_pct"],
                "shadow_crush_pct": r["exposure"]["shadow_crush_pct"],
                "face_count": (r.get("faces") or {}).get("face_count", 0),
                "burst_group": r.get("burst_group"),
                "burst_rank": r.get("burst_rank"),
                "burst_size": r.get("burst_size", 1),
                "rating": r.get("rating"),
                "label": r.get("label"),
                "iso": r.get("iso"),
                "shutter": r.get("shutter"),
                "aperture": r.get("aperture"),
                "focal": r.get("focal"),
                "reasons": "; ".join(r.get("reasons") or []),
            }
            writer.writerow(row)
    return path


def write_json(records, path, summary=None):
    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    payload = {
        "summary": summary or {},
        "records": [{k: v for k, v in r.items() if k != "thumb"} for r in records],
    }
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
    return path


def contact_sheet(records, path, verdict="reject", cols=5, cell=280, max_items=60):
    """把指定判定的片子拼成印象图，用于快速复核。

    此处按需回读图像，不在分析阶段缓存缩略图。缓存看似省事，代价是
    每张记录挂着一张全尺寸缩略图，两千张就是7.8GB，直接把内存打爆。
    印象图最多只展示几十张，回读这几十张的开销不到十秒。
    """
    import loader

    sel = [r for r in records if r["verdict"] == verdict][:max_items]
    if not sel:
        return None
    for r in sel:
        if r.get("thumb") is None:
            try:
                _, bgr, _ = loader.load_gray(r["path"], long_side=cell * 2)
                r["thumb"] = bgr
            except Exception:
                r["thumb"] = None
    sel = [r for r in sel if r.get("thumb") is not None]
    if not sel:
        return None
    rows = int(np.ceil(len(sel) / cols))
    label_h = 26
    sheet = np.full((rows * (cell + label_h), cols * cell, 3), 32, np.uint8)

    for k, r in enumerate(sel):
        i, j = divmod(k, cols)
        thumb = r["thumb"]
        h, w = thumb.shape[:2]
        scale = cell / max(h, w)
        small = cv2.resize(
            thumb, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA
        )
        sh, sw = small.shape[:2]
        y0 = i * (cell + label_h) + (cell - sh) // 2
        x0 = j * cell + (cell - sw) // 2
        sheet[y0 : y0 + sh, x0 : x0 + sw] = small
        text = os.path.splitext(r["name"])[0][:26]
        cv2.putText(
            sheet,
            text,
            (j * cell + 6, i * (cell + label_h) + cell + 18),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.42,
            (220, 220, 220),
            1,
            cv2.LINE_AA,
        )

    os.makedirs(os.path.dirname(os.path.abspath(path)) or ".", exist_ok=True)
    if not cv2.imwrite(path, sheet):
        raise OSError(f"写入废片联系表失败: {path}")
    return path


def summarize(records):
    counts = {"keep": 0, "review": 0, "reject": 0}
    blur = {}
    for r in records:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
        blur[r["blur_type"]] = blur.get(r["blur_type"], 0) + 1
    total = max(len(records), 1)
    return {
        "total": len(records),
        "keep": counts["keep"],
        "review": counts["review"],
        "reject": counts["reject"],
        "keep_pct": round(100 * counts["keep"] / total, 1),
        "reject_pct": round(100 * counts["reject"] / total, 1),
        "blur_types": blur,
    }
