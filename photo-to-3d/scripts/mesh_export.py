"""Export a textured height-field as portable OBJ, MTL and PNG files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image


def _mesh_size(width: int, height: int, longest_side: int) -> tuple[int, int]:
    scale = longest_side / max(width, height)
    return max(2, round(width * scale)), max(2, round(height * scale))


def export_textured_relief(
    photo_rgb: np.ndarray,
    depth: np.ndarray,
    output_dir: str | Path,
    stem: str,
    mesh_resolution: int = 256,
    relief_strength: float = 0.12,
) -> dict[str, Any]:
    if not 64 <= mesh_resolution <= 512:
        raise ValueError("mesh_resolution必须在64至512之间")
    if not 0.01 <= relief_strength <= 0.30:
        raise ValueError("relief_strength必须在0.01至0.30之间")

    directory = Path(output_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    obj_path = directory / f"{stem}_relief.obj"
    mtl_path = directory / f"{stem}_relief.mtl"
    texture_path = directory / f"{stem}_texture.png"
    for path in (obj_path, mtl_path, texture_path):
        if path.exists():
            raise FileExistsError(f"3D输出已存在，默认不覆盖: {path}")

    height, width = depth.shape
    mesh_width, mesh_height = _mesh_size(width, height, mesh_resolution)
    mesh_depth = cv2.resize(depth, (mesh_width, mesh_height), interpolation=cv2.INTER_AREA)
    aspect = width / height

    lines = [f"mtllib {mtl_path.name}", "o photo_relief", "usemtl photo_texture"]
    for row in range(mesh_height):
        y = 0.5 - row / (mesh_height - 1)
        for column in range(mesh_width):
            x = (column / (mesh_width - 1) - 0.5) * aspect
            z = (float(mesh_depth[row, column]) - 0.5) * relief_strength * aspect
            lines.append(f"v {x:.8f} {y:.8f} {z:.8f}")

    for row in range(mesh_height):
        v = 1.0 - row / (mesh_height - 1)
        for column in range(mesh_width):
            u = column / (mesh_width - 1)
            lines.append(f"vt {u:.8f} {v:.8f}")

    face_count = 0
    for row in range(mesh_height - 1):
        for column in range(mesh_width - 1):
            a = row * mesh_width + column + 1
            b = a + 1
            c = a + mesh_width
            d = c + 1
            lines.append(f"f {a}/{a} {c}/{c} {b}/{b}")
            lines.append(f"f {b}/{b} {c}/{c} {d}/{d}")
            face_count += 2

    obj_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    mtl_path.write_text(
        "newmtl photo_texture\n"
        "Ka 0.000000 0.000000 0.000000\n"
        "Kd 1.000000 1.000000 1.000000\n"
        "Ks 0.000000 0.000000 0.000000\n"
        "d 1.000000\n"
        "illum 1\n"
        f"map_Kd {texture_path.name}\n",
        encoding="utf-8",
    )
    Image.fromarray(photo_rgb, mode="RGB").save(texture_path)

    return {
        "obj": str(obj_path),
        "mtl": str(mtl_path),
        "texture": str(texture_path),
        "mesh_width": mesh_width,
        "mesh_height": mesh_height,
        "vertex_count": mesh_width * mesh_height,
        "face_count": face_count,
        "relief_strength": relief_strength,
    }
