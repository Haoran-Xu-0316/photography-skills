# city示例实际提示

输入为本次生成的虚构摄影场景，随后将该输入作为唯一编辑目标执行风格重构。两次调用均使用运行环境内置图像生成能力。提示不保证随机生成逐像素复现。

## 输入素材生成

```text
Use case: photorealistic-natural. Generate a synthetic source photograph for an image-editing tutorial, not an artwork with effects. Portrait 3:4. A fictional waterfront city skyline at amber sunset, a single tall slim glass tower slightly right of center with a sloping crown, a shorter stepped stone tower on its left, clustered dark midrise buildings across the bottom. Upper 45 percent calm gold hazy sky, pale gold clouds, dark brown foreground. Natural telephoto travel photograph, coherent architecture and fine windows. Full continuous ordinary photo, no borders, no text, no watermarks, NO streaks, NO collage, NO pixel stretch.
```

## 色带重构

```text
Use case: style-transfer. Input image 1 is the edit target and sole scene source. Create a photo-color-streak artwork, same portrait 3:4 aspect ratio. Keep the tall slanted-crown glass tower right of center, shorter stepped stone tower left, connected foreground buildings and waterfront in their original positions and proportions with crisp photographic surfaces and amber sunlight. Retain one connected photographic island occupying roughly x=15% to 85% and extending to the bottom, its upper border following the stepped building silhouettes; the tall tower rises far above that border. Replace ALL surrounding sky and outer side strips with horizontal pixel-stretch color bands that run continuously left to right behind the photographic island. Upper bands pale warm grey-gold, middle amber with thin cream highlights, lower bands brown and near-black with gold lines aligned to the scene's original vertical colors. Broad quiet bands interleaved with very fine horizontal scanline-like streaks, clearly visible, no remaining realistic clouds in the background. Sharp natural subject edges, no white outline, no torn paper, no drop shadow. Do not blur the buildings, do not bend the tower, do not add buildings. No text, no frame, no new decoration. Deliver one completed artwork, not a comparison sheet.
```
