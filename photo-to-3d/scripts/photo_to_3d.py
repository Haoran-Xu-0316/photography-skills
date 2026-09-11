"""Public API for converting one photo into depth-aware 2.5D deliverables."""

from __future__ import annotations

import base64
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

try:
    from .depth_engine import (
        MODEL_ID,
        PhotoData,
        assess_depth,
        estimate_depth_with_model,
        load_depth_map,
        load_photo,
        save_depth16,
    )
    from .mesh_export import export_textured_relief
except ImportError:
    from depth_engine import (
        MODEL_ID,
        PhotoData,
        assess_depth,
        estimate_depth_with_model,
        load_depth_map,
        load_photo,
        save_depth16,
    )
    from mesh_export import export_textured_relief


SKILL_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_PATH = SKILL_ROOT / "assets" / "parallax-template.html"
VALID_MODES = {"depth", "parallax", "relief", "bundle"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    if path.exists():
        raise FileExistsError(f"报告已存在，默认不覆盖: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _preflight_output_paths(directory: Path, stem: str, mode: str) -> None:
    planned = [
        directory / f"{stem}_depth16.png",
        directory / f"{stem}_3d_preview.jpg",
        directory / f"{stem}_3d.recipe.json",
        directory / f"{stem}_3d.validation.json",
    ]
    if mode in {"parallax", "bundle"}:
        planned.extend(
            [
                directory / f"{stem}_parallax.html",
                directory / f"{stem}_parallax.gif",
            ]
        )
    if mode in {"relief", "bundle"}:
        planned.extend(
            [
                directory / f"{stem}_relief.obj",
                directory / f"{stem}_relief.mtl",
                directory / f"{stem}_texture.png",
            ]
        )
    existing = [str(path) for path in planned if path.exists()]
    if existing:
        raise FileExistsError("以下输出已存在，默认不覆盖: " + ", ".join(existing))


def analyze_photo(input_path: str | Path) -> dict[str, Any]:
    photo = load_photo(input_path)
    return {
        "file": str(photo.path),
        "sha256": _sha256(photo.path),
        "width": int(photo.rgb.shape[1]),
        "height": int(photo.rgb.shape[0]),
        "aspect_ratio": round(photo.rgb.shape[1] / photo.rgb.shape[0], 6),
        "exif_present": photo.exif is not None,
        "icc_profile_present": photo.icc_profile is not None,
    }


def _resolve_depth(
    photo: PhotoData,
    depth_map_path: str | Path | None,
    allow_model_download: bool,
    invert_depth: bool,
) -> tuple[np.ndarray, dict[str, Any]]:
    if depth_map_path is not None:
        depth_path = Path(depth_map_path).expanduser().resolve()
        if depth_path == photo.path:
            raise ValueError("原照片不能同时作为深度图输入")
        depth = load_depth_map(
            depth_path,
            target_size=(photo.rgb.shape[1], photo.rgb.shape[0]),
            invert=invert_depth,
        )
        source = {
            "type": "user-depth-map",
            "file": str(depth_path),
            "sha256": _sha256(depth_path),
            "inverted": invert_depth,
        }
    else:
        depth = estimate_depth_with_model(photo, allow_download=allow_model_download)
        if invert_depth:
            depth = 1.0 - depth
        source = {
            "type": "monocular-model",
            "model": MODEL_ID,
            "download_allowed": allow_model_download,
            "inverted": invert_depth,
        }
    return depth, source


def estimate_depth(
    input_path: str | Path,
    output_dir: str | Path,
    depth_map_path: str | Path | None = None,
    allow_model_download: bool = False,
    invert_depth: bool = False,
) -> dict[str, Any]:
    photo = load_photo(input_path)
    directory = Path(output_dir).expanduser().resolve()
    depth_path = directory / f"{photo.path.stem}_depth16.png"
    report_path = directory / f"{photo.path.stem}_depth.json"
    existing = [str(path) for path in (depth_path, report_path) if path.exists()]
    if existing:
        raise FileExistsError("以下输出已存在，默认不覆盖: " + ", ".join(existing))
    depth, source = _resolve_depth(photo, depth_map_path, allow_model_download, invert_depth)
    quality = assess_depth(photo.rgb, depth)
    save_depth16(depth, depth_path)
    report = {
        "input": str(photo.path),
        "input_sha256": _sha256(photo.path),
        "depth": str(depth_path),
        "source": source,
        "quality": quality,
    }
    _write_json(report_path, report)
    return {**report, "report": str(report_path)}


def _resized_rgb(rgb: np.ndarray, longest_side: int) -> np.ndarray:
    height, width = rgb.shape[:2]
    scale = min(1.0, longest_side / max(height, width))
    if scale == 1.0:
        return rgb
    return cv2.resize(rgb, (round(width * scale), round(height * scale)), interpolation=cv2.INTER_AREA)


def _data_url(rgb: np.ndarray, format_name: str = "JPEG") -> str:
    buffer = io.BytesIO()
    image = Image.fromarray(rgb, mode="RGB")
    if format_name == "JPEG":
        image.save(buffer, format="JPEG", quality=94, subsampling=0)
        mime = "image/jpeg"
    else:
        image.save(buffer, format="PNG")
        mime = "image/png"
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _depth_data_url(depth: np.ndarray) -> str:
    buffer = io.BytesIO()
    array = np.round(np.clip(depth, 0.0, 1.0) * 255.0).astype(np.uint8)
    Image.fromarray(array, mode="L").save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def _build_parallax_html(
    photo_rgb: np.ndarray,
    depth: np.ndarray,
    output_path: Path,
    strength: float,
) -> Path:
    if output_path.exists():
        raise FileExistsError(f"视差网页已存在，默认不覆盖: {output_path}")
    if not 0.005 <= strength <= 0.04:
        raise ValueError("parallax_strength必须在0.005至0.04之间")
    web_photo = _resized_rgb(photo_rgb, 2048)
    web_depth = cv2.resize(depth, (web_photo.shape[1], web_photo.shape[0]), interpolation=cv2.INTER_CUBIC)
    motion_sigma = max(0.8, max(web_depth.shape) * 0.003)
    web_depth = cv2.GaussianBlur(web_depth, (0, 0), motion_sigma)
    html = TEMPLATE_PATH.read_text(encoding="utf-8")
    html = html.replace("__IMAGE_DATA__", _data_url(web_photo))
    html = html.replace("__DEPTH_DATA__", _depth_data_url(web_depth))
    html = html.replace("__STRENGTH__", f"{2.0 * strength:.6f}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path


def _parallax_frame(rgb: np.ndarray, depth: np.ndarray, phase: float, strength: float) -> np.ndarray:
    height, width = depth.shape
    yy, xx = np.mgrid[0:height, 0:width].astype(np.float32)
    motion_sigma = max(0.8, max(height, width) * 0.003)
    motion_depth = cv2.GaussianBlur(depth.astype(np.float32), (0, 0), motion_sigma)
    centered = motion_depth - 0.5
    dx = np.sin(phase) * strength * width * centered
    dy = np.cos(phase) * strength * width * 0.45 * centered
    map_x = np.asarray(xx + dx, dtype=np.float32)
    map_y = np.asarray(yy + dy, dtype=np.float32)
    return cv2.remap(
        rgb,
        map_x,
        map_y,
        interpolation=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_REFLECT_101,
    )


def _build_parallax_gif(
    photo_rgb: np.ndarray,
    depth: np.ndarray,
    output_path: Path,
    strength: float,
    frame_count: int = 24,
) -> Path:
    if output_path.exists():
        raise FileExistsError(f"视差动画已存在，默认不覆盖: {output_path}")
    preview = _resized_rgb(photo_rgb, 960)
    preview_depth = cv2.resize(depth, (preview.shape[1], preview.shape[0]), interpolation=cv2.INTER_CUBIC)
    frames = [
        Image.fromarray(
            _parallax_frame(preview, preview_depth, 2.0 * np.pi * index / frame_count, strength),
            mode="RGB",
        )
        for index in range(frame_count)
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        output_path,
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
        optimize=False,
        disposal=2,
    )
    return output_path


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size=size)
            except OSError:
                pass
    return ImageFont.load_default()


def _build_contact_sheet(photo_rgb: np.ndarray, depth: np.ndarray, output_path: Path, strength: float) -> Path:
    if output_path.exists():
        raise FileExistsError(f"检查图已存在，默认不覆盖: {output_path}")
    photo = _resized_rgb(photo_rgb, 720)
    depth_small = cv2.resize(depth, (photo.shape[1], photo.shape[0]), interpolation=cv2.INTER_CUBIC)
    colored_depth = cv2.applyColorMap(
        np.round(np.clip(depth_small, 0.0, 1.0) * 255.0).astype(np.uint8),
        cv2.COLORMAP_TURBO,
    )
    colored_depth = cv2.cvtColor(colored_depth, cv2.COLOR_BGR2RGB)
    shifted = _parallax_frame(photo, depth_small, np.pi / 2.0, strength)
    panels = [("ORIGINAL", photo), ("DEPTH", colored_depth), ("PARALLAX", shifted)]
    margin, label_height = 16, 48
    cell_width, image_height = photo.shape[1], photo.shape[0]
    canvas = Image.new("RGB", (cell_width * 3 + margin * 4, image_height + label_height + margin * 2), (238, 237, 233))
    draw = ImageDraw.Draw(canvas)
    font = _font(20)
    for index, (label, panel) in enumerate(panels):
        x = margin + index * (cell_width + margin)
        canvas.paste(Image.fromarray(panel, mode="RGB"), (x, margin))
        box = draw.textbbox((0, 0), label, font=font)
        draw.text((x + (cell_width - (box[2] - box[0])) / 2, margin + image_height + 12), label, fill=(25, 25, 25), font=font)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output_path, quality=94, subsampling=0)
    return output_path


def _validate_outputs(
    photo: PhotoData,
    original_hash: str,
    depth: np.ndarray,
    quality: dict[str, Any],
    outputs: dict[str, Any],
    mesh_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    blocking = list(quality.get("blocking", []))
    warnings = list(quality.get("warnings", []))
    if _sha256(photo.path) != original_hash:
        blocking.append("原照片哈希发生变化")

    for name, value in outputs.items():
        if isinstance(value, str) and name not in {"mode"} and not Path(value).is_file():
            blocking.append(f"缺少输出文件: {name}")

    gif_frames = None
    if "gif" in outputs:
        with Image.open(outputs["gif"]) as animation:
            gif_frames = getattr(animation, "n_frames", 1)
        if gif_frames < 12:
            blocking.append(f"视差动画帧数不足: {gif_frames}")

    obj_vertices = obj_faces = None
    if "obj" in outputs:
        obj_text = Path(outputs["obj"]).read_text(encoding="utf-8")
        lines = obj_text.splitlines()
        vertices = [line.split()[1:] for line in lines if line.startswith("v ")]
        coordinates = [line.split()[1:] for line in lines if line.startswith("vt ")]
        faces = [line.split()[1:] for line in lines if line.startswith("f ")]
        obj_vertices, obj_faces = len(vertices), len(faces)
        if mesh_info is None:
            blocking.append("缺少OBJ网格尺寸契约")
        else:
            width, height = mesh_info["mesh_width"], mesh_info["mesh_height"]
            if obj_vertices != width * height or obj_faces != 2 * (width - 1) * (height - 1):
                blocking.append("OBJ网格规模与采样尺寸不符")
        try:
            xyz = np.asarray(vertices, dtype=float)
            uv = np.asarray(coordinates, dtype=float)
            if xyz.shape != (obj_vertices, 3) or not np.isfinite(xyz).all():
                blocking.append("OBJ顶点坐标无效")
            if uv.shape != (obj_vertices, 2) or not np.isfinite(uv).all() or np.any((uv < 0) | (uv > 1)):
                blocking.append("OBJ纹理坐标无效")
            for face in faces:
                pairs = [tuple(int(value) for value in token.split("/")) for token in face]
                if len(pairs) != 3 or any(len(pair) != 2 or not (1 <= pair[0] <= obj_vertices and 1 <= pair[1] <= len(coordinates)) for pair in pairs):
                    blocking.append("OBJ面片索引无效")
                    break
        except (ValueError, TypeError):
            blocking.append("OBJ坐标或索引无法解析")

    return {
        "status": "pass" if not blocking else "blocked",
        "blocking": blocking,
        "warnings": warnings,
        "depth": quality.get("metrics", {}),
        "gif_frames": gif_frames,
        "obj_vertices": obj_vertices,
        "obj_faces": obj_faces,
        "source_dimensions": [int(photo.rgb.shape[1]), int(photo.rgb.shape[0])],
        "depth_dimensions": [int(depth.shape[1]), int(depth.shape[0])],
    }


def convert_photo_to_3d(
    input_path: str | Path,
    output_dir: str | Path,
    mode: str = "bundle",
    depth_map_path: str | Path | None = None,
    allow_model_download: bool = False,
    invert_depth: bool = False,
    parallax_strength: float = 0.02,
    mesh_resolution: int = 256,
    relief_strength: float = 0.12,
) -> dict[str, Any]:
    if mode not in VALID_MODES:
        raise ValueError(f"不支持的模式: {mode}。可用模式为{sorted(VALID_MODES)}")
    photo = load_photo(input_path)
    original_hash = _sha256(photo.path)
    directory = Path(output_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    stem = photo.path.stem
    _preflight_output_paths(directory, stem, mode)

    depth, depth_source = _resolve_depth(photo, depth_map_path, allow_model_download, invert_depth)
    quality = assess_depth(photo.rgb, depth)
    if quality["status"] == "blocked":
        raise ValueError("深度质量不合格: " + "; ".join(quality["blocking"]))

    outputs: dict[str, Any] = {}
    depth_path = directory / f"{stem}_depth16.png"
    save_depth16(depth, depth_path)
    outputs["depth"] = str(depth_path)
    preview_path = directory / f"{stem}_3d_preview.jpg"
    _build_contact_sheet(photo.rgb, depth, preview_path, parallax_strength)
    outputs["preview"] = str(preview_path)

    if mode in {"parallax", "bundle"}:
        html_path = directory / f"{stem}_parallax.html"
        gif_path = directory / f"{stem}_parallax.gif"
        _build_parallax_html(photo.rgb, depth, html_path, parallax_strength)
        _build_parallax_gif(photo.rgb, depth, gif_path, parallax_strength)
        outputs["html"] = str(html_path)
        outputs["gif"] = str(gif_path)

    mesh = None
    if mode in {"relief", "bundle"}:
        mesh = export_textured_relief(
            photo.rgb,
            depth,
            directory,
            stem,
            mesh_resolution=mesh_resolution,
            relief_strength=relief_strength,
        )
        outputs.update({key: mesh[key] for key in ("obj", "mtl", "texture")})

    validation = _validate_outputs(photo, original_hash, depth, quality, outputs, mesh_info=mesh)
    recipe_path = directory / f"{stem}_3d.recipe.json"
    validation_path = directory / f"{stem}_3d.validation.json"
    recipe = {
        "input": str(photo.path),
        "input_sha256": original_hash,
        "mode": mode,
        "depth_source": depth_source,
        "near_is_white": True,
        "parallax_strength": parallax_strength,
        "mesh_resolution": mesh_resolution if mesh else None,
        "relief_strength": relief_strength if mesh else None,
        "outputs": outputs,
    }
    _write_json(recipe_path, recipe)
    _write_json(validation_path, validation)
    return {
        "status": validation["status"],
        "outputs": outputs,
        "recipe": str(recipe_path),
        "validation": str(validation_path),
        "warnings": validation["warnings"],
        "blocking": validation["blocking"],
    }
