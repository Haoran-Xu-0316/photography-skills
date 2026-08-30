"""评分与判定。

三条原则。

第一，只判客观项。对焦、抖动、曝光溢出、连拍重复，这些有明确物理判据。
构图好坏、表情、氛围一概不判，那是审美，交给人。

第二，宁可留错不可删错。误留一张的代价是多看一眼，误删一张的代价是
永久损失。所以判废的门槛必须明显高于判优，中间地带一律进待定。

第三，删片理由必须可追溯。每张废片都写明具体指标和数值，用户能复核，
不接受就调阈值重跑。
"""


VERDICTS = ("keep", "review", "reject")


def score_one(rec, cfg):
    """对单张给出判定与理由。此时还不考虑连拍关系。"""
    s = cfg["sharpness"]
    e = cfg["exposure"]
    sharp = rec["sharpness"]
    expo = rec["exposure"]
    reasons, verdict = [], "review"

    blur = rec["blur_type"]
    w = sharp.get("peak_edge_width")

    if w is None:
        # 清晰度测不出来时不能直接返回。纯黑的镜头盖误拍、全白的严重过曝
        # 都缺乏有效边缘，恰恰是最该判废的一类，若在此处提前返回，它们会
        # 全部落进待定，用户还得手工挑一遍
        reasons.append(sharp.get("note") or "无法测量清晰度")
        verdict, quality = "review", 0.3
    elif blur == "sharp":
        verdict, quality = "keep", 1.0
    elif blur == "soft":
        verdict = "review"
        reasons.append(f"略欠锐，边缘宽度{w:.2f}，可能是轻微失焦或镜头软")
        quality = 0.6
    elif blur == "motion_blur":
        reasons.append(
            f"抖动，边缘宽度{w:.2f}，方向性{sharp['anisotropy']:.2f}"
            f"，主方向{sharp['blur_angle']}度"
        )
        verdict = "reject" if w >= s["reject_width"] else "review"
        quality = 0.25
    else:
        reasons.append(f"失焦，边缘宽度{w:.2f}")
        verdict = "reject" if w >= s["reject_width"] else "review"
        quality = 0.2

    # 曝光。只有不可逆的损失才参与判废
    if expo["highlight_clip_pct"] >= e["reject_highlight_pct"]:
        reasons.append(f"高光溢出{expo['highlight_clip_pct']:.1f}%，超出可接受范围")
        verdict = "reject"
        quality = min(quality, 0.2)
    elif expo["highlight_clip_pct"] >= e["warn_highlight_pct"]:
        reasons.append(f"高光溢出{expo['highlight_clip_pct']:.1f}%")
        verdict = "review" if verdict == "keep" else verdict
        quality = min(quality, 0.7)

    if expo["shadow_crush_pct"] >= e["reject_shadow_pct"]:
        reasons.append(f"暗部死黑{expo['shadow_crush_pct']:.1f}%")
        verdict = "reject"
        quality = min(quality, 0.25)

    if expo["relative_contrast"] < e["flat_threshold"]:
        reasons.append("反差极低，疑似误拍或镜头遮挡")
        verdict = "reject"
        quality = min(quality, 0.1)

    # 对焦落点。检测到人脸但最锐处不在脸上，是很硬的废片证据
    focus = rec.get("focus_check")
    if focus and not focus["hit"] and blur in ("sharp", "soft"):
        reasons.append(
            f"画面有人脸但最锐区域在别处，距离{focus['distance']:.2f}，对焦可能跑了"
        )
        verdict = "review" if verdict == "keep" else verdict
        quality = min(quality, 0.5)

    # 闭眼只提示，永不判废。检测不到眼睛也可能是墨镜、侧脸或检测器漏检
    faces = rec.get("faces") or {}
    if faces.get("eyes_missing"):
        reasons.append(f"{faces['eyes_missing']}张脸未检出双眼，可能闭眼，需人工确认")

    return verdict, reasons, quality


def resolve_bursts(records, cfg):
    """在连拍组内排序，只留最优的若干张，其余降级。

    组内比较用边缘宽度，同组构图与光线基本一致，这个比较是公平的。
    跨组不做这种比较，不同场景的绝对锐度没有可比性。
    """
    keep_n = int(cfg["burst"]["keep_per_group"])
    groups = {}
    for i, r in enumerate(records):
        groups.setdefault(r["burst_group"], []).append(i)

    for gid, idxs in groups.items():
        if len(idxs) < 2:
            continue
        ranked = sorted(
            idxs,
            key=lambda i: (
                records[i]["quality"] * -1,
                records[i]["sharpness"].get("peak_edge_width") or 99,
            ),
        )
        for rank, i in enumerate(ranked):
            records[i]["burst_size"] = len(idxs)
            records[i]["burst_rank"] = rank + 1
            if rank < keep_n:
                continue
            # 组内落选的降为待定而非直接判废。连拍里第二好的那张
            # 可能表情更好，这是机器看不出来的
            if records[i]["verdict"] == "keep":
                records[i]["verdict"] = "review"
                records[i]["reasons"].append(
                    f"连拍组内第{rank + 1}锐，共{len(idxs)}张，已有更锐的一张"
                )
    return records


def to_rating(rec, cfg):
    """映射到星级与色标，供Lightroom和Capture One读取。"""
    v = rec["verdict"]
    if v == "reject":
        return 1, cfg["labels"]["reject"]
    if v == "review":
        return 3, cfg["labels"]["review"]
    if rec.get("burst_rank") == 1 and rec.get("burst_size", 1) > 1:
        return 5, cfg["labels"]["best"]
    return 4, cfg["labels"]["keep"]
