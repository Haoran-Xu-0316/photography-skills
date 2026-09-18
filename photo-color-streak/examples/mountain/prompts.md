# mountain示例实际提示

输入为本次生成的虚构摄影场景，随后将该输入作为唯一编辑目标执行风格重构。两次调用均使用运行环境内置图像生成能力。提示不保证随机生成逐像素复现。

## 输入素材生成

```text
Use case: photorealistic-natural. Generate a synthetic source photograph for an image-editing tutorial. Portrait 3:4. A fictional alpine lake, one prominent snow-covered triangular peak near center-left, sunlit brown forested slope descending from upper right towards center-left, still dark teal lake reflecting the same peak and slope, two small dark wooden cabins at bottom left. Upper third pale blue grey sky. Natural detailed travel photography, coherent reflection and geography. Full continuous ordinary photo, no text, no watermarks, NO streaks, NO collage, NO pixel stretch.
```

## 色带重构

```text
Use case: style-transfer. Input image 1 is the sole scene source and edit target. Produce a portrait 3:4 photo-color-streak artwork. Preserve the snow peak center-left, golden forested right slope, shoreline and their connected calm lake reflections, plus both foreground cabins; keep their photographic texture, positions, view and lighting. Make a single connected retained photo region with roughly vertical side cuts near 10% and 90% width, continuing to bottom, and an irregular upper edge closely following the real mountain silhouette. The snow peak and right slope protrude above the retained photo region naturally. Replace entire sky AND outside side margins with full-width horizontal pixel-stretch color bands behind the photo region: pale blue-grey and cream across the upper field, white and slate grey near snowy mountain levels, warm ochre and forest-dark thin bands at slope levels, deep teal and pale reflection streaks at lake levels. Fine horizontal lines interleaved with broad calm bands. Clearly abstract stretched background, not realistic sky, not just smooth gradient. Keep lake and mountain reflections continuous inside the photo region. No extra mountain or cabin, no distorted geometry, no blurred subject, no paper, no white outline, no border or shadow, no text. Single finished artwork.
```
