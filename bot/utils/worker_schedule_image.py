"""Build worker schedule table image over background."""
from __future__ import annotations

import io
from datetime import date
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from bot.utils.date_parser import get_weekday_full, get_date_day_month


# Path to background (relative to this file: bot/utils/ -> bot/assets/)
_ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_BG_PNG = _ASSETS_DIR / "worker_schedule_bg.png"
_BG_JPG = _ASSETS_DIR / "worker_schedule_bg.jpg"

# Table layout (compact, table width 65% of image, centered)
HEADER_ROW = ["Время", "Оператор", "Камера", "Ц.Камера", "Комментатор", "Судьи"]
TABLE_WIDTH_RATIO = 0.65  # 65% of image width
MARGIN = 24
ROW_HEIGHT = 26
HEADER_HEIGHT = 32
TITLE_HEIGHT = 38
FONT_SIZE_TITLE = 22
FONT_SIZE_HEADER = 14
FONT_SIZE_CELL = 15  # чуть крупнее для читаемости
COLUMN_WEIGHTS = (1.2, 1.2, 1.2, 1.2, 1.4, 1.2)  # relative widths for 6 columns
BOTTOM_MARGIN = 24
# Горизонтальная обрезка: отступы как по вертикали, чуть больше для пропорций
H_CROP_MARGIN = 28
# Таблица чуть прозрачнее (alpha 165), фон просвечивает сильнее
COLOR_HEADER_BG = (70, 70, 70, 165)
COLOR_HEADER_TEXT = (255, 255, 255)
COLOR_ROW_BG = (255, 255, 255, 165)
COLOR_ROW_ALT = (245, 245, 245, 165)
COLOR_BREAK_BG = (220, 220, 220, 165)
COLOR_OUTLINE = (50, 50, 50, 130)
COLOR_OUTLINE_LIGHT = (200, 200, 200, 100)
COLOR_TEXT = (40, 40, 40)
COLOR_TITLE_WHITE = (255, 255, 255)
COLOR_TITLE_STROKE = (0, 0, 0)


def _find_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Пробуем более лёгкие шрифты (Condensed/Light), затем обычные — чтобы текст не выглядел тяжёлым."""
    candidates = [
        _ASSETS_DIR / "DejaVuSansCondensed.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"),
        _ASSETS_DIR / "DejaVuSans.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    ]
    for p in candidates:
        if p.exists():
            try:
                return ImageFont.truetype(str(p), size)
            except Exception:
                continue
    return ImageFont.load_default()


def _weekday_accusative(weekday_nom: str) -> str:
    """Винительный падеж: Суббота -> Субботу, Среда -> Среду, ..."""
    acc_map = {"Суббота": "Субботу", "Среда": "Среду", "Пятница": "Пятницу"}
    return acc_map.get(weekday_nom, weekday_nom)


def build_worker_schedule_image(
    tour_date: date,
    display_slots: list[dict[str, Any]],
    title: str | None = None,
) -> bytes:
    """
    Draw schedule table on background image, return PNG bytes.

    display_slots: list of dicts with keys
      time_slot, operator, camera, camera_c, commentator, referee (str),
      is_break (bool).
    """
    bg_path = _BG_PNG if _BG_PNG.exists() else _BG_JPG
    if not bg_path.exists():
        # No background: create white image 1000x1333
        img = Image.new("RGBA", (1000, 1333), color=(255, 255, 255, 255))
    else:
        img = Image.open(bg_path).convert("RGBA")
    width, height = img.size

    draw = ImageDraw.Draw(img)
    font_title = _find_font(FONT_SIZE_TITLE)
    font_header = _find_font(FONT_SIZE_HEADER)
    font_cell = _find_font(FONT_SIZE_CELL)

    # Высота контента: заголовок + таблица, чтобы центрировать по вертикали (эмблема по центру)
    title_block_h = MARGIN + FONT_SIZE_TITLE + 4 + FONT_SIZE_CELL + TITLE_HEIGHT
    table_block_h = HEADER_HEIGHT + len(display_slots) * ROW_HEIGHT
    content_height = title_block_h + table_block_h + BOTTOM_MARGIN
    y_start = max(0, (height - content_height) // 2)

    y = y_start + MARGIN
    # Заголовок: дата и день недели — всегда tour_date
    weekday = get_weekday_full(tour_date)
    weekday_acc = _weekday_accusative(weekday)
    title_line1 = title or f"Расписание работников на {weekday_acc}"
    date_line2 = get_date_day_month(tour_date)
    # Таблица по центру по горизонтали; заголовок текста — от левого края таблицы (x0 ниже)
    table_width_px = int(width * TABLE_WIDTH_RATIO)
    x0 = (width - table_width_px) // 2
    draw.text(
        (x0, y),
        title_line1,
        fill=COLOR_TITLE_WHITE,
        font=font_title,
        anchor="lt",
        stroke_width=1,
        stroke_fill=COLOR_TITLE_STROKE,
    )
    y += FONT_SIZE_TITLE + 4
    draw.text(
        (x0, y),
        date_line2,
        fill=COLOR_TITLE_WHITE,
        font=font_cell,
        anchor="lt",
        stroke_width=0,
        stroke_fill=COLOR_TITLE_STROKE,
    )
    y += TITLE_HEIGHT
    table_y_start = y

    # Ширина таблицы 65%, колонки по весам
    table_width = table_width_px
    total_w = sum(COLUMN_WEIGHTS)
    col_widths = [int(table_width * w / total_w) for w in COLUMN_WEIGHTS]
    col_widths[-1] = table_width - sum(col_widths[:-1])

    # Прозрачность таблицы: рисуем таблицу на отдельном RGBA-слое, затем compositing.
    # В Pillow rectangle() на основном изображении не смешивает альфу — рисуем overlay и вставляем с маской.
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw_table = ImageDraw.Draw(overlay)
    y = table_y_start

    # Header row
    for i, label in enumerate(HEADER_ROW):
        x = x0 + sum(col_widths[:i])
        cx = x + col_widths[i] // 2
        draw_table.rectangle(
            [x, y, x + col_widths[i], y + HEADER_HEIGHT],
            fill=COLOR_HEADER_BG,
            outline=COLOR_OUTLINE,
        )
        draw_table.text(
            (cx, y + HEADER_HEIGHT // 2),
            label,
            fill=COLOR_HEADER_TEXT,
            font=font_header,
            anchor="mm",
        )
    y += HEADER_HEIGHT

    # Data rows
    for idx, slot in enumerate(display_slots):
        row_h = ROW_HEIGHT
        is_break = slot.get("is_break", False)
        bg = COLOR_BREAK_BG if is_break else (COLOR_ROW_ALT if idx % 2 else COLOR_ROW_BG)
        cells = [
            slot.get("time_slot") or "",
            slot.get("operator") or "",
            slot.get("camera") or "",
            slot.get("camera_c") or "",
            slot.get("commentator") or "",
            slot.get("referee") or "",
        ]
        if is_break and not any(cells[1:]):
            cells[1] = "Перерыв"
        for i, cell_text in enumerate(cells):
            x = x0 + sum(col_widths[:i])
            draw_table.rectangle(
                [x, y, x + col_widths[i], y + row_h],
                fill=bg,
                outline=COLOR_OUTLINE_LIGHT,
            )
            draw_table.text(
                (x + 6, y + row_h // 2),
                str(cell_text)[:20],
                fill=COLOR_TEXT,
                font=font_cell,
                anchor="lm",
            )
        y += row_h

    # Накладываем полупрозрачную таблицу на фон (альфа смешивается)
    img = Image.alpha_composite(img, overlay)

    # Обрезка по блоку контента: по вертикали и по горизонтали (таблица — главное, отступы как по вертикали, чуть больше)
    crop_bottom = min(y_start + content_height, height)
    crop_left = max(0, x0 - H_CROP_MARGIN)
    crop_right = min(width, x0 + table_width + H_CROP_MARGIN)
    img = img.crop((crop_left, y_start, crop_right, crop_bottom))

    # Save to bytes (PNG supports RGBA)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
