"""人脸与对焦落点。

用OpenCV自带的Haar级联，完全离线，不需要下载模型。代价是只能测正脸，
侧脸和低头会漏，而且对眼睛的判断相当粗糙。

因此这里的定位是提示而非判据。眼睛检测不到有三种可能：闭眼、戴墨镜、
检测器本身漏检，三者无法区分。所以闭眼只作为提示项输出，绝不参与自动
判废。把不确定的信号当成确定的判据，是筛片工具最容易犯也最伤人的错，
误删一张就再也找不回来。

真正可靠的是对焦落点检验：把画面最锐的区域和人脸位置对比，如果人脸在
画面里而最锐处在别处，说明对焦跑了。这个判断只依赖人脸框位置，不依赖
眼睛检测，可靠得多。
"""

import os

import cv2
import numpy as np

_CASCADES = {}


def _cascade(name):
    if not hasattr(cv2, "CascadeClassifier") or not hasattr(cv2, "data"):
        return None
    if not hasattr(cv2.data, "haarcascades"):
        return None
    if name not in _CASCADES:
        path = os.path.join(cv2.data.haarcascades, name)
        c = cv2.CascadeClassifier(path)
        _CASCADES[name] = None if c.empty() else c
    return _CASCADES[name]


def detect(bgr, min_face_ratio=0.04, detect_long_side=800):
    """返回人脸列表与眼睛提示。坐标为相对画面的归一化值。

    在降采样图上检测。Haar对四分之一以上画面占比的人脸在800像素下已经
    足够，全分辨率检测慢三倍且检出率并无提升。
    """
    scale = detect_long_side / max(bgr.shape[:2])
    if scale < 1.0:
        bgr = cv2.resize(bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.equalizeHist(gray)
    h, w = gray.shape
    face_cc = _cascade("haarcascade_frontalface_alt2.xml")
    if face_cc is None:
        return {"faces": [], "face_count": 0, "eyes_missing": 0, "available": False}

    min_size = int(min(h, w) * min_face_ratio)
    rects = face_cc.detectMultiScale(
        gray,
        scaleFactor=1.12,
        minNeighbors=6,
        minSize=(max(min_size, 24), max(min_size, 24)),
    )
    eye_cc = _cascade("haarcascade_eye.xml")
    faces, missing = [], 0
    for x, y, fw, fh in rects:
        # 只在人脸上半部找眼睛，下半部的鼻孔和嘴角容易误检
        roi = gray[y : y + int(fh * 0.6), x : x + fw]
        eyes = []
        if eye_cc is not None and roi.size:
            eyes = eye_cc.detectMultiScale(
                roi,
                scaleFactor=1.1,
                minNeighbors=8,
                minSize=(max(int(fw * 0.12), 10),) * 2,
            )
        if len(eyes) < 2:
            missing += 1
        faces.append(
            {
                "x": round(float(x + fw / 2) / w, 3),
                "y": round(float(y + fh / 2) / h, 3),
                "size": round(float(fw) / w, 3),
                "eyes_found": len(eyes),
            }
        )

    faces.sort(key=lambda f: -f["size"])
    return {
        "faces": faces,
        "face_count": len(faces),
        "eyes_missing": missing,
        "available": True,
    }


def focus_on_subject(sharp_metrics, face_info, tolerance=0.18):
    """对焦落点是否命中主体。

    只在检测到人脸时有意义。比较最锐区块中心与最大人脸中心的距离，
    容差按画面对角线的比例给。返回None表示无法判断。
    """
    if not face_info.get("faces"):
        return None
    fx, fy = sharp_metrics.get("focus_x"), sharp_metrics.get("focus_y")
    if fx is None or fy is None:
        return None
    face = face_info["faces"][0]
    dist = float(np.hypot(fx - face["x"], fy - face["y"]))
    # 容差随人脸尺寸放宽，大头照的人脸本身就占很大面积
    tol = tolerance + face["size"] * 0.5
    return {
        "hit": bool(dist <= tol),
        "distance": round(dist, 3),
        "tolerance": round(tol, 3),
    }
