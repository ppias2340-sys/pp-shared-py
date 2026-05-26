from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def row_button(text: str, callback_data: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text, callback_data=callback_data)]


def back_button(callback_data: str = "menu:back") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("← Volver", callback_data=callback_data)]])


def main_menu(rows: list[list[tuple[str, str]]]) -> InlineKeyboardMarkup:
    keyboard = []
    for row in rows:
        keyboard.append([InlineKeyboardButton(text, callback_data=cb) for text, cb in row])
    return InlineKeyboardMarkup(keyboard)
