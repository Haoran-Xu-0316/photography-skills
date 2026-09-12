# 工作流衔接

## 推荐流程

导入前先筛。把存储卡内容拷到硬盘后立刻跑一遍，再导入Lightroom，这样目录里从一开始就带着星级，不用先建预览再筛。

第一步只分析并查看统计。

```python
from photo_cull import analyze_photos

analysis = analyze_photos(photo_directory, report_directory, preset="wildlife")
```

看两个数：判废比例和废片印象图。正常外拍的判废比例在一到三成。超过五成通常是阈值不适合当前题材或器材，比如老镜头本身就软；低于半成说明阈值太松，没起到作用。

第二步看废片印象图。这张图把所有被判废的缩略图拼在一起，扫一眼就能发现误杀。发现误杀就调阈值重跑，不要将就。

第三步使用新的报告目录显式写入XMP。

```python
from photo_cull import create_cull_sidecars

result = create_cull_sidecars(
    photo_directory,
    confirmed_report_directory,
    preset="wildlife",
)
```

第四步在Lightroom或Capture One里按星级过滤，只看四星和五星，从中挑最终成片。三星的待定片在时间充裕时再回头看。

不满意时不要自动删除既有XMP。先在独立副本或软件内复核，再由用户决定如何回退评级；本Skill不提供批量删除入口。

## Lightroom

导入时在文件处理面板勾选自动读取XMP，或对已导入的照片选中后用元数据菜单里的从文件读取元数据。星级和色标会直接出现。

Lightroom默认不自动监视XMP变化，重跑本工具后需要手动再读一次。

## Capture One

对RAW文件，Capture One默认读取同名XMP。在编辑菜单的偏好设置里确认元数据选项卡下已开启自动同步边车。

## Bridge 与 digiKam

两者都原生读XMP边车，无需额外设置。

## 确认候选

完成人工复核后，按需调用`create_cull_sidecars`写入XMP评级，再在Lightroom中按星级查看候选。保留原始文件，最终取舍由用户确认。

## 不要做的事

不要用本工具直接删文件。它只写星级，删除动作必须由人在看过之后执行。

不要跳过废片印象图这一步。自动判废没有复核就是危险操作。

不要把三星待定片当成废片批量删。待定的含义是机器判不了，不是判为坏。
