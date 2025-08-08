import os
import sqlite3
import logging
from datetime import datetime, date
from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(admin_id) for admin_id in os.getenv('ADMIN_IDS', '').split(',')]
DATABASE_FILE = 'drevo.ged'
SQLITE_DB = 'genealogy.db'

# Настройка логирования
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# Класс для преобразования GEDCOM в SQLite
class GedcomToSqliteConverter:
    def __init__(self, gedcom_file, db_file=SQLITE_DB):
        self.gedcom_file = gedcom_file
        self.db_file = db_file
        self.parser = Parser()
        self.convert_to_sqlite()

    def convert_to_sqlite(self):
        """Парсит GEDCOM и сохраняет данные в SQLite."""
        self.parser.parse_file(self.gedcom_file)
        root_child_elements = self.parser.get_root_child_elements()

        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS individuals (
                id TEXT PRIMARY KEY,
                full_name TEXT,
                birth_date TEXT
            )
        ''')

        for element in root_child_elements:
            if isinstance(element, IndividualElement):
                try:
                    individual_id = element.get_pointer()
                    full_name = self._get_full_name(element)
                    birth_date = self._get_birth_date(element)

                    if birth_date:
                        birth_date_str = birth_date.strftime('%Y-%m-%d')
                        cursor.execute('''
                            INSERT OR REPLACE INTO individuals (id, full_name, birth_date)
                            VALUES (?, ?, ?)
                        ''', (individual_id, full_name, birth_date_str))
                except Exception as e:
                    logger.warning(f"Ошибка обработки {full_name}: {e}")

        conn.commit()
        conn.close()
        logger.info(f"Данные из {self.gedcom_file} успешно сохранены в {self.db_file}")

    def _get_birth_date(self, individual):
        birth_date_element = individual.get_birth_data()
        if birth_date_element and birth_date_element[0]:
            try:
                date_formats = ['%d %b %Y', '%b %d %Y', '%Y %b %d', '%d %m %Y']
                for date_format in date_formats:
                    try:
                        parsed_date = datetime.strptime(birth_date_element[0], date_format).date()
                        date(parsed_date.year, parsed_date.month, parsed_date.day)
                        return parsed_date
                    except ValueError:
                        continue
                logger.warning(f"Не удалось распознать дату: {birth_date_element[0]}")
                return None
            except ValueError as e:
                logger.warning(f"Некорректная дата рождения для {self._get_full_name(individual)}: {e}")
                return None
            except Exception as e:
                logger.warning(f"Ошибка парсинга даты: {e}")
                return None
        return None

    def _get_full_name(self, individual):
        try:
            name_elements = individual.get_name()
            if name_elements and len(name_elements) >= 2:
                return f"{name_elements[0]} {name_elements[1]}"
        except Exception as e:
            logger.warning(f"Ошибка получения имени: {e}")
        return "Неизвестное имя"


# Класс для работы с данными из SQLite
class GedcomManager:
    def __init__(self, db_file=SQLITE_DB):
        self.db_file = db_file

    def get_birthdays_today(self):
        today = date.today()
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT full_name, birth_date FROM individuals
            WHERE strftime('%m-%d', birth_date) = strftime('%m-%d', ?)
        ''', (today.strftime('%Y-%m-%d'),))

        birthdays = []
        for row in cursor.fetchall():
            name, birth_date_str = row
            birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
            age = today.year - birth_date.year
            birthdays.append((name, age))

        conn.close()
        return birthdays

    def get_upcoming_birthdays(self, days_ahead=3):
        today = date.today()
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()

        cursor.execute('SELECT full_name, birth_date FROM individuals')
        upcoming_birthdays = []

        for row in cursor.fetchall():
            name, birth_date_str = row
            try:
                birth_date = datetime.strptime(birth_date_str, '%Y-%m-%d').date()
                try:
                    next_birthday = date(today.year, birth_date.month, birth_date.day)
                except ValueError:
                    logger.warning(f"Некорректная дата для {name}: {birth_date}")
                    continue

                if next_birthday < today:
                    try:
                        next_birthday = date(today.year + 1, birth_date.month, birth_date.day)
                    except ValueError:
                        logger.warning(f"Некорректная дата в следующем году для {name}: {birth_date}")
                        continue

                days_until_birthday = (next_birthday - today).days
                if days_until_birthday >= 0:
                    age = next_birthday.year - birth_date.year
                    upcoming_birthdays.append({
                        'name': name,
                        'age': age,
                        'days_left': days_until_birthday,
                        'birthday_date': next_birthday,
                        'birth_date': birth_date
                    })
            except Exception as e:
                logger.warning(f"Ошибка обработки записи для {name}: {e}")

        conn.close()
        sorted_birthdays = sorted(upcoming_birthdays, key=lambda x: x['days_left'])
        result = [b for b in sorted_birthdays if b['days_left'] <= days_ahead]
        if not result:
            result = sorted_birthdays[:3]

        return result

    def _calculate_age(self, birth_date):
        today = date.today()
        age = today.year - birth_date.year
        try:
            if today < date(today.year, birth_date.month, birth_date.day):
                age -= 1
        except ValueError:
            pass
        return age


# Клавиатуры
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder


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


# Основной код бота
import asyncio
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State


class AdminStates(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_delete_user_id = State()


class GenealogyBot:
    def __init__(self):
        self.bot = Bot(BOT_TOKEN)
        self.dp = Dispatcher()
        GedcomToSqliteConverter(DATABASE_FILE)
        self.gedcom_manager = GedcomManager(SQLITE_DB)
        self.setup_routes()

    def setup_routes(self):
        self.dp.message(Command("start"))(self.start_command)
        self.dp.message(F.text == "Ближайшие дни рождения")(self.upcoming_birthdays)

        admin_router = Router()
        admin_router.message.filter(F.from_user.id.in_(ADMIN_IDS))
        admin_router.message(F.text == "Добавить пользователя")(self.add_user)
        admin_router.message(F.text == "Удалить пользователя")(self.delete_user)
        admin_router.message(F.text == "Обновить базу")(self.update_database)
        self.dp.include_router(admin_router)

    async def start_command(self, message: Message):
        if message.from_user.id in ADMIN_IDS:
            await message.answer("Привет, администратор!",
                                 reply_markup=Keyboards.get_admin_keyboard())
        else:
            await message.answer("Привет!",
                                 reply_markup=Keyboards.get_user_keyboard())

    async def upcoming_birthdays(self, message: Message):
        birthdays = self.gedcom_manager.get_upcoming_birthdays()
        if birthdays:
            response = "Ближайшие дни рождения:\n\n"
            for birthday in birthdays:
                response += (f"{birthday['name']}, исполнится {birthday['age']} лет\n"
                             f"Дата рождения: {birthday['birth_date'].strftime('%d.%m.%Y')}\n"
                             f"Дата: {birthday['birthday_date'].strftime('%d.%m.%Y')}\n"
                             f"Осталось дней: {birthday['days_left']}\n\n")
            await message.answer(response.strip())
        else:
            await message.answer("Предстоящих дней рождения не найдено.")

    async def add_user(self, message: Message, state: FSMContext):
        await message.answer("Введите Telegram ID пользователя для добавления:")
        await state.set_state(AdminStates.waiting_for_user_id)

    async def delete_user(self, message: Message, state: FSMContext):
        await message.answer("Введите Telegram ID пользователя для удаления:")
        await state.set_state(AdminStates.waiting_for_delete_user_id)

    async def update_database(self, message: Message):
        try:
            GedcomToSqliteConverter(DATABASE_FILE)
            self.gedcom_manager = GedcomManager(SQLITE_DB)
            await message.answer("База данных успешно обновлена.")
            logger.info("Database updated successfully")
        except Exception as e:
            await message.answer(f"Ошибка обновления базы данных: {e}")
            logger.error(f"Database update error: {e}")

    async def daily_birthday_notifications(self):
        birthdays = self.gedcom_manager.get_birthdays_today()
        if birthdays:
            for user_id in ADMIN_IDS:
                for name, age in birthdays:
                    await self.bot.send_message(
                        user_id,
                        f"Сегодня день рождения у {name}, исполняется {age} лет!"
                    )

    async def start(self):
        scheduler = asyncio.create_task(self.schedule_daily_check())
        await self.dp.start_polling(self.bot)

    async def schedule_daily_check(self):
        while True:
            await self.daily_birthday_notifications()
            await asyncio.sleep(86400)  # Проверка каждые 24 часа


async def main():
    genealogy_bot = GenealogyBot()
    await genealogy_bot.start()


if __name__ == '__main__':
    asyncio.run(main())