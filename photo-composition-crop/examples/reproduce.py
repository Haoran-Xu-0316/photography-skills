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
engine = import_module("photo_composition_crop")


def reproduce_example(output_directory: str | Path) -> dict:
    """调用原有处理接口，生成可检查的示例结果。"""
    if Path(output_directory).exists():
        raise FileExistsError("请指定尚不存在的输出目录，保留已有结果。")
    return engine.create_crop_set(INPUT / "workbench.jpg", output_directory, aspect_ratios=("1:1", "4:5", "16:9"), focus_point=(0.675, 0.48))
