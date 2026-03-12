from datetime import date

from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder


def get_worker_schedule_publish_keyboard(tour_date: date) -> InlineKeyboardMarkup:
    """
    Инлайн‑клавиатура под картинкой расписания работников:
    - Опубликовать всем работникам
    - Заменить (перезагрузить из таблицы и пересохранить черновик)
    - Отменить (удалить черновик)
    """
    d_str = tour_date.isoformat()
    builder = InlineKeyboardBuilder()
    builder.button(
        text="✅ Опубликовать",
        callback_data=f"worker_sched:publish:{d_str}",
    )
    builder.button(
        text="🔄 Заменить",
        callback_data=f"worker_sched:replace:{d_str}",
    )
    builder.button(
        text="❌ Отменить",
        callback_data=f"worker_sched:cancel:{d_str}",
    )
    builder.adjust(1, 2)
    return builder.as_markup()

