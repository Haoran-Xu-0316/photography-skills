"""Compose a photograph and an accepted miniature; never generate or retouch either."""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps


def _load_image(path):
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert("RGBA")
        background = Image.new("RGBA", image.size, "white")
        background.alpha_composite(image)
        return background.convert("RGB")


def compose_poster(
    photo_path, miniature_path, output_path, *, size=(1500, 2000),
    photo_fraction=0.5, photo_fit="contain", title="", subtitle="",
    font_path=None,
):
    """Return a new PNG path. Inputs are read-only; existing output is rejected.

    photo_fit='contain' preserves the entire photo with white padding;
    'cover' center-crops and requires the caller to visually approve the crop.
    Use photo_fraction to preserve a critical subject without forced cropping.
    font_path must support all requested glyphs; inspect the final rendering.
    """
    photo_path, miniature_path, output_path = map(
        Path, (photo_path, miniature_path, output_path)
    )
    if output_path.resolve() in (photo_path.resolve(), miniature_path.resolve()):
        raise ValueError("Output must not replace either source image")
    if output_path.exists():
        raise FileExistsError(output_path)
    if output_path.suffix.lower() != ".png":
        raise ValueError("Output must be PNG")
    if len(size) != 2 or any(type(v) is not int or v < 400 for v in size):
        raise ValueError("size must contain two integers of at least 400 pixels")
    if not 0.3 <= photo_fraction <= 0.65:
        raise ValueError("photo_fraction must be between 0.3 and 0.65")
    if photo_fit not in ("contain", "cover"):
        raise ValueError("photo_fit must be contain or cover")
    if any("\n" in text for text in (title, subtitle)):
        raise ValueError("Captions must be single-line strings")
    if (title or subtitle) and not font_path:
        raise ValueError("A font with the requested glyphs is required for captions")

    width, height = size
    split = round(height * photo_fraction)
    photo, miniature = _load_image(photo_path), _load_image(miniature_path)
    canvas = Image.new("RGB", size, "white")
    if photo_fit == "cover":
        fitted = ImageOps.fit(photo, (width, split), Image.Resampling.LANCZOS)
    else:
        fitted = ImageOps.contain(photo, (width, split), Image.Resampling.LANCZOS)
    canvas.paste(fitted, ((width - fitted.width) // 2, (split - fitted.height) // 2))

    # Reserve space before laying out the model, so captions cannot overlap it.
    caption_height = round(height * 0.10) if title or subtitle else 0
    margin = round(height * 0.025)
    available_height = height - split - caption_height - 2 * margin
    fitted_model = ImageOps.contain(
        miniature, (round(width * 0.68), available_height), Image.Resampling.LANCZOS
    )
    canvas.paste(fitted_model, (
        (width - fitted_model.width) // 2,
        split + margin + (available_height - fitted_model.height) // 2,
    ))

    draw = ImageDraw.Draw(canvas)
    for text, y, point_size in (
        (title, height - caption_height + margin // 2, round(width * 0.031)),
        (subtitle, height - caption_height // 2, round(width * 0.016)),
    ):
        if not text:
            continue
        font = ImageFont.truetype(str(font_path), point_size)
        while draw.textbbox((0, 0), text, font=font)[2] > width * 0.84:
            point_size -= 1
            if point_size < 10:
                raise ValueError("Caption is too long; shorten it")
            font = ImageFont.truetype(str(font_path), point_size)
        box = draw.textbbox((0, 0), text, font=font)
        draw.text(((width - (box[2] - box[0])) / 2 - box[0], y - box[1]),
                  text, font=font, fill="#626569")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation also prevents accidental replacement between validation and save.
    with output_path.open("xb") as stream:
        canvas.save(stream, format="PNG")
    return output_path
