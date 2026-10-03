# 全景照片拼接

将具有真实重叠区域的相邻照片拼接为更宽的视场。基于源图配准与融合，不生成未拍摄内容。

![已知重叠的拼接示例](examples/comparison.jpg)

图示为随附案例的实际处理输出。素材、参数和验证范围见文末。

## 1. 输入要求

输入至少两张有可靠重叠且包含新增视场的照片，按空间相邻顺序排列。圆柱投影可提供可靠焦距，参数单位为像素。执行规范见[SKILL.md](SKILL.md)。

> 按左到右顺序拼接这组远景照片，采用圆柱投影。保留有效画面，输出接缝图与有效区域蒙版。若焦距需要估计，请在报告中注明，不填补未拍摄区域。

## 2. 处理流程与依赖

[photo_panorama_stitcher.py](scripts/photo_panorama_stitcher.py)根据相邻照片的共同区域建立几何关系，再将新视场加入公共画布。

1. 检查空间顺序和投影参数。每张输入应与相邻帧有可匹配区域，并带来新增视场。
2. 提取SIFT特征；不可用时回退ORB。匹配经过比率筛选，RANSAC排除错误对应并估计单应变换。
3. 采用平面或圆柱投影组织公共画布，检查几何规模与有效覆盖。
4. 对重叠区进行亮度补偿，并以距离权重融合过渡。
5. 裁取完全有效区域，另存结果、接缝过渡图和配准记录。

NumPy承担变换及融合数组计算，OpenCV承担特征、匹配与投影，Pillow负责图像读写和联系表。运行要求为Python3.10+，版本见[requirements.txt](requirements.txt)。

## 3. 核心接口与参数

`analyze_panorama`检查相邻匹配与投影风险；`stitch_panorama`进行配准、融合和有效区域裁切。

下表列出关键参数。默认值与当前接口定义一致，完整参数以源码为准。

| 参数 | 默认值或要求 | 说明 |
| --- | --- | --- |
| `projection` | `planar` | 平面投影；宽视角旋转拍摄可选择`cylindrical`。 |
| `focal_length_px` | `None` | 圆柱投影使用的像素焦距；缺省时估计，需记录来源。 |

## 4. 调用示例

以下代码在本skill根目录的Python会话中运行，直接调用处理接口：

```python
from pathlib import Path
import sys

sys.path.insert(0, str(Path("scripts").resolve()))
from photo_panorama_stitcher import analyze_panorama, stitch_panorama

photos = ["left.jpg", "middle.jpg", "right.jpg"]
analysis = analyze_panorama(photos, projection="planar")
if not analysis["blockers"]:
    result = stitch_panorama(photos, "panorama-review", projection="planar")
```

基础示例使用planar模式，先调用`analyze_panorama`，有阻断项时停止；通过后调用`stitch_panorama`。更多参数见[调用示例](examples/basic_usage.py)，随附图片的实际调用见[reproduce.py](examples/reproduce.py)。

## 5. 交付文件与质量控制

### 5.1 文件与结果解释

`panorama_16bit.tif`与`panorama_preview.jpg`保存结果；`valid_area_mask.png`显示源图覆盖；`seam_transition_map.png`显示融合过渡；`stitch_contact_sheet.jpg`和`panorama_report.json`记录对齐与风险。

有效区域蒙版不是内容真实性认证。16位输出也不增加源图实际记录的细节。

### 5.2 参数选择与失败条件

planar用于较窄视角或近似平面主题；cylindrical用于宽视角旋转拍摄。圆柱焦距单位为像素，不能直接传毫米焦距；缺省估计值应在报告中说明。

匹配不足、空间顺序错误、画布规模异常或无完整有效裁切时停止。近距离多层景物和移动主体可能违反单应变换假设，表现为重影或断裂。空白区域只裁除，不生成补齐。

## 6. 示例与验证

基础示例是同一底图的两个裁片，重叠50%，使用平面模型拼接。它验证特征匹配和接缝处理，不验证真实多视角、视差或圆柱投影。查看[匹配与输出记录](examples/README.md)及[其他题材案例](examples/cases/README.md)。
