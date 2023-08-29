import sqlite3 as sl
import logger
from datetime import timezone, timedelta
from contextlib import closing
from apscheduler.job import Job


class Database:

    def __init__(self, path_to_db: str) -> None:
        self.__name = path_to_db

    def _create_table(self, table_name: str, table_cols: dict[str, str]) -> None:
        """
        Метод для создания таблиц
        :param table_name: название таблицы
        :param table_cols: словарь { названия_столбца: тип_столбца }
        """
        with closing(sl.connect(self.__name)) as conn:      # авто-закрытие sl.Connection
            with conn:                                      # авто-коммит sl.connect().commit()
                with closing(conn.cursor()) as curs:        # авто-закрытие sl.Cursor

                    cols_name_type = ""

                    for cols_name in table_cols:
                        cols_name_type += cols_name + ' ' + table_cols[cols_name] + ', '

                    cols_name_type = cols_name_type[:len(cols_name_type) - 2]     # стираем ', ' в конце строки

                    curs.execute(f"CREATE TABLE IF NOT EXISTS '{table_name}' ( {cols_name_type} )")

    def _insert_values_into_table(self, table_name: str, values: list[dict[str]]) -> None:
        """
        Метод для вставки значений в таблицу
        :param table_name: название таблицы
        :param values: массив из словарей { название_столбца: вставляемое_значение }
        """
        with closing(sl.connect(self.__name)) as conn:
            with conn:
                with closing(conn.cursor()) as curs:

                    values_names = ""
                    amount_of_values = ""
                    vals: list[tuple] = []

                    for value in values[0]:
                        values_names += f"{value}, "
                        amount_of_values += "?, "

                    for value in values:
                        for key in value:
                            if str(type(value[key])) == "<class 'bool'>":
                                value[key] = 1 if value[key] else 0
                        vals.append(tuple(value.values()))

                    values_names = values_names[:len(values_names) - 2]
                    amount_of_values = amount_of_values[:len(amount_of_values) - 2]

                    curs.executemany(f"INSERT OR REPLACE INTO '{table_name}' ({values_names}) "
                                     f"VALUES({amount_of_values});", vals)

    def _update_values_in_table(self, table_name: str, values: dict[str], condition: str) -> None:
        """
        Метод для обновления значений в таблице
        :param table_name: название таблицы
        :param values: словарь новых значений { название_столбца: новое_значение }
        :param condition: условие для определения строки для вставляемых значений
        """
        with closing(sl.connect(self.__name)) as conn:
            with conn:
                with closing(conn.cursor()) as curs:

                    new_values = ""

                    for key in values:
                        if str(type(values[key])) == "<class 'bool'>":
                            values[key] = 1 if values[key] else 0
                        new_values += f"{key} = ?, "

                    vals: tuple = tuple(values.values())
                    new_values = new_values[:len(new_values) - 2]

                    curs.execute(f"UPDATE {table_name} SET {new_values} WHERE {condition} ", vals)

    def _select_values_from_table(self, table_name: str, cols: str | list[str], condition: str = None) -> list[tuple]:
        """
        Метод для извлечения значений из таблицы
        :param table_name: название таблицы
        :param cols: извлекаемые столбцы
        :param condition: условие для определения конкретной извлекаемой строки
        :return: список из кортежей с извлеченными значениями или пустой список, если таблица пуста или ее нет в базе
        """
        with closing(sl.connect(self.__name)) as conn:
            with conn:
                with closing(conn.cursor()) as curs:

                    check_existance_of_table = \
                        f"SELECT count(name) FROM sqlite_master WHERE type = 'table' AND name = '{table_name}'"
                    if curs.execute(check_existance_of_table).fetchone()[0] != 1:
                        return []

                    values = ""

                    if str(type(cols)) != "<class 'str'>":      # для обеспечение работы как с ["str"], так и с "str"
                        for value in cols:
                            values += value + ", "

                    values = values[:len(values) - 2] if str(type(cols)) != "<class 'str'>" else cols
                    condition = "WHERE " + condition if condition is not None else ""

                    return curs.execute(f"SELECT {values} FROM '{table_name}' {condition} ").fetchall()

    def _get_table_names(self) -> list[tuple]:
        """
        Метод для извлечения всех названий таблиц
        :return: Список из кортежей с одним элементом - названием таблицы
        """
        with closing(sl.connect(self.__name)) as conn:
            with conn:
                with closing(conn.cursor()) as curs:

                    query = "SELECT name FROM sqlite_schema WHERE type = 'table'"

                    return curs.execute(query).fetchall()

    def _delete_from_table(self, table_name: str, condition: str = None) -> None:
        """
        Метод для удаления строк в таблице
        :param table_name: название таблицы
        :param condition: условие для определения конкретной удаляемой строки
        """
        with closing(sl.connect(self.__name)) as conn:
            with conn:
                with closing(conn.cursor()) as curs:

                    condition = "WHERE " + condition if condition is not None else ""

                    curs.execute(f"DELETE FROM '{table_name}' {condition} ")


class Events(Database):

    def __init__(self, path_to_db: str) -> None:
        super().__init__(path_to_db)
        self.users = self.download_all()
        self.delayed: list[Job] = []
        self.previews: dict[int, list[dict[str, str]]] = {}

    def __init_user_events_table(self, chat_id: int):
        """Объявление таблицы пользователя по его types.Message.chat.id"""
        self._create_table(
            str(chat_id),
            {
                "title": "TEXT",
                "description": "TEXT",
                "sendTo": "INTEGER",
                "date": "TEXT",
                "time": "TEXT",
                "weekday": "INTEGER",
                "repeated": "INTEGER",
                "with_sound": "INTEGER"
            }
        )

    def download_all(self) -> dict[int, list[dict[str]]]:
        """
        Метод для загрузки анонсов из БД в оперативную память
        :return: Словарь с ключами из types.Message.chat.id пользователя и значениями, являющимися списком его анонсов
        """
        chat_ids: list[int] = []
        result: dict[int, list[dict[str]]] = {}

        for chat_id in self._get_table_names():
            if chat_id[0] != "settings" and "group_" not in chat_id[0]:
                chat_ids.append(int(chat_id[0]))

        if len(chat_ids) == 0:
            logger.info(f"В базе данных нет данных об анонсах пользователей, поэтому Events.users - пустой словарь.")
            return result

        for chat_id in chat_ids:
            events = self._select_values_from_table(str(chat_id), '*')
            for event in events:
                if chat_id not in result:   # инициализация ключа, если нет в словаре
                    result[chat_id] = []
                result[chat_id].append(
                    {
                        "title": event[0],
                        "description": event[1],
                        "sendTo": event[2],
                        "date": event[3],
                        "time": event[4],
                        "weekday": event[5],
                        "repeated": True if event[6] == 1 else False,
                        "with_sound": True if event[7] == 1 else False
                    }
                )

        logger.info("Данные об анонсах пользователей успешно загружены из базы данных.")
        return result

    def upload_all(self) -> None:
        """Метод для загрузки анонсов из оперативной памяти в БД"""
        # active_users: list[int] = []

        if len(self.users) != 0:
            for chat_id in self.users:
                # active_users.append(chat_id)
                events = self.users[chat_id]
                table_name = str(chat_id)
                self.__init_user_events_table(chat_id)
                self._delete_from_table(str(chat_id))  # очистка таблицы пользователя
                if len(events) != 0:
                    self._insert_values_into_table(table_name, events)
            logger.info("Данные об анонсах пользователей успешно загружены в базу данных.")
        else:
            raise ValueError("Events.users is empty, so it can't be uploaded to database.")

        # # Дополнительная очистка БД от пользователей без анонсов. Код не нуждается в исполнении, т.к. все
        # # пользователи всегда будут попадать в Events.users вне зависимости от наличия у них анонсов, следовательно,
        # # очистка БД итак производится в коде выше.
        #
        # all_users: list[int] = []
        # users = self.__get_table_names()
        #
        # if len(users) != 0:
        #     for chat_id in users:
        #         if chat_id[0] != "settings":
        #             all_users.append(int(chat_id[0]))
        #
        # for chat_id in all_users:
        #     if chat_id not in active_users:
        #         self.__delete_from_table(str(chat_id))


class Settings(Database):

    def __init__(self, path_to_db: str) -> None:
        super().__init__(path_to_db)
        self.users = self.download_all_users()
        self.groups = self.download_all_groups()

    class User:
        """Класс данных пользователя"""
        def __init__(self, chat_id: int = 0, username: str = "", main_group: int = -1, mention_all: bool = True,
                     time_zone: timezone = timezone(timedelta(hours=3)),
                     allow_preview: bool = True) -> None:
            self.chat_id = chat_id
            self.username = username
            self.main_group = main_group
            self.mention_all = mention_all
            self.groups: list = []
            self.time_zone = time_zone
            self.allow_preview = allow_preview

    class Group:
        """Класс данных группы"""
        def __init__(self, chat_id: int = 0, ):
            self.chat_id = chat_id
            self.white_list: list = []

        class Admin:
            """Внутренний класс админа"""
            def __init__(self, chat_id: int = 0, username: str = ""):
                self.chat_id = chat_id
                self.username = username

    def __init_settings_users_table(self):
        """Объявление таблицы настроек пользователей"""
        self._create_table(
            "settings",
            {
                "chat_id": "INTEGER PRIMARY KEY",
                "username": "TEXT",
                "main_group": "INTEGER",
                "groups": "TEXT",
                "time_zone": "INTEGER",
                "mention_all": "INTEGER",
                "allow_preview": "INTEGER"
            }
        )

    def __init_settings_group_table(self, chat_id: int):
        self._create_table(
            f"group_{chat_id}",
            {
                "chat_id": "INTEGER PRIMARY KEY",
                "username": "TEXT"
            }
        )

    def download_all_users(self) -> dict[int, User]:
        """
        Метод для загрузки настроек пользователей из БД в оперативную память
        :return: Словарь с ключами из types.Message.chat.id пользователя и значениями, являющимися объектами класса User
        """

        result: dict[int, Settings.User] = {}

        self.__init_settings_users_table()
        users_data = self._select_values_from_table("settings", '*')

        if len(users_data) == 0:
            logger.info("В базе данных нет данных о настройках пользователей, поэтому Settings.users - пустой словарь.")
            return result

        for data in users_data:
            groups: list[int] = []
            for group in data[3].split(' '):
                groups.append(int(group))

            result[data[0]] = Settings.User(
                chat_id=data[0],
                username=data[1],
                main_group=data[2],
                time_zone=self.__parse_int_to_timezone(data[4]),
                mention_all=True if data[5] == 1 else False,
                allow_preview=True if data[6] == 1 else False
            )
            result[data[0]].groups = groups

        logger.info("Данные о настройках пользователей успешно загружены из базы данных.")
        return result

    def download_all_groups(self) -> dict[int, Group]:
        """
        Метод для загрузки вайт-листов групп из БД в оперативную память.
        :return: словарь с ключами types.Message.chat.id группы и значениями, являющимися объектами класса Group
        """

        groups_chat_ids: list[int] = []
        result: dict[int, Settings.Group] = {}

        for group_chat_id in self._get_table_names():
            if "group_" in group_chat_id[0]:
                groups_chat_ids.append(int(group_chat_id[0].split('_')[1]))

        if len(groups_chat_ids) == 0:
            logger.info("В базе данных нет данных о группах, поэтому Settings.groups - пустой словарь.")
            return result

        for group_chat_id in groups_chat_ids:
            self.__init_settings_group_table(group_chat_id)
            white_list = self._select_values_from_table(f"group_{group_chat_id}", '*')
            result[group_chat_id] = Settings.Group(chat_id=group_chat_id)
            for admin in white_list:
                result[group_chat_id].white_list.append(Settings.Group.Admin(chat_id=admin[0], username=admin[1]))

        logger.info("Данные о группах успешно загружены из базы данных.")
        return result

    def upload_all_users(self) -> None:
        """Метод для загрузки настроек пользователей из оперативной памяти в БД"""
        if len(self.users) != 0:
            for user in self.users:
                attrs = self.users[user]
                groups = ""

                for group in attrs.groups:
                    groups += str(group) + ' '

                groups = groups[:len(groups) - 1]

                self.__init_settings_users_table()
                self._delete_from_table("settings")
                self._insert_values_into_table(
                    "settings",
                    [{
                        "chat_id": attrs.chat_id,
                        "username": attrs.username,
                        "main_group": attrs.main_group,
                        "groups": groups,
                        "time_zone": self.__parse_timezone_to_int(attrs.time_zone)[0],  # ToDo: поддержка минут в UTC
                        "mention_all": 1 if attrs.mention_all else 0,
                        "allow_preview": 1 if attrs.allow_preview else 0
                    }]
                )
            logger.info("Данные о настройках пользователей успешно загружены в базу данных.")
        else:
            raise ValueError("Settings.users is empty, so it can't be uploaded to database.")

    def upload_all_groups(self) -> None:
        """Метод для загрузки данных о группах из оперативной памяти в БД"""
        if len(self.groups) != 0:
            for group in self.groups:
                self.__init_settings_group_table(group)
                self._delete_from_table(f"group_{group}")
                for admin in self.groups[group].white_list:
                    self._insert_values_into_table(
                        f"group_{group}",
                        [{
                            "chat_id": admin.chat_id,
                            "username": admin.username
                        }]
                    )
            logger.info("Данные о группах успешно загружены в базу данных.")
        else:
            raise ValueError("Settings.groups is empty, so it can't be uploaded to database.")

    @staticmethod
    def __parse_timezone_to_int(tz: timezone) -> list[int]:
        """
        Парсинг объекта datetime.timezone в список, где элементы - отклонение в часах и минутах от UTC. Поддерживает
        отрицательные числа.
        :param tz: объект datetime.timezone
        :return: [HH, MM]
        """
        if len(str(tz)) != 3:
            return [int(str(tz)[3:6]), int(str(tz)[7:9])]
        else:
            return [0, 0]

    @staticmethod
    def __parse_int_to_timezone(int_tz_hours: int, int_tz_minutes: int = 0) -> timezone:
        """
        Парсинг часов и минут с типом int в объект datetime.timezone. Поддерживает время только в интервале
        от -23:59 до 23:59.
        :param int_tz_hours: отклонение от UTC в часах
        :param int_tz_minutes: отклонение от UTC в минутах
        :return: объект datetime.timezone
        """
        return timezone(timedelta(hours=int_tz_hours, minutes=int_tz_minutes))


# database = {}
# active_users: list[Settings.User] = []


# def get_all_active_users():
#     global database
#     for user in database:
#         active_user = Settings._User(user, user["username"], user["main_group"], user["mention_all"], user["groups"],
#                                         user["timezone"])
#         active_users.append(active_user)
#
#
# def create_active_user(chatid: int, username: str, main_group: int, mention_all: bool, groups: list[int],
#                        user_timezone: timezone, allow_preview: bool):
#     active_users.append(
#         Settings._User(chatid, username, main_group, mention_all, groups, user_timezone, allow_preview)
#     )
#     return active_users[-1]
#
#
# def get_user_data(chatid: int = 0, username: str = ""):
#     user_exist: bool = False
#     data = Settings._User
#     for user in active_users:
#         if user.chat_id == chatid or user.username == username:
#             data = user
#             user_exist = True
#     if user_exist:
#         return data
#     else:
#         return create_active_user(chatid, username, chatid, True, [], timezone(timedelta(hours=3)), True)
#
#
# def update_user_data(chatid: int, username: str = None, main_group: int = None, mention_all: bool = None,
#                      group: int = None, user_timezone: timezone = None, allow_preview: bool = None):
#     if len(active_users) != 0:
#         for user in active_users:
#             if user.chat_id == chatid:
#                 user.username = username if username is not None else user.username
#                 user.main_group = main_group if main_group is not None else user.main_group
#                 user.mention_all = mention_all if mention_all is not None else user.mention_all
#                 if group is not None and group < 0:
#                     user.groups.append(group)
#                 user.user_timezone = user_timezone if user_timezone is not None else user.user_timezone
#                 user.allow_preview = allow_preview if allow_preview is not None else user.allow_preview
#                 return None
#     return create_active_user(chatid,
#                               username if username is not None else "",
#                               main_group if main_group is not None else chatid,
#                               mention_all if mention_all is not None else True,
#                               [group] if group is not None and group < 0 else [],
#                               user_timezone if user_timezone is not None else timezone(timedelta(hours=3)),
#                               allow_preview if allow_preview is not None else True)
#
#
# all_usernames_in_chats = {
#     -1001658853491: ["@deadsen", "@tedd_deireaddh", "@danya44ka", "@pretty_ratty", "@shoegaypedoffka",
#                      "@eliswithbayles", "@lKomfa", "@Drake_Lengford", "@VlissaJin", "@kireychenkov", "@iTBadBird",
#                      "@WeltisGodOurs", "@H_e_ck", "@unicorn_7_9", "@H0MYAK0ID", "@iam205th", "@Adoxanar", "@Flowbakery",
#                      "@FateOfFenix", "@AaaaBbbbr", "@GodfatherMikle", "@Sharmani1", "@railbat_27", "@YariAntnv13"],
#     -1001658853490: ["@tedd_deireaddh", "@shoegaypedoffka", "@deadsen"]
# }
#
#
# def users_main_group_chat_id(user_chat_id: int):
#     users_n_groups_chat_ids = {
#         491045788: -1001658853490,
#     }
#     return users_n_groups_chat_ids[user_chat_id] if user_chat_id in users_n_groups_chat_ids else user_chat_id
#
#
# def addressees_chat_id(username: str, user_chat_id: int):
#     usernames_n_chat_ids = {
#         "@deadsen": 491045788
#     }
#     return usernames_n_chat_ids[username] if username in usernames_n_chat_ids else user_chat_id
