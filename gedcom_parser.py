import logging
from datetime import datetime, date
from gedcom.parser import Parser
from gedcom.element.individual import IndividualElement


class GedcomManager:
    def __init__(self, file_path):
        self.parser = Parser()
        self.parser.parse_file(file_path)
        self.root_child_elements = self.parser.get_root_child_elements()

    def get_birthdays_today(self):
        today = date.today()
        birthdays = []

        for element in self.root_child_elements:
            if isinstance(element, IndividualElement):
                try:
                    birth_date = self._get_birth_date(element)
                    if birth_date and birth_date.month == today.month and birth_date.day == today.day:
                        name = self._get_full_name(element)
                        age = self._calculate_age(birth_date)
                        birthdays.append((name, age))
                except ValueError as e:
                    logging.warning(f"Ошибка обработки даты для {self._get_full_name(element)}: {e}")

        return birthdays

    def get_upcoming_birthdays(self, days_ahead=3):
        today = date.today()
        upcoming_birthdays = []

        for element in self.root_child_elements:
            if isinstance(element, IndividualElement):
                try:
                    birth_date = self._get_birth_date(element)
                    if birth_date:
                        try:
                            next_birthday = date(today.year, birth_date.month, birth_date.day)
                        except ValueError:
                            logging.warning(f"Некорректная дата для {self._get_full_name(element)}")
                            continue

                        if next_birthday < today:
                            next_birthday = date(today.year + 1, birth_date.month, birth_date.day)

                        days_until_birthday = (next_birthday - today).days
                        if days_until_birthday >= 0:  # Учитываем все будущие дни рождения
                            name = self._get_full_name(element)
                            age = self._calculate_age(birth_date)
                            upcoming_birthdays.append({
                                'name': name,
                                'age': age,
                                'days_left': days_until_birthday,
                                'birthday_date': next_birthday,
                                'birth_date': birth_date  # Добавляем дату рождения
                            })
                except Exception as e:
                    logging.warning(f"Ошибка обработки даты для {self._get_full_name(element)}: {e}")

        # Сортируем по количеству дней до дня рождения
        sorted_birthdays = sorted(upcoming_birthdays, key=lambda x: x['days_left'])

        # Если есть дни рождения в пределах days_ahead, возвращаем их, иначе ближайшие
        result = [b for b in sorted_birthdays if b['days_left'] <= days_ahead]
        if not result:
            result = sorted_birthdays[:3]  # Берём 3 ближайших, если в пределах days_ahead ничего нет

        return result

    def _get_birth_date(self, individual):
        birth_date_element = individual.get_birth_data()
        if birth_date_element and birth_date_element[0]:
            try:
                # Пробуем разные форматы даты
                date_formats = [
                    '%d %b %Y',  # день месяц год
                    '%b %d %Y',  # месяц день год
                    '%Y %b %d',  # год месяц день
                    '%d %m %Y',  # день месяц год (цифрами)
                ]

                for date_format in date_formats:
                    try:
                        return datetime.strptime(birth_date_element[0], date_format).date()
                    except ValueError:
                        continue

                # Если ни один формат не подошел
                logging.warning(f"Не удалось распознать дату: {birth_date_element[0]}")
                return None

            except (ValueError, TypeError, IndexError) as e:
                logging.warning(f"Ошибка парсинга даты: {e}")
                return None
        return None

    def _get_full_name(self, individual):
        try:
            name_elements = individual.get_name()
            if name_elements and len(name_elements) >= 2:
                return f"{name_elements[0]} {name_elements[1]}"
        except Exception as e:
            logging.warning(f"Ошибка получения имени: {e}")
        return "Неизвестное имя"

    def _calculate_age(self, birth_date):
        today = date.today()
        age = today.year - birth_date.year

        # Проверяем, был ли уже день рождения в этом году
        birthday_this_year = date(today.year, birth_date.month, birth_date.day)

        # Уменьшаем возраст на 1, если день рождения ещё не наступил
        if today < birthday_this_year:
            age -= 1

        return age