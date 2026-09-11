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
engine = import_module("photo_panorama_stitcher")


def reproduce_example(output_directory: str | Path) -> dict:
    """调用原有处理接口，生成可检查的示例结果。"""
    if Path(output_directory).exists():
        raise FileExistsError("请指定尚不存在的输出目录，保留已有结果。")
    paths = [INPUT / "left.png", INPUT / "right.png"]
    analysis = engine.analyze_panorama(paths, projection="planar")
    if analysis["blockers"]:
        return {"analysis": analysis, "result": None}
    return {"analysis": analysis, "result": engine.stitch_panorama(paths, output_directory, projection="planar")}
