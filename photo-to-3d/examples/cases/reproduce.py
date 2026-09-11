"""多题材案例复现。输入为合成测试素材，参数固定且原文件只读。"""

from pathlib import Path
from importlib import import_module
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"scripts"))
engine = import_module("photo_to_3d")


def reproduce_case(case_name: str, output_directory: str | Path) -> dict:
    """在独立Python进程中调用；多帧输入仅为模拟回归，不冒充实拍。"""
    if case_name not in {"animal", "city", "portrait"}:
        raise ValueError("Unknown bundled case")
    inputs = Path(__file__).resolve().parent/case_name/"input"
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError("Use a new output directory")
    return engine.convert_photo_to_3d(inputs/"source.png",output,mode="bundle",depth_map_path=inputs/"depth.png",allow_model_download=False,parallax_strength=.008,mesh_resolution=64)
