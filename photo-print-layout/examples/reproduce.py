"""复现随附的受控示例；不覆盖源文件，不代表全部能力已验证。

在独立Python会话中导入本文件，调用reproduce_example(一个尚不存在的输出目录)。
多帧、组照和手工深度输入的限制见README.md。
"""

from importlib import import_module
from pathlib import Path
import sys

SKILL_ROOT = Path(__file__).resolve().parents[1]
INPUT = Path(__file__).resolve().parent / "input"
sys.path.insert(0, str(SKILL_ROOT / "scripts"))
engine = import_module("photo_print_layout")


def reproduce_example(output_directory: str | Path) -> dict:
    """调用原有处理接口，生成可检查的示例结果。"""
    if Path(output_directory).exists():
        raise FileExistsError("请指定尚不存在的输出目录，保留已有结果。")
    return engine.create_print_layout([INPUT / name for name in ("workbench.jpg", "garden.jpg", "workbench-detail.jpg", "garden-detail.jpg")], output_directory, paper_size_mm=(210, 297), grid=(2, 2), fit_strategy="contain", margins_mm=(15, 15, 18, 20), gap_mm=6, bleed_mm=3, binding_edge="left", binding_safe_mm=8, dpi=300, minimum_ppi=240)
