"""多题材案例复现。输入为合成测试素材，参数固定且原文件只读。"""

from pathlib import Path
from importlib import import_module
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/"scripts"))
engine = import_module("photo_print_layout")


def reproduce_case(case_name: str, output_directory: str | Path) -> dict:
    """在独立Python进程中调用；多帧输入仅为模拟回归，不冒充实拍。"""
    if case_name not in {"animal", "city", "portrait"}:
        raise ValueError("Unknown bundled case")
    inputs = Path(__file__).resolve().parent/case_name/"input"
    output = Path(output_directory)
    if output.exists():
        raise FileExistsError("Use a new output directory")
    return engine.create_print_layout([inputs/"source.png"]+[inputs/f"{name}.png" for name in ("animal","city","portrait") if name!=case_name],output,paper_size_mm=(210,297),grid=(2,2),fit_strategy="contain",margins_mm=15,dpi=300,minimum_ppi=240)
