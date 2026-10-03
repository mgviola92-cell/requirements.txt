# =========================================================
# 🎨 DYNAMIC CARD GENERATOR
# =========================================================

from io import BytesIO
from pathlib import Path

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
    ImageFilter,
)

from core.asset_manager import (
    get_asset_path,
)


# =========================================================
# ⚙️ DEFAULT CARD SETTINGS
# =========================================================

DEFAULT_WIDTH = 1200
DEFAULT_HEIGHT = 675

DEFAULT_PADDING = 60
DEFAULT_RADIUS = 36


# =========================================================
# 🔤 FONT HELPER
#
# Font asset မရှိသေးရင် Pillow default font သုံးမည်။
# နောက် Asset Phase မှာ proper fonts ချိတ်မည်။
# =========================================================

def load_font(
    size=40,
    font_path=None
):
    try:
        if font_path:
            path = Path(font_path)

            if path.exists():
                return ImageFont.truetype(
                    str(path),
                    int(size)
                )

        return ImageFont.load_default()

    except Exception:
        return ImageFont.load_default()


# =========================================================
# 🖼️ CREATE BLANK CARD
# =========================================================

def create_card(
    width=DEFAULT_WIDTH,
    height=DEFAULT_HEIGHT,
    background=(24, 26, 32, 255)
):
    width = max(1, int(width))
    height = max(1, int(height))

    return Image.new(
        "RGBA",
        (width, height),
        background
    )


# =========================================================
# 🖼️ OPEN IMAGE SAFELY
# =========================================================

def open_image(
    image_source,
    mode="RGBA"
):
    if image_source is None:
        return None

    try:
        if isinstance(
            image_source,
            Image.Image
        ):
            return image_source.convert(mode)

        path = Path(image_source)

        if not path.exists():
            return None

        image = Image.open(path)
        return image.convert(mode)

    except Exception as e:
        print(
            f"❌ Image Open Error: {e}"
        )
        return None


# =========================================================
# ✂️ COVER RESIZE
#
# Image ကို box ထဲမှာ crop/cover လုပ်ပေးမည်။
# =========================================================

def resize_cover(
    image,
    target_width,
    target_height
):
    if image is None:
        return None

    target_width = max(
        1,
        int(target_width)
    )

    target_height = max(
        1,
        int(target_height)
    )

    source_width, source_height = (
        image.size
    )

    scale = max(
        target_width / source_width,
        target_height / source_height
    )

    new_width = int(
        source_width * scale
    )

    new_height = int(
        source_height * scale
    )

    resized = image.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS
    )

    left = (
        new_width - target_width
    ) // 2

    top = (
        new_height - target_height
    ) // 2

    return resized.crop(
        (
            left,
            top,
            left + target_width,
            top + target_height
        )
    )


# =========================================================
# 🌄 ADD BACKGROUND IMAGE
# =========================================================

def add_background_image(
    card,
    image_source,
    blur=0,
    darken=0
):
    image = open_image(
        image_source
    )

    if image is None:
        return card

    image = resize_cover(
        image,
        card.width,
        card.height
    )

    if blur > 0:
        image = image.filter(
            ImageFilter.GaussianBlur(
                radius=float(blur)
            )
        )

    if darken > 0:
        darken = max(
            0,
            min(255, int(darken))
        )

        overlay = Image.new(
            "RGBA",
            card.size,
            (
                0,
                0,
                0,
                darken
            )
        )

        image = Image.alpha_composite(
            image,
            overlay
        )

    return Image.alpha_composite(
        card,
        image
    )


# =========================================================
# ▢ ROUNDED PANEL
# =========================================================

def draw_panel(
    card,
    box,
    fill=(20, 22, 28, 220),
    radius=DEFAULT_RADIUS,
    outline=None,
    outline_width=0
):
    draw = ImageDraw.Draw(
        card
    )

    draw.rounded_rectangle(
        box,
        radius=int(radius),
        fill=fill,
        outline=outline,
        width=int(outline_width)
    )

    return card


# =========================================================
# 📝 DRAW TEXT
# =========================================================

def draw_text(
    card,
    text,
    position,
    size=40,
    fill=(255, 255, 255, 255),
    font_path=None,
    anchor=None
):
    draw = ImageDraw.Draw(
        card
    )

    font = load_font(
        size=size,
        font_path=font_path
    )

    draw.text(
        position,
        str(text),
        font=font,
        fill=fill,
        anchor=anchor
    )

    return card


# =========================================================
# 📊 PROGRESS BAR
# =========================================================

def draw_progress_bar(
    card,
    box,
    percent,
    background=(
        60,
        63,
        72,
        220
    ),
    foreground=(
        255,
        255,
        255,
        255
    ),
    radius=18
):
    draw = ImageDraw.Draw(
        card
    )

    left, top, right, bottom = box

    percent = max(
        0,
        min(
            100,
            float(percent)
        )
    )

    draw.rounded_rectangle(
        box,
        radius=radius,
        fill=background
    )

    width = (
        right - left
    )

    progress_width = int(
        width * percent / 100
    )

    if progress_width > 0:
        progress_box = (
            left,
            top,
            left + progress_width,
            bottom
        )

        draw.rounded_rectangle(
            progress_box,
            radius=radius,
            fill=foreground
        )

    return card


# =========================================================
# 🖼️ PASTE IMAGE
# =========================================================

def paste_image(
    card,
    image_source,
    box,
    rounded_radius=0
):
    image = open_image(
        image_source
    )

    if image is None:
        return card

    left, top, right, bottom = box

    width = max(
        1,
        right - left
    )

    height = max(
        1,
        bottom - top
    )

    image = resize_cover(
        image,
        width,
        height
    )

    if rounded_radius > 0:
        mask = Image.new(
            "L",
            (width, height),
            0
        )

        mask_draw = ImageDraw.Draw(
            mask
        )

        mask_draw.rounded_rectangle(
            (
                0,
                0,
                width,
                height
            ),
            radius=int(
                rounded_radius
            ),
            fill=255
        )

        image.putalpha(
            mask
        )

    card.alpha_composite(
        image,
        dest=(
            int(left),
            int(top)
        )
    )

    return card


# =========================================================
# 💾 CARD → BYTES
#
# Telegram send_photo() အတွက်
# BytesIO ပြန်ပေးမည်။
# =========================================================

def card_to_bytes(
    card,
    image_format="PNG",
    quality=90
):
    buffer = BytesIO()

    image_format = (
        image_format.upper()
    )

    save_kwargs = {}

    if image_format in (
        "JPEG",
        "JPG",
        "WEBP"
    ):
        save_kwargs["quality"] = int(
            quality
        )

    image = card

    if image_format in (
        "JPEG",
        "JPG"
    ):
        image = card.convert(
            "RGB"
        )

    image.save(
        buffer,
        format=image_format,
        **save_kwargs
    )

    buffer.seek(0)

    return buffer


# =========================================================
# 💾 SAVE CARD
#
# Debug/testing အတွက်။
# =========================================================

def save_card(
    card,
    output_path
):
    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True
    )

    card.save(
        output_path
    )

    return output_path
