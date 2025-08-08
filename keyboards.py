from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

class Keyboards:
    @staticmethod
    def get_admin_keyboard():
        kb = ReplyKeyboardBuilder()
        kb.button(text="Добавить пользователя")
        kb.button(text="Удалить пользователя")
        kb.button(text="Обновить базу")
        kb.button(text="Ближайшие дни рождения")
        kb.adjust(2)
        return kb.as_markup(resize_keyboard=True)

    @staticmethod
    def get_user_keyboard():
        kb = ReplyKeyboardBuilder()
        kb.button(text="Ближайшие дни рождения")
        return kb.as_markup(resize_keyboard=True)