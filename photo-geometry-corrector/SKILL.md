---
name: photo-geometry-corrector
description: 校正照片的水平倾斜、四点透视和基于已知相机标定参数的镜头几何畸变。适用于地平线倾斜、建筑垂直线汇聚、文件扫描矫正和已有内参畸变校正；不用于审美构图裁切、噪点暗角色差修复、内容感知补边或生成式扩图。
metadata:
  runtime: 需要Python3.10+及requirements.txt中的依赖；核心流程完全离线；最终几何验收要求执行环境能够查看校正前后图像和有效像素边界。
---

# 照片几何校正

## 运行契约

- 核心入口是本目录的`SKILL.md`。`scripts`、`references`和`assets`路径必须相对本Skill根目录解析，不依赖特定模型、厂商工具名或提示词语法。
- 自动分析和校正需要Python3.10+和`requirements.txt`中的依赖。执行代理应将本Skill的`scripts`目录临时加入当前Python进程的模块搜索路径，再调用下述接口。
- 最终验收需要查看校正前后图像和有效像素边界。无法查看图像的模型只能输出变换计划或待复核结果，不能宣称几何校正通过。

## 定位

只修正照片中可定义、可复现的几何关系，回答“线是否水平、平面是否方正、标定畸变是否得到校正”。原图只读，不改变颜色和摄影内容。

本skill与相邻能力的边界：

- 只裁掉几何变换产生的无效边，不重新决定审美取景范围。
- 只处理坐标几何与标定镜头畸变，不处理噪点、暗角、横向色差和坏点。

## 模式

- `horizon`：检测或接收水平线角度，旋转照片并裁掉旋转产生的无效边。
- `perspective`：把用户确认的四点平面映射为矩形，适合建筑立面、画框和文档。
- `calibrated-distortion`：使用用户提供的相机矩阵与畸变系数校正镜头几何畸变，不凭照片猜测镜头参数。

## 工作流

1. 读取照片方向和哈希，确认原图保持只读。
2. 调用`analyze_geometry`检测近水平直线。自动检测置信度不足时停止；置信度达标也只能作为建议角度，执行代理必须先查看对应直线，再显式提供角度或设置`automatic_detection_confirmed=True`。
3. 根据任务调用单一校正接口，不把多个变换静默叠加。
4. 输出校正副本和几何报告JSON，记录变换矩阵、输入参数、输出尺寸与无效边裁切范围。
5. 检查原图哈希、输出可读性和有效像素范围。未通过时不得把结果称为完成。

## 程序化接口

本skill不提供面向用户的命令行工具。将`scripts`目录加入Python路径后调用：

```python
from photo_geometry_corrector import (
    analyze_geometry,
    correct_calibrated_distortion,
    correct_horizon,
    correct_perspective,
)

analysis = analyze_geometry(input_path)
leveled = correct_horizon(
    input_path,
    output_dir,
    angle_degrees=analysis["horizon"]["angle_degrees"],
)
rectified = correct_perspective(input_path, output_dir, source_points)
undistorted = correct_calibrated_distortion(
    input_path,
    output_dir,
    camera_matrix,
    distortion_coefficients,
)
```

## 约束

- 自动水平校正只使用可靠的近水平长直线；弱纹理、曲线主导或意见不一致时必须停止。
- 自动检测达到阈值也不能静默执行。`angle_degrees=None`时必须显式传入`automatic_detection_confirmed=True`，表示执行代理已经查看并确认检测线确实代表真实水平。
- 四点透视必须由用户提供或经用户确认，顺序固定为左上、右上、右下、左下。
- 标定畸变校正必须有实际相机矩阵和畸变系数，不从单张普通照片臆测参数。
- 不做三分法、主体重心、留白或社交画幅优化。
- 不生成、镜像、拉伸或内容感知填充无效区域。裁切仅用于移除几何变换产生的无效边。
- 输出路径不得与输入相同；输出已存在时默认失败。
- 脚本中的`status="pass"`只表示文件可解码、原图哈希未变等机械检查通过。报告的`acceptance_status`在视觉复核前保持`visual-review-required`，不能解释为最终视觉验收。

坐标、角度、畸变参数和有效边规则见[references/geometry-rules.md](references/geometry-rules.md)。
