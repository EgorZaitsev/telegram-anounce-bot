from telebot import TeleBot, types
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta, timezone
from time import sleep
import logger
import json
import database

logger.getLogger("apscheduler").setLevel(logger.DEBUG)

bot = TeleBot("6250913675:AAGoT62yuzk25PVB_OVcjVf6SenR0wWGxqQ")  # @announcements_robot

scheduler = BackgroundScheduler()

events = database.Events("database.db")  # БД для анонсов
settings = database.Settings("database.db")  # БД для настроек


@bot.my_chat_member_handler(lambda updated: True)
def check_bot_membership(updated: types.ChatMemberUpdated):
    if updated.new_chat_member.status in ["kicked", "restricted", "left"]:
        update_groups_data(updated.chat.id, delete_group=True)
        for user in settings.users:
            if updated.chat.id in settings.users[user].groups:
                i: int = 0
                for group in settings.users[user].groups:
                    if updated.chat.id == group:
                        settings.users[user].groups.pop(i)
                        break
                    i += 1
            if updated.chat.id == settings.users[user].main_group:
                settings.users[user].main_group = -1
    else:
        update_groups_data(updated.chat.id)


@bot.message_handler(commands=["start"])
def welcome_command(message: types.Message) -> types.Message:
    """
    Приветственное сообщение бота
    :param message: сообщение с командой пользователя
    :return: welcome-сообщение или сообщение с командой в случае deeplinking'a
    """
    # Обработка deeplinking (например, https://t.me/announcements_robot?start=id)
    if len(message.text.split()) > 1:
        match message.text.split()[1]:
            case "add" | "create" | "new" | "event":
                return create_event_command(message)
            case "id" | "getid" | "chatid":
                return get_chat_id_command(message)
            case "all":
                return mention_all_command(message)
            case "settings" | "setup":
                return settings_command(message)
            case "tz" | "timezone":
                return choose_time_zone_command(message)
            case "main_group" | "group" | "mg":
                return choose_main_group(message)
            case "main_menu" | "mm" | "menu":
                return main_menu_command(message)
            case "list" | "events" | "event_list":
                return events_list_command(message)
            case "push":
                return push_event_command(message, event_id="")
            case "del" | "delete":
                return delete_event_command(message)
            case "show" | "preview":
                return show_event_preview_command(message)
            case _:
                pass
    # Сообщение из группы
    if message.chat.id < 0:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            group=message.chat.id
        )
        return bot.reply_to(message,
                            f"<b>Приветствую, @{message.from_user.username}!</b>\n\n"
                            f"Я – планировщик анонсов для всевозможных событий. Для полного взаимодействия со мной,  "
                            f"нажмите <b>«<a href='https://t.me/announcements_robot?start=menu'>Открыть чат с ботом</a>»</b> "
                            f"для перехода в мое главное меню, или откройте вкладку <b>«Меню»</b> для вывода всех доступных "
                            f"команд «/».\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                "Открыть чат с ботом",
                                url="https://t.me/announcements_robot?start=menu"
                            )))
    # Сообщение из чата
    else:
        update_users_data(
            chat_id=message.chat.id,
            username=message.from_user.username
        )

    open_mainmenu_button = types.InlineKeyboardButton("Главное меню", callback_data="open_mainmenu")
    open_mainmenu_keyboard = types.InlineKeyboardMarkup()
    open_mainmenu_keyboard.add(open_mainmenu_button)

    return bot.send_message(message.chat.id,
                            f"<b>Приветствую, @{message.from_user.username}!</b>\n\n"
                            f"Я – планировщик анонсов для всевозможных событий. Чтобы "
                            f"взаимодействовать со мной, нажмите <b>«Главное меню»</b> для открытия "
                            f"inline-меню, или откройте вкладку <b>«Меню»</b> для вывода всех доступных "
                            f"команд «/».\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            reply_markup=open_mainmenu_keyboard)


@bot.message_handler(commands=["create", "new", "add"])
def create_event_command(message: types.Message, from_menu: bool = False) -> types.Message:
    """
    Команда для отправки веб-формы для создания анонсов.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :return: сообщение с Reply клавиатурой вместе с веб-формой
    """

    if message.chat.id < 0:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            group=message.chat.id
        )
        return bot.reply_to(message,
                            "<b>Ошибка</b>: данная команда не предназначена для выполнения в группе. Пожалуйста, "
                            "перейдите в чат с <a href='https://t.me/announcements_robot?start=add'>ботом</a>, чтобы "
                            "создать новое событие.\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                "Открыть чат с ботом",
                                url="https://t.me/announcements_robot?start=add"
                            )))
    else:
        update_users_data(
            chat_id=message.chat.id,
            username=message.from_user.username if not from_menu else None
        )

    web_app_keyboard = types.ReplyKeyboardMarkup(one_time_keyboard=True, resize_keyboard=True)
    web_app_keyboard.add(
        types.KeyboardButton(
            "Создать анонс",
            web_app=types.WebAppInfo(
                url="https://egorzaitsev.github.io/telegram-anounce-bot/webapp/index.html"
            )
        )
    )

    if from_menu:  # удаление вместо изменения, т.к. нельзя менять один тип клавиатуры на другой (Reply и Inline)
        bot.delete_message(message.chat.id, message.id)

    msg = bot.send_message(message.chat.id,  # Дробление сообщения бота на два,
                           "<b>Создание анонса //</b>",  # чтобы совместить одновременно и inline-кнопку,
                           parse_mode="HTML",  # и reply-кнопку
                           reply_markup=web_app_keyboard)

    open_mainmenu_keyboard = types.InlineKeyboardMarkup().add(
        types.InlineKeyboardButton("Отмена", callback_data=f"open_mainmenu_{msg.id}")
    )

    return bot.send_message(message.chat.id,
                            "Нажмите на кнопку <b>«Создать анонс»</b> ниже, чтобы открыть веб-приложение "
                            "для создания анонсов.",
                            parse_mode="HTML",
                            reply_markup=open_mainmenu_keyboard)


@bot.message_handler(commands=["all"])
def mention_all_command(message: types.Message) -> types.Message:
    """
    Команда для упоминания всех пользователей в группе
    :param message: сообщение с командой пользователя
    :return: сообщение с никами всех найденных в settings.users пользователей в данной группе
    """

    users_in_chat: str = ""

    if message.chat.id > 0:
        update_users_data(
            chat_id=message.chat.id,
            username=message.from_user.username if message.from_user.username != "announcements_robot" else None,
        )
        return bot.reply_to(message,
                            "<b>Ошибка</b>: команда /all вызвана внутри личного чата с ботом. Пожалуйста, добавьте бота в "
                            "группу с более чем одним участником."
                            "\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            reply_markup=types.InlineKeyboardMarkup().add(
                                types.InlineKeyboardButton(
                                    "Добавить в группу",
                                    url="https://t.me/announcements_robot?startgroup=true/"
                                ),
                                types.InlineKeyboardButton(
                                    "В главное меню",
                                    callback_data="open_mainmenu"
                                )
                            ))
    else:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            group=message.chat.id
        )

    for chat_id in settings.users:
        if message.chat.id in settings.users[chat_id].groups:
            if message.from_user.username != settings.users[chat_id].username:
                users_in_chat += f"@{settings.users[chat_id].username} "
                users_in_chat = users_in_chat.replace("@None ", '')

    if users_in_chat != "":
        return bot.reply_to(message, users_in_chat)
    else:
        return bot.reply_to(message,
                            "<b>Ошибка</b>: команда /all вызвана внутри группы с одним участником, или ни один пользователь "
                            "в данной группе пока не указан как ее участник. Пожалуйста, убедитесь, что все участники "
                            "данной группы отправили хотя бы одно сообщение в присутствие бота или задействовали его "
                            "команды (например, /id), а также указали никнейм в своем профиле телеграм-аккаунта."
                            "\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML")


@bot.message_handler(commands=["chatid", "id", "getid", "chat_id", "get_id"])
def get_chat_id_command(message: types.Message) -> types.Message:
    """
    Команда для определения пользователем некоторых данных, извлеченных из его сообщения с командой.
    :param message: сообщение с командой пользователя
    :return: сообщение с данными о текущем чате
    """

    if message.chat.id > 0:
        update_users_data(
            chat_id=message.chat.id,
            username=message.from_user.username
        )
        return bot.reply_to(message,
                            f"<b>Данные о текущем чате //</b>\n\n"
                            f"<b>user.id</b>: <code>{message.from_user.id}</code>\n"
                            f"<b>user.username</b>: <code>{message.from_user.username}</code>"
                            f"\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML")
    else:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            group=message.chat.id
        )
        return bot.reply_to(message,
                            f"<b>Данные о текущей группе //</b>\n\n"
                            f"<b>user.id</b>: <code>{message.from_user.id}</code>\n"
                            f"<b>user.username</b>: <code>{message.from_user.username}</code>\n"
                            f"<b>group.id</b>: <code>{message.chat.id}</code>"
                            f"\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML")


@bot.message_handler(commands=["ban", "unban"], content_types=["text"])
def manage_access_command(message: types.Message) -> types.Message:
    """

    :param message:
    :return:
    """

    if message.chat.id > 0:
        update_users_data(
            chat_id=message.chat.id,
            username=message.from_user.username
        )
        return bot.reply_to(message,
                            "<b>Ошибка</b>: данная команда не предназначена для выполнения в личном чате с ботом. Пожалуйста, "
                            "добавьте бота в созданную вами группу, чтобы задавать уровни доступа к отправке анонсов для всех админов."
                            "\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            reply_markup=types.InlineKeyboardMarkup().add(
                                types.InlineKeyboardButton(
                                    "Добавить в группу",
                                    url="https://t.me/announcements_robot?startgroup=true/"
                                ),
                                types.InlineKeyboardButton(
                                    "В главное меню",
                                    callback_data="open_mainmenu"
                                )
                            ))

    elif message.chat.id < 0:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            main_group=message.chat.id,
            group=message.chat.id
        )

    admins = bot.get_chat_administrators(message.chat.id)
    is_creator: bool = False
    creator_username: str = ""

    for admin in admins:
        if admin.status == "creator":
            is_creator = True if admin.user.id == message.from_user.id else False
            creator_username = admin.user.username

    message.text = message.text.replace('@', '')

    if is_creator:
        if len(message.text.split(' ')) > 1:
            if message.text.split(' ')[0] == "/ban":
                if message.text.split(' ')[1].isdigit():
                    for admin in admins:
                        if str(admin.user.id) == message.text.split(' ')[1] and admin.status != "creator" \
                                and admin.user.username != "announcements_robot":
                            update_groups_data(message.chat.id, banned_admin_chat_id=int(message.text.split(' ')[1]))
                            return bot.reply_to(message,
                                                "<b>Оповещение</b>: указанный админ теперь не имеет доступа к отправке анонсов "
                                                "в данную группу.",
                                                parse_mode="HTML")
                    return bot.reply_to(message,
                                        "<b>Ошибка</b>: указанного админа нет в группе. Пожалуйста, проверьте правильность "
                                        "указанного user.id или обратитесь в поддержку в личном чате с ботом."
                                        "\n\n<b>Ознакомиться со справкой – /help</b>",
                                        parse_mode="HTML",
                                        reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                            "Открыть чат с ботом",
                                            url="https://t.me/announcements_robot?start=support/"
                                        )))
                else:
                    for admin in admins:
                        if admin.user.username == message.text.split(' ')[1] and admin.status != "creator" \
                                and admin.user.username != "announcements_robot":
                            update_groups_data(message.chat.id, banned_admin_username=message.text.split(' ')[1])
                            return bot.reply_to(message,
                                                "<b>Оповещение</b>: указанный админ теперь не имеет доступа к отправке анонсов "
                                                "в данную группу.",
                                                parse_mode="HTML")
                    return bot.reply_to(message,
                                        "<b>Ошибка</b>: указанного админа нет в группе. Пожалуйста, проверьте правильность "
                                        "указанного никнейма или обратитесь в поддержку в личном чате с ботом."
                                        "\n\n<b>Ознакомиться со справкой – /help</b>",
                                        parse_mode="HTML",
                                        reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                            "Открыть чат с ботом",
                                            url="https://t.me/announcements_robot?start=support/"
                                        )))
            else:
                if message.text.split(' ')[1].isdigit():
                    for admin in admins:
                        if str(admin.user.id) == message.text.split(' ')[1] and admin.status != "creator" \
                                and admin.user.username != "announcements_robot":
                            update_groups_data(message.chat.id, unbanned_admin_chat_id=int(message.text.split(' ')[1]))
                            return bot.reply_to(message,
                                                "<b>Оповещение</b>: указанный админ теперь имеет доступ к отправке анонсов "
                                                "в данную группу.",
                                                parse_mode="HTML")
                    return bot.reply_to(message,
                                        "<b>Ошибка</b>: указанного админа нет в группе. Пожалуйста, проверьте правильность "
                                        "указанного user.id или обратитесь в поддержку в личном чате с ботом."
                                        "\n\n<b>Ознакомиться со справкой – /help</b>",
                                        parse_mode="HTML",
                                        reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                            "Открыть чат с ботом",
                                            url="https://t.me/announcements_robot?start=support/"
                                        )))
                else:
                    for admin in admins:
                        if admin.user.username == message.text.split(' ')[1] and admin.status != "creator" \
                                and admin.user.username != "announcements_robot":
                            update_groups_data(message.chat.id, unbanned_admin_username=message.text.split(' ')[1])
                            return bot.reply_to(message,
                                                "<b>Оповещение</b>: указанный админ теперь имеет доступ к отправке анонсов "
                                                "в данную группу.",
                                                parse_mode="HTML")
                    return bot.reply_to(message,
                                        "<b>Ошибка</b>: указанного админа нет в группе. Пожалуйста, проверьте правильность "
                                        "указанного никнейма или обратитесь в поддержку в личном чате с ботом."
                                        "\n\n<b>Ознакомиться со справкой – /help</b>",
                                        parse_mode="HTML",
                                        reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                            "Открыть чат с ботом",
                                            url="https://t.me/announcements_robot?start=support/"
                                        )))
        else:
            return bot.reply_to(message,
                                "<b>Ошибка</b>: не указан user.id или никнейм админа. Пожалуйста, отправьте данную команду снова, "
                                "указав user.id или никнейм админа через пробел."
                                "\n\n<b>Ознакомиться со справкой – /help</b>",
                                parse_mode="HTML")
    else:
        return bot.reply_to(message,
                            "<b>Ошибка</b>: данной командой может пользоваться только владелец группы. Пожалуйста, обратитесь к "
                            f"{'нему' if creator_username == '' else '@' + creator_username}"
                            ", чтобы задать уровень доступа к анонсам для админов."
                            "\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML")


@bot.message_handler(commands=["main_menu", "menu", "main"])
def main_menu_command(message: types.Message, from_menu: bool = False) -> types.Message:
    """
    Команда для показа главного меню бота.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :return: сообщение с inline-кнопками, вызывающими другие основные команды бота
    """

    if message.chat.id < 0:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            group=message.chat.id
        )
        return bot.reply_to(message,
                            "<b>Ошибка</b>: данная команда не предназначена для выполнения в группе. Пожалуйста, "
                            "перейдите в чат с <a href='https://t.me/announcements_robot?start=menu'>ботом</a>, чтобы "
                            "открыть главное меню.\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                "Открыть чат с ботом",
                                url="https://t.me/announcements_robot?start=menu"
                            )))
    else:
        update_users_data(
            chat_id=message.chat.id,
            username=message.from_user.username if not from_menu else None
        )

    create_event_button = types.InlineKeyboardButton("Создать анонс", callback_data="open_create")
    events_list_button = types.InlineKeyboardButton("Список анонсов", callback_data="open_list")
    settings_button = types.InlineKeyboardButton("Настройки анонсов", callback_data="open_settings")
    help_button = types.InlineKeyboardButton("Помощь", callback_data="open_help")

    main_menu_keyboard = types.InlineKeyboardMarkup(row_width=2)
    main_menu_keyboard.add(create_event_button, events_list_button, settings_button, help_button)

    welcome_phrase: str

    current_time: datetime = datetime.now(tz=settings.users[message.chat.id].time_zone)

    hour_int: int = int(current_time.strftime("%H"))

    if 3 < hour_int <= 11:
        welcome_phrase = "Доброе утро"
    elif 11 < hour_int <= 16:
        welcome_phrase = "Добрый день"
    elif 16 < hour_int <= 22:
        welcome_phrase = "Добрый вечер"
    elif 22 < hour_int or hour_int <= 3:
        welcome_phrase = "Доброй ночи"
    else:
        welcome_phrase = "Доброго времени суток"  # на всякий случай

    if not from_menu:
        return bot.send_message(message.chat.id,
                                f"<b>Главное меню //</b>\n\n"
                                f"{welcome_phrase}, @{settings.users[message.chat.id].username}.",
                                parse_mode="HTML",
                                reply_markup=main_menu_keyboard)
    else:
        return bot.edit_message_text(f"<b>Главное меню //</b>\n\n{welcome_phrase}, "
                                     f"@{settings.users[message.chat.id].username}.",
                                     message.chat.id,
                                     message.id,
                                     parse_mode="HTML",
                                     reply_markup=main_menu_keyboard)


@bot.message_handler(commands=["help"])
def help_command(message: types.Message, from_menu: bool = False) -> types.Message:
    """
    Команда для помощи пользователям.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :return: сообщение с меню помощи
    """

    open_mainmenu_button = types.InlineKeyboardButton("В главное меню", callback_data="open_mainmenu")
    open_commands_button = types.InlineKeyboardButton("Список команд", callback_data="open_commands")
    open_support_button = types.InlineKeyboardButton("Обратиться в поддержку", callback_data="open_support")
    open_support_from_group_button = types.InlineKeyboardButton("Обратиться в поддержку",
                                                                url="https://t.me/announcements_robot?start=support")
    terms_of_use_button = types.InlineKeyboardButton("Условия использования", url="https://telegra.ph/scheduler-terms-of-use-08-29")
    help_article_button = types.InlineKeyboardButton("Справка", url="https://telegra.ph/scheduler-faq-07-27")
    devs_group_button = types.InlineKeyboardButton("Разработчики", url="https://t.me/announcements_devs")

    help_keyboard = types.InlineKeyboardMarkup()

    if message.chat.id < 0:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            main_group=message.chat.id,
            group=message.chat.id
        )
        help_keyboard.add(terms_of_use_button, help_article_button, open_support_from_group_button,
                          open_commands_button, devs_group_button, row_width=1)
        if not from_menu:
            return bot.reply_to(message,
                                "<b>Помощь //</b>",
                                parse_mode="HTML",
                                reply_markup=help_keyboard)
        else:
            return bot.edit_message_text("<b>Помощь //</b>",
                                         message.chat.id,
                                         message.id,
                                         parse_mode="HTML",
                                         reply_markup=help_keyboard)
    else:
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username
        )
        help_keyboard.add(terms_of_use_button, help_article_button, open_support_button, open_commands_button,
                          devs_group_button, open_mainmenu_button, row_width=1)
        if from_menu:
            return bot.edit_message_text("<b>Помощь //</b>",
                                         message.chat.id,
                                         message.id,
                                         parse_mode="HTML",
                                         reply_markup=help_keyboard)
        else:
            return bot.send_message(message.chat.id,
                                    "<b>Помощь //</b>",
                                    parse_mode="HTML",
                                    reply_markup=help_keyboard)


@bot.message_handler(commands=["commands", "command", "cmds", "cmd"])
def show_commands_command(message: types.Message, from_menu: bool = False) -> types.Message:
    """
    Команда для вывода всех доступных команд.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :return: сообщение со списком доступных для использования в данном чате команд
    """

    if message.chat.id < 0:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            main_group=message.chat.id,
            group=message.chat.id
        )
        text = "<b>Помощь / Список команд //</b>\n\n" \
               "<i>Команды, доступные в текущей группе:</i>\n" \
               "/all – упомянуть всех активных пользователей в группе;\n" \
               "/commands – список команд;\n" \
               "/id – информация о текущем чате;\n" \
               "/help – раздел помощи.\n\n" \
               "<i>Команды, доступные только создателю группы:</i>\n" \
               "/ban [админ] – заблокировать доступ к анонсам для админа;\n" \
               "/unban [админ] – разрешить доступ к анонсам для админа (для новых админов доступ по умолчанию запрещен).\n\n" \
               "<i>Команды, доступные только в </i><a href='https://t.me/announcements_robot'><i>чате с ботом:</i></a>\n" \
               "/add – создать анонс;\n" \
               "/list – список анонсов;\n" \
               "/push [id анонса] – отправить анонс без ожидания;\n" \
               "/delete [id анонса] – удалить анонс;\n" \
               "/preview [id анонса] – посмотреть превью анонса;\n" \
               "/menu – главное меню бота;\n" \
               "/settings – меню настроек пользователя бота;\n" \
               "/timezone – настройка часового пояса всех анонсов;\n" \
               "/main_group – настройка главной группы для отправки анонсов;\n" \
               "/support – обратиться в поддержку."
        if from_menu:
            return bot.edit_message_text(text,
                                         message.chat.id,
                                         message.id,
                                         parse_mode="HTML",
                                         disable_web_page_preview=True,
                                         reply_markup=types.InlineKeyboardMarkup().add(
                                             types.InlineKeyboardButton("В меню помощи", callback_data="open_help")
                                         ))
        else:
            return bot.send_message(message.chat.id,
                                    text,
                                    parse_mode="HTML",
                                    disable_web_page_preview=True,
                                    reply_markup=types.InlineKeyboardMarkup().add(
                                        types.InlineKeyboardButton("В меню помощи", callback_data="open_help")
                                    ))
    else:
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username
        )
        text = "<b>Помощь / Список команд //</b>\n\n" \
               "<i>Команды, доступные в текущем чате:</i>\n" \
               "/add – создать анонс;\n" \
               "/list – список анонсов;\n" \
               "/push [id анонса] – отправить анонс без ожидания;\n" \
               "/delete [id анонса] – удалить анонс;\n" \
               "/preview [id анонса] – посмотреть превью анонса;\n" \
               "/menu – главное меню бота;\n" \
               "/settings – меню настроек пользователя бота;\n" \
               "/timezone – настройка часового пояса всех анонсов;\n" \
               "/main_group – настройка главной группы для отправки анонсов;\n" \
               "/support – обратиться в поддержку;\n" \
               "/commands – список команд;\n" \
               "/id – информация о текущем чате;\n" \
               "/help – раздел помощи.\n\n" \
               "<i>Команды, доступные только в группах:</i>\n" \
               "/all – упомянуть всех активных пользователей в группе;\n" \
               "/ban [админ] – заблокировать доступ к анонсам для админа;\n" \
               "/unban [админ] – разрешить доступ к анонсам для админа (для новых админов доступ по умолчанию запрещен)."
        if from_menu:
            return bot.edit_message_text(text,
                                         message.chat.id,
                                         message.id,
                                         parse_mode="HTML",
                                         reply_markup=types.InlineKeyboardMarkup().add(
                                             types.InlineKeyboardButton("В меню помощи", callback_data="open_help")
                                         ))
        else:
            return bot.send_message(message.chat.id,
                                    text,
                                    parse_mode="HTML",
                                    reply_markup=types.InlineKeyboardMarkup().add(
                                             types.InlineKeyboardButton("В меню помощи", callback_data="open_help")
                                    ))


@bot.message_handler(commands=["support"])
def support_command(message: types.Message, from_menu: bool = False) -> types.Message | None:
    """
    Команда для обращения в техподдержку.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :return: сообщение с правилами обращения в техподдержку и ожидание ввода текста
    """

    if message.chat.id < 0:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            main_group=message.chat.id,
            group=message.chat.id
        )
        return bot.reply_to(message,
                            "<b>Ошибка</b>: обращение в поддержку невозможно из группы. Пожалуйста, перейдите в "
                            "<a href='https://t.me/announcements_robot?start=support'>чат с ботом</a> и отправьте свое обращение"
                            " в поддержку.\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            reply_markup=types.InlineKeyboardMarkup().add(
                                types.InlineKeyboardButton("Открыть чат с ботом", url="https://t.me/announcements_robot?start=support")
                            ))
    else:
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username
        )

    text = "<b>Помощь / Обратиться в поддержку //</b>\n\n" \
           "Вы можете обратиться в поддержку по абсолютно любым вопросам, связанным с данным ботом. Пожалуйста, постарайтесь " \
           "уместить текст своего обращения в пределах одного сообщения, ведь в противном случае, придется создать два обращения. " \
           "Вы также можете прикрепить фото, видео и иной файл, если они отправлены одним сообщением с текстом.\n\nУчтите, что " \
           "поддержка оставляет за собой право не рассмотреть полученное обращение в некоторых случаях, указанных в " \
           "<a href='https://telegra.ph/scheduler-faq-07-27'>Справке</a>."

    if from_menu:
        bot.edit_message_text(text,
                              message.chat.id,
                              message.id,
                              parse_mode="HTML",
                              disable_web_page_preview=True,
                              reply_markup=types.InlineKeyboardMarkup().add(
                                  types.InlineKeyboardButton("Отмена", callback_data="open_help")
                              ))
    else:
        bot.send_message(message.chat.id,
                         text,
                         parse_mode="HTML",
                         disable_web_page_preview=True,
                         reply_markup=types.InlineKeyboardMarkup().add(
                                  types.InlineKeyboardButton("Отмена", callback_data="open_help")
                         ))

    return bot.register_next_step_handler(message, send_message_to_support)


def send_message_to_support(message: types.Message) -> types.Message:
    """
    Функция перенаправления сообщений в чат-техподдержки.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :return: уведомление об успешной отправке обращения
    """
    msg = bot.forward_message(-990277292, message.chat.id, message.id)

    return bot.send_message(message.chat.id,
                            f"<b>Оповещение</b>: обращение №<code>{msg.id}</code> успешно зарегистрировано. Пожалуйста, ожидайте ответа от "
                            f"поддержки.",
                            parse_mode="HTML",
                            reply_markup=types.InlineKeyboardMarkup().add(
                                types.InlineKeyboardButton("В меню помощи", callback_data="open_help"),
                                types.InlineKeyboardButton("В главное меню", callback_data="open_mainmenu")
                            ))


@bot.message_handler(commands=["push", "send"], content_types=["text"])
def push_event_command(message: types.Message, event_id: str = "", from_menu: bool = False) -> types.Message | None:
    """
    Команда для мгновенной отправки запланированного анонса по его ID.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param event_id: уникальный идентификатор анонса (для вызова из других функций)
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :return: сообщение о статусе отправки анонса получателю через event_pusher или сообщение об ошибке
    """

    if message.chat.id < 0:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            group=message.chat.id
        )
        return bot.reply_to(message,
                            "<b>Ошибка</b>: данная команда не предназначена для выполнения в группе. Пожалуйста, "
                            "перейдите в чат с <a href='https://t.me/announcements_robot?start=push'>ботом</a>, чтобы "
                            "отправить запланированный анонс сейчас.\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                "Открыть чат с ботом",
                                url="https://t.me/announcements_robot?start=push"
                            )))
    else:
        update_users_data(
            chat_id=message.chat.id,
            username=message.from_user.username if not from_menu else None
        )

    if len(message.text.split(' ')) > 1 and event_id == "" and "start" not in message.text:
        event_id = message.text.split(' ')[1]

    if event_id != "":
        return event_pusher(message, event_id, from_menu)
    else:
        bot.send_message(message.chat.id,
                         "<b>Отправка анонса без ожидания //</b>\n\nПришлите корректный идентификатор анонса для его"
                         "немедленного отправления указанному получателю.",
                         parse_mode="HTML",
                         reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                             "Отмена",
                             callback_data="open_mainmenu"
                         )))
        return bot.register_next_step_handler(message, event_pusher, event_id, from_menu)


def event_pusher(message: types.Message, event_id: str = "", from_menu: bool = False) -> types.Message | None:
    """
    Функция для отправки анонса по команде /push.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param event_id: уникальный идентификатор анонса (для вызова из других функций)
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :return: Сообщение об ошибке при отправке анонса в случае неправильного ID, иначе None (и отправка анонса)
    """

    open_mainmenu_button = types.InlineKeyboardButton("В главное меню", callback_data="open_mainmenu")
    open_list_button = types.InlineKeyboardButton("К списку анонсов", callback_data="open_list")

    event_pusher_keyboard = types.InlineKeyboardMarkup().add(open_list_button, open_mainmenu_button)

    if event_id == "":
        event_id = message.text

    i = 0
    for event in events.delayed:
        if message.chat.id == int(event.id.split('__')[0]) and event_id == event.id.split('__')[2]:
            event.modify(next_run_time=datetime.now(tz=settings.users[message.chat.id].time_zone))
            if event.id.split("__")[1] != "cron" and message.chat.id:
                events.delayed.pop(i)    # для более быстрого удаления анонса из списка (чтобы сообщение со списком не показывало уже удаленный анонс)
            return None
        i += 1

    if not from_menu:
        return bot.send_message(message.chat.id,
                                "<b>Ошибка</b>: указанный идентификатор анонса недействителен. Пожалуйста, повторите "
                                "попытку, используя корректный идентификатор запланированного анонса."
                                "\n\n<b>Ознакомиться со справкой – /help</b>",
                                parse_mode="HTML",
                                reply_markup=event_pusher_keyboard)
    else:
        return bot.edit_message_text("<b>Ошибка</b>: указанный идентификатор анонса недействителен. Пожалуйста, повторите "
                                     "попытку, используя корректный идентификатор запланированного анонса."
                                     "\n\n<b>Ознакомиться со справкой – /help</b>",
                                     message.chat.id,
                                     message.id,
                                     parse_mode="HTML",
                                     reply_markup=event_pusher_keyboard)


@bot.message_handler(commands=["delete", "del", 'd', "remove"], content_types=["text"])
def delete_event_command(message: types.Message, event_id: str = "", from_menu: bool = False) -> types.Message | None:
    """
    Команда для удаления анонса по его ID.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param event_id: уникальный идентификатор анонса (для вызова из других функций)
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :return: вызов команды event_remover или сообщение об ошибке
    """

    if message.chat.id < 0:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            group=message.chat.id
        )
        return bot.reply_to(message,
                            "<b>Ошибка</b>: данная команда не предназначена для выполнения в группе. Пожалуйста, "
                            "перейдите в чат с <a href='https://t.me/announcements_robot?start=del'>ботом</a>, чтобы "
                            "удалить запланированный анонс сейчас.\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                "Открыть чат с ботом",
                                url="https://t.me/announcements_robot?start=del"
                            )))
    else:
        update_users_data(
            chat_id=message.chat.id,
            username=message.from_user.username if not from_menu else None
        )

    if len(message.text.split(' ')) > 1 and event_id == "" and "start" not in message.text:
        event_id = message.text.split(' ')[1]

    if event_id != "":
        return event_remover(message, event_id, from_menu)
    else:
        bot.send_message(message.chat.id,
                         "<b>Удаление анонса //</b>\n\nПришлите корректный идентификатор анонса для его "
                         "удаления из списка запланированных анонсов.",
                         parse_mode="HTML",
                         reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                             "Отмена",
                             callback_data="open_mainmenu"
                         )))
        return bot.register_next_step_handler(message, event_remover, event_id, from_menu)


def event_remover(message: types.Message, event_id: str = "", from_menu: bool = False) -> types.Message:
    """
    Функция для удаления анонса по команде /push.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param event_id: уникальный идентификатор анонса (для вызова из других функций)
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :return: сообщение об удалении анонса или об ошибочном ID
    """

    open_mainmenu_button = types.InlineKeyboardButton("В главное меню", callback_data="open_mainmenu")
    open_list_button = types.InlineKeyboardButton("К списку анонсов", callback_data="open_list")

    event_remover_keyboard = types.InlineKeyboardMarkup().add(open_list_button, open_mainmenu_button)

    if event_id == "":
        event_id = message.text

    i = 0
    for event in events.delayed:
        if message.chat.id == int(event.id.split('__')[0]) and event_id == event.id.split('__')[2]:
            events.delayed.pop(i)
            i = 0
            for previews in events.previews[message.chat.id]:
                for preview in previews:
                    if preview == event_id:
                        events.previews[message.chat.id].pop(i)
                        msg = bot.send_message(message.chat.id,
                                               f"<b>Оповещение</b>: анонс <b>{event.name}</b> (код: <code>{event_id}</code>) "
                                               f"удален из списка запланированных. Данный код анонса более недоступен "
                                               f"для использования.",
                                               parse_mode="HTML")
                        return bot.edit_message_reply_markup(message.chat.id, msg.id,
                                                             reply_markup=types.InlineKeyboardMarkup().add(
                                                                 types.InlineKeyboardButton(
                                                                     "ОК", callback_data=f"system_delete_{msg.id}"
                                                                 )
                                                             ))
                    i += 1
        i += 1
    if not from_menu:
        return bot.send_message(message.chat.id,
                                "<b>Ошибка</b>: указанный идентификатор анонса недействителен. Пожалуйста, повторите "
                                "попытку, используя корректный идентификатор запланированного анонса."
                                "\n\n<b>Ознакомиться со справкой – /help</b>",
                                parse_mode="HTML",
                                reply_markup=event_remover_keyboard)
    else:
        return bot.edit_message_text("<b>Ошибка</b>: указанный идентификатор анонса недействителен. Пожалуйста, повторите "
                                     "попытку, используя корректный идентификатор запланированного анонса."
                                     "\n\n<b>Ознакомиться со справкой – /help</b>",
                                     message.chat.id,
                                     message.id,
                                     parse_mode="HTML",
                                     reply_markup=event_remover_keyboard)


@bot.message_handler(commands=["preview", "event", "show"])
def show_event_preview_command(message: types.Message, event_id: str = "", from_menu: bool = False,
                               callback: str = None) -> types.Message | None:
    """
    Команда для показа анонса отправителю перед его отправкой.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param event_id: уникальный идентификатор анонса (для вызова из других функций)
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :param callback: call.data для возврата к выбранному анонсу в event_list
    :return: вызов команды show_event_preview или сообщение об ошибке
    """

    if message.chat.id < 0:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            group=message.chat.id
        )
        return bot.reply_to(message,
                            "<b>Ошибка</b>: данная команда не предназначена для выполнения в группе. Пожалуйста, "
                            "перейдите в чат с <a href='https://t.me/announcements_robot?start=show'>ботом</a>, чтобы "
                            "посмотреть запланированный анонс сейчас.\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                "Открыть чат с ботом",
                                url="https://t.me/announcements_robot?start=show"
                            )))
    else:
        update_users_data(
            chat_id=message.chat.id,
            username=message.from_user.username if not from_menu else None
        )

    if len(message.text.split(' ')) > 1 and event_id == "" and "start" not in message.text:
        event_id = message.text.split(' ')[1]

    if event_id != "":
        return show_event_preview(message, event_id, from_menu, callback)
    else:
        bot.send_message(message.chat.id,
                         "<b>Предпросмотр анонса //</b>\n\nПришлите корректный идентификатор анонса для его "
                         "предварительного просмотра.",
                         parse_mode="HTML",
                         reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                             "Отмена", callback_data="open_mainmenu"
                         )))
        return bot.register_next_step_handler(message, show_event_preview, event_id, from_menu, callback)


def show_event_preview(message: types.Message, event_id: str = "", from_menu: bool = False, callback: str = None) -> types.Message:
    """
    Функция для показа превью анонса по команде /preview.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param event_id: уникальный идентификатор анонса (для вызова из других функций)
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :param callback: call.data для возврата к выбранному анонсу в event_list
    :return: сообщение с превью анонса или об ошибочном ID
    """

    open_mainmenu_button = types.InlineKeyboardButton("В главное меню", callback_data="open_mainmenu")
    open_list_button = types.InlineKeyboardButton("К списку анонсов", callback_data="open_list")
    back_to_event_button = types.InlineKeyboardButton("К выбранному анонсу", callback_data=callback)

    show_event_preview_keyboard = types.InlineKeyboardMarkup()

    if event_id == "":
        event_id = message.text
        show_event_preview_keyboard.add(open_list_button, open_mainmenu_button)
    elif callback is not None:
        show_event_preview_keyboard.add(back_to_event_button)
    else:
        show_event_preview_keyboard.add(open_list_button, open_mainmenu_button)

    if message.chat.id in events.previews:
        for previews in events.previews[message.chat.id]:
            for preview in previews:
                if preview == event_id:
                    if not from_menu:
                        return bot.send_message(message.chat.id,
                                                previews[preview],
                                                parse_mode="HTML",
                                                reply_markup=show_event_preview_keyboard,
                                                disable_web_page_preview=settings.users[message.chat.id].allow_preview)
                    else:
                        return bot.edit_message_text(previews[preview],
                                                     message.chat.id,
                                                     message.id,
                                                     parse_mode="HTML",
                                                     reply_markup=show_event_preview_keyboard,
                                                     disable_web_page_preview=settings.users[message.chat.id].allow_preview)
    if not from_menu:
        return bot.send_message(message.chat.id,
                                "<b>Ошибка</b>: указанный идентификатор анонса недействителен. Пожалуйста, повторите "
                                "попытку, используя корректный идентификатор запланированного анонса."
                                "\n\n<b>Ознакомиться со справкой – /help</b>",
                                parse_mode="HTML",
                                reply_markup=types.InlineKeyboardMarkup().add(open_list_button, open_mainmenu_button))
    else:
        return bot.edit_message_text("<b>Ошибка</b>: указанный идентификатор анонса недействителен. Пожалуйста, повторите "
                                     "попытку, используя корректный идентификатор запланированного анонса."
                                     "\n\n<b>Ознакомиться со справкой – /help</b>",
                                     message.chat.id,
                                     message.id,
                                     parse_mode="HTML",
                                     reply_markup=types.InlineKeyboardMarkup().add(open_list_button, open_mainmenu_button))


@bot.message_handler(commands=["list", "events", "events_list", "loe", "list_of_events"])
def events_list_command(message: types.Message, page: int = 0, from_menu: bool = False) -> types.Message:
    """
    Команда для вывода всех запланированных анонсов с пагинацией.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param page: показывающаяся в данный момент страница, индекс списка pages (по умолчанию - 0)
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :return: сообщение с запланированными анонсами с подключенной пагинацией
    """

    if message.chat.id < 0:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            group=message.chat.id
        )
        return bot.reply_to(message,
                            "<b>Ошибка</b>: данная команда не предназначена для выполнения в группе. Пожалуйста, "
                            "перейдите в чат с <a href='https://t.me/announcements_robot?start=list'>ботом</a>, чтобы "
                            "посмотреть список запланированных анонсов.\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                "Открыть чат с ботом",
                                url="https://t.me/announcements_robot?start=list"
                            )))
    else:
        update_users_data(
            chat_id=message.chat.id,
            username=message.from_user.username if not from_menu else None
        )

    user_events: list = []  # анонсы пользователя для вывода в виде str
    pages: list = []  # анонсы пользователя в виде объектов Job
    clipboard: list = []  # переменная-буфер для хранение промежуточных значений
    clipboard1: list = []

    showed_events: str = ""  # для перевода из list[str] в str

    events_per_page: int = 10  # количество анонсов на одной странице - без особой надобности
    counter: int = 1  # счетчик анонсов пользователя
    page_counter: int = 0  # счетчик страниц

    for event in events.delayed:
        if message.chat.id == int(event.id.split('__')[0]):
            if page_counter >= events_per_page:
                page_counter -= 10
                pages.append(clipboard)
                user_events.append(clipboard1)
                clipboard = []
                clipboard1 = []
            clipboard.append(event)
            event_name = event.name.replace('<', '&lt;').replace('>', '&gt;')
            clipboard1.append(f"{counter}. <i>{event_name if len(event.name) < 26 else f'{event_name[:25]}...'}</i>")
            counter += 1
            page_counter += 1

    if counter % 10 != 0:  # добавление остатков при кол-ве страниц не кратном 10
        pages.append(clipboard)
        user_events.append(clipboard1)

    if user_events != [[]]:
        for event in user_events[page]:
            showed_events += event + '\n'
    else:
        showed_events = "<i>Список пуст</i>\n"

    curr_page_button = types.InlineKeyboardButton(f"{page + 1} / {len(pages)}", callback_data="none")
    prev_page_button = types.InlineKeyboardButton("<", callback_data=f"list_prev_{page - 1}")
    next_page_button = types.InlineKeyboardButton(">", callback_data=f"list_next_{page + 1}")
    choose_event_button = types.InlineKeyboardButton("Выбрать анонс", callback_data=f"list_choose_{page}_0")
    open_mainmenu_button = types.InlineKeyboardButton("В главное меню", callback_data="open_mainmenu")

    events_list_keyboard = types.InlineKeyboardMarkup()

    if len(pages) == 1 and counter == 1:  # если 1 страница и список пуст
        events_list_keyboard.add(open_mainmenu_button)
    elif len(pages) == 1 and counter != 1:  # если 1 страница и анонсы есть
        events_list_keyboard.add(choose_event_button, open_mainmenu_button, row_width=1)
    elif len(pages) > 1 and page == 0:  # показ на начальной странице
        events_list_keyboard.add(curr_page_button, next_page_button, choose_event_button, row_width=2)
        events_list_keyboard.add(open_mainmenu_button)
    elif len(pages) > 1 and page == len(pages) - 1:  # на конечной
        events_list_keyboard.add(prev_page_button, curr_page_button, choose_event_button, row_width=2)
        events_list_keyboard.add(open_mainmenu_button)
    else:  # в промежутке
        events_list_keyboard.add(prev_page_button, curr_page_button, next_page_button, choose_event_button,
                                 row_width=3)
        events_list_keyboard.add(open_mainmenu_button)

    if not from_menu:
        return bot.send_message(message.chat.id,
                                f"<b>Список анонсов //</b>\n\n{showed_events}\nВсего запланировано: "
                                f"<b>{counter - 1 if showed_events != 'Список пуст' else 0}</b>",
                                parse_mode="HTML",
                                reply_markup=events_list_keyboard)
    else:
        return bot.edit_message_text(f"<b>Список анонсов //</b>\n\n{showed_events}\nВсего запланировано: "
                                     f"<b>{counter - 1 if showed_events != 'Список пуст' else 0}</b>",
                                     message.chat.id,
                                     message.id,
                                     parse_mode="HTML",
                                     reply_markup=events_list_keyboard)


@bot.message_handler(commands=["settings", "specs", "prefs", "setup"])
def settings_command(message: types.Message, from_menu: bool = False) -> types.Message:
    """
    Команда для настройки основных данных пользователя (в объекте класса Settings).
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :return: сообщение с inline-кнопками текущих настроек пользователя
    """

    if message.chat.id < 0:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            group=message.chat.id
        )
        return bot.reply_to(message,
                            "<b>Ошибка</b>: данная команда не предназначена для выполнения в группе. Пожалуйста, "
                            "перейдите в чат с <a href='https://t.me/announcements_robot?start=settings'>ботом</a>, чтобы "
                            "настроить параметры анонсов.\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                "Открыть чат с ботом",
                                url="https://t.me/announcements_robot?start=settings"
                            )))
    else:
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username if not from_menu else None
        )

    allow_preview = "ON" if settings.users[message.chat.id].allow_preview else "OFF"
    mention_all = "ON" if settings.users[message.chat.id].mention_all else "OFF"

    allow_preview_button = types.InlineKeyboardButton(f"Превью ссылок: {allow_preview}", callback_data="settings_ap")
    mention_all_button = types.InlineKeyboardButton(f"Упоминать всех: {mention_all}", callback_data="settings_ma")
    time_zones_button = types.InlineKeyboardButton(f"Часовой пояс: {settings.users[message.chat.id].time_zone}",
                                                   callback_data="settings_tz")
    main_group_button = types.InlineKeyboardButton(
        f"Главная группа: "
        f"{bot.get_chat(settings.users[message.chat.id].main_group).title if settings.users[message.chat.id].main_group < -1 else 'не выбрана'}",
        callback_data="settings_mg")
    open_mainmenu_button = types.InlineKeyboardButton("В главное меню", callback_data="open_mainmenu")

    settings_keyboard = types.InlineKeyboardMarkup(row_width=1)
    settings_keyboard.add(main_group_button, time_zones_button, mention_all_button, allow_preview_button,
                          open_mainmenu_button)

    if not from_menu:
        return bot.send_message(message.chat.id,
                                "<b>Настройки анонсов //</b>\n\n"
                                "Данные настройки распространяются на абсолютно все анонсы.",
                                parse_mode="HTML",
                                reply_markup=settings_keyboard)
    else:
        return bot.edit_message_text("<b>Настройки анонсов //</b>\n\n"
                                     "Данные настройки распространяются на абсолютно все анонсы.",
                                     message.chat.id,
                                     message.id,
                                     parse_mode="HTML",
                                     reply_markup=settings_keyboard)


@bot.message_handler(commands=["main_group", "mg", "group"])
def choose_main_group(message: types.Message, from_menu: bool = False, page=0) -> types.Message:
    """
    Команда для настройки главной группы для отправки анонсов.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :param page: страница пагинатора для вывода групп (если их много)
    :return: сообщение с inline-кнопками chat.id групп, где был замечен пользователь (из списка User.groups)
    """
    # ToDo: переделать логику "главных групп":
    #  1) сделать @all - отправку анонса во все группы?
    #  2) переделать вкладку в "группы", где пользователь может смотреть и удалять свои группы (+ добавлять новые)?

    if message.chat.id < 0:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            group=message.chat.id
        )
        return bot.reply_to(message,
                            "<b>Ошибка</b>: данная команда не предназначена для выполнения в группе. Пожалуйста, "
                            "перейдите в чат с <a href='https://t.me/announcements_robot?start=mg'>ботом</a>, чтобы "
                            "выбрать главную группу для анонсов.\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                "Открыть чат с ботом",
                                url="https://t.me/announcements_robot?start=mg"
                            )))
    else:
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username if not from_menu else None
        )

    pages: list[int | list] = []
    clipboard: list[int] = []
    buttons: list[types.InlineKeyboardButton] = []
    counter = 0

    prev_groups_page_button = types.InlineKeyboardButton("<", callback_data=f"mg_prev_{page - 1}")
    next_groups_page_button = types.InlineKeyboardButton(">", callback_data=f"mg_next_{page + 1}")
    add_bot_to_group_button = types.InlineKeyboardButton(
        "Добавить бота в группу",
        url="https://t.me/announcements_robot?startgroup=true",
        callback_data="none"
    )
    back_to_settings_button = types.InlineKeyboardButton("К настройкам анонсов", callback_data="open_settings")

    groups_keyboard = types.InlineKeyboardMarkup()

    if len(settings.users[message.chat.id].groups) != 0:
        for group in settings.users[message.chat.id].groups:
            if counter >= 10:
                counter -= 10
                pages.append(clipboard)
                clipboard = []
            clipboard.append(group)
            counter += 1

        if counter % 10 != 0:
            pages.append(clipboard)

        for group in pages[page]:
            buttons.append(types.InlineKeyboardButton(
                f"{bot.get_chat(group).title if group < -1 else 'не выбрана'}", callback_data=f"mg_{group}"))

        curr_groups_page_button = types.InlineKeyboardButton(f"{page + 1} / {len(pages)}", callback_data="none")

        if page == 0 and len(pages) > 1:
            groups_keyboard.add(curr_groups_page_button, next_groups_page_button, row_width=2)
            groups_keyboard.add(*buttons, add_bot_to_group_button, back_to_settings_button, row_width=1)
        elif page == len(pages) - 1 and len(pages) > 1:
            groups_keyboard.add(prev_groups_page_button, curr_groups_page_button, row_width=2)
            groups_keyboard.add(*buttons, add_bot_to_group_button, back_to_settings_button, row_width=1)
        elif page == 0 and len(pages) == 1:
            groups_keyboard.add(*buttons, add_bot_to_group_button, back_to_settings_button, row_width=1)
        else:
            groups_keyboard.add(prev_groups_page_button, curr_groups_page_button, next_groups_page_button, row_width=3)
            groups_keyboard.add(*buttons, add_bot_to_group_button, back_to_settings_button, row_width=1)
    else:
        groups_keyboard.add(add_bot_to_group_button, back_to_settings_button, row_width=1)

    if not from_menu:
        return bot.send_message(
            message.chat.id,
            f"<b>Настройки анонсов / Главная группа //</b>\n\n"
            f"В данную группу отправляются анонсы при указании получателя @all.\n\nТекущая: "
            f"<b>{bot.get_chat(settings.users[message.chat.id].main_group).title if settings.users[message.chat.id].main_group < -1 else 'не выбрана'}</b>",
            parse_mode="HTML",
            reply_markup=groups_keyboard)
    else:
        return bot.edit_message_text(
            f"<b>Настройки анонсов / Главная группа //</b>\n\n"
            f"В данную группу отправляются анонсы при указании получателя @all.\n\nТекущая: "
            f"<b>{bot.get_chat(settings.users[message.chat.id].main_group).title if settings.users[message.chat.id].main_group < -1 else 'не выбрана'}</b>",
            message.chat.id,
            message.id,
            parse_mode="HTML",
            reply_markup=groups_keyboard)


@bot.message_handler(commands=["timezone", "time_zone", "tz"])
def choose_time_zone_command(message: types.Message, from_menu: bool = False) -> types.Message:
    """
    Команда для настройки часового пояса отправляемых анонсов.
    :param message: сообщение пользователя или сообщение бота в случае from_menu == True
    :param from_menu: флаг для определения, откуда была вызвана команда: из inline-меню - True, пользователем - False
    :return: сообщение с inline-кнопками часовых поясов
    """

    if message.chat.id < 0:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            group=message.chat.id
        )
        return bot.reply_to(message,
                            "<b>Ошибка</b>: данная команда не предназначена для выполнения в группе. Пожалуйста, "
                            "перейдите в чат с <a href='https://t.me/announcements_robot?start=tz'>ботом</a>, чтобы "
                            "настроить часовой пояс анонсов.\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                "Открыть чат с ботом",
                                url="https://t.me/announcements_robot?start=tz"
                            )))
    else:
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username if not from_menu else None
        )

    # ToDo: пересмотреть установку часовых поясов:
    #  1) тумблер для пошагового изменения времени;
    #  2) массив для кнопок часовых поясов;
    #  3) пагинация для кнопок;
    #  4) показ региона-примера (напр. "UTC+3 (Москва)")?
    utc2_button = types.InlineKeyboardButton("UTC+2", callback_data="tz_utc2")
    utc3_button = types.InlineKeyboardButton("UTC+3", callback_data="tz_utc3")
    utc4_button = types.InlineKeyboardButton("UTC+4", callback_data="tz_utc4")
    utc5_button = types.InlineKeyboardButton("UTC+5", callback_data="tz_utc5")
    utc6_button = types.InlineKeyboardButton("UTC+6", callback_data="tz_utc6")
    utc7_button = types.InlineKeyboardButton("UTC+7", callback_data="tz_utc7")
    utc8_button = types.InlineKeyboardButton("UTC+8", callback_data="tz_utc8")
    utc9_button = types.InlineKeyboardButton("UTC+9", callback_data="tz_utc9")
    utc10_button = types.InlineKeyboardButton("UTC+10", callback_data="tz_utc10")
    utc11_button = types.InlineKeyboardButton("UTC+11", callback_data="tz_utc11")
    utc12_button = types.InlineKeyboardButton("UTC+12", callback_data="tz_utc12")
    open_settings_button = types.InlineKeyboardButton("К настройкам анонсов", callback_data="open_settings")

    timezones_keyboard = types.InlineKeyboardMarkup(row_width=2)
    timezones_keyboard.add(utc2_button, utc3_button, utc4_button, utc5_button, utc6_button, utc7_button, utc8_button,
                           utc9_button, utc10_button, utc11_button, utc12_button, open_settings_button)

    if not from_menu:
        return bot.send_message(message.chat.id,
                                "<b>Настройки анонсов / Часовой пояс //</b>"
                                "\n\nВремя всех анонсов корректируется в соответствии с указанным часовым поясом."
                                "\n\nТекущий: "
                                f"<b>{settings.users[message.chat.id].time_zone}</b>",
                                parse_mode="HTML",
                                reply_markup=timezones_keyboard)
    else:
        return bot.edit_message_text("<b>Настройки анонсов / Часовой пояс //</b>"
                                     "\n\nВремя всех анонсов корректируется в соответствии с указанным часовым поясом."
                                     "\n\nТекущий: "
                                     f"<b>{settings.users[message.chat.id].time_zone}</b>",
                                     message.chat.id,
                                     message.id,
                                     parse_mode="HTML",
                                     reply_markup=timezones_keyboard)


@bot.callback_query_handler(lambda call: "system_" in call.data)
def execute_system_commands(call: types.CallbackQuery) -> None:
    """
    Обработчик системных запросов.
    :param call: системный вызов через кнопку
    """
    match call.data.split('_')[1]:
        case "delete":
            bot.delete_message(call.message.chat.id, int(call.data.split('_')[2]))

    return None


@bot.callback_query_handler(lambda call: "list_" in call.data and "open_" not in call.data)
def events_paginator(call: types.CallbackQuery) -> types.Message:
    """
    Обработчик кнопок пагинации в команде для вывода списка запланированных анонсов и для выбора конкретного анонса.
    :param call: полученный вызов от пользователя через кнопку
    :return: отредактированное сообщение, полученное из call.message
    """

    update_users_data(chat_id=call.message.from_user.id)

    match call.data.split('_')[1]:
        case "prev" | "next":  # при пролистывании страниц, вызов той же самой команды повторно
            return events_list_command(call.message, int(call.data.split('_')[2]), True)
        case "choose":  # при выборе конкретного анонса на странице, повторное извлечение всех
            user_events: list = []  # анонсов пользователя, как и в events_list_command
            pages: list = []
            clipboard: list = []
            clipboard1: list = []

            showed_events: str = ""

            page_index: int = int(call.data.split('_')[2])  # индекс страницы в списке pages
            event_index: int = int(call.data.split('_')[3])  # индекс анонса в списке user_events

            events_per_page: int = 10  # переменная обретает новый смысл для пагинации по анонсам,
            counter: int = 1  # выводя "текущий анонс из events_per_page" (напр. "7 / 10")
            page_counter: int = 0

            for event in events.delayed:
                if call.message.chat.id == int(event.id.split('__')[0]):
                    if page_counter >= events_per_page:
                        page_counter -= 10
                        pages.append(clipboard)
                        user_events.append(clipboard1)
                        clipboard = []
                        clipboard1 = []
                    clipboard.append(event)
                    event_name = event.name.replace('<', '&lt;').replace('>', '&gt;')
                    clipboard1.append(
                        f"{counter}. <i>{event_name if len(event.name) < 26 else f'{event_name[:25]}...'}</i>")
                    counter += 1
                    page_counter += 1

            if counter % 10 != 0:
                pages.append(clipboard)
                user_events.append(clipboard1)

            i: int = 0
            for event in user_events[page_index]:  # выделение подчеркиванием выбранного анонса из
                if i == event_index:  # списка user_events на текущей странице
                    showed_events += "<u>" + event + "</u>\n"
                else:
                    showed_events += event + '\n'
                i += 1

            # ToDo: переделать эту переменную, сократив длину строки в коде
            event_info: str = \
                "Полное название: " \
                f"<b>{pages[page_index][event_index].name}</b>\n" \
                "ID анонса: " \
                f"<code>{pages[page_index][event_index].id.split('__')[2]}</code>\n" \
                f"Получатель{' (группа)' if pages[page_index][event_index].args[0] < 0 else ''}: " \
                f"<b>{'@' + settings.users[pages[page_index][event_index].args[0]].username if pages[page_index][event_index].args[0] > 0 else bot.get_chat(pages[page_index][event_index].args[0]).title}</b>\n" \
                f"{'Время отправки' if pages[page_index][event_index].id.split('__')[1] == 'date' else 'Следующее время отправки'}: " \
                f"<b>{pages[page_index][event_index].next_run_time.strftime('%d.%m.%Y в %H:%M')}</b>\n" \
                "Повторяющийся анонс: " \
                f"<b>{'ON' if pages[page_index][event_index].id.split('__')[1] == 'cron' else 'OFF'}</b>\n" \
                "Звуковое оповещение: " \
                f"<b>{'ON' if not pages[page_index][event_index].args[3] else 'OFF'}</b>"

            if counter < 11:  # если страница в pages одна
                events_per_page = counter - 1
            elif counter >= 11:  # если страниц в pages много
                if (counter - 1) % 10 != 0 and page_index == len(pages) - 1:  # на последней странице,
                    events_per_page = (counter - 1) % 10  # показ оставшихся анонсов
                else:
                    events_per_page = 10

            open_event_list_button = types.InlineKeyboardButton("К списку анонсов",
                                                                callback_data=f"list_prev_{call.data.split('_')[2]}")
            curr_event_button = types.InlineKeyboardButton(f"{event_index + 1} / {events_per_page}",
                                                           callback_data="none")
            prev_event_button = types.InlineKeyboardButton("<", callback_data=f"list_choose_"
                                                                              f"{call.data.split('_')[2]}_"
                                                                              f"{event_index - 1}")
            next_event_button = types.InlineKeyboardButton(">", callback_data=f"list_choose_"
                                                                              f"{call.data.split('_')[2]}_"
                                                                              f"{event_index + 1}")
            push_event_button = types.InlineKeyboardButton("Отправить сейчас",
                                                           callback_data=f"push_"
                                                                         f"{pages[page_index][event_index].id.split('__')[2]}"
                                                                         f"_{page_index}")
            delete_event_button = types.InlineKeyboardButton("Удалить",
                                                             callback_data="delete_"
                                                                           f"{pages[page_index][event_index].id.split('__')[2]}"
                                                                           f"_{page_index}")
            show_event_preview_button = types.InlineKeyboardButton("Предпросмотр",
                                                                   callback_data="preview_"
                                                                                 f"{pages[page_index][event_index].id.split('__')[2]}"
                                                                                 f"_{page_index}"
                                                                                 f"_{event_index}")

            choose_event_keyboard = types.InlineKeyboardMarkup()

            if len(pages[page_index]) in [0, 1]:  # анонсов нет или только один
                choose_event_keyboard.add(show_event_preview_button, push_event_button, delete_event_button,
                                          open_event_list_button, row_width=1)
            elif len(pages[page_index]) > 1 and event_index == 0:  # первый анонс из n
                choose_event_keyboard.add(curr_event_button, next_event_button, show_event_preview_button, row_width=2)
                choose_event_keyboard.add(push_event_button, delete_event_button, open_event_list_button, row_width=1)
            elif len(pages[page_index]) > 1 and event_index == events_per_page - 1:  # последний анонс
                choose_event_keyboard.add(prev_event_button, curr_event_button, show_event_preview_button, row_width=2)
                choose_event_keyboard.add(push_event_button, delete_event_button, open_event_list_button, row_width=1)
            else:  # в промежутке
                choose_event_keyboard.add(prev_event_button, curr_event_button, next_event_button,
                                          show_event_preview_button, row_width=3)
                choose_event_keyboard.add(push_event_button, delete_event_button, open_event_list_button, row_width=1)

            return bot.edit_message_text(f"<b>Список анонсов / Выбор анонса //</b>\n\n{showed_events}\n{event_info}",
                                         call.message.chat.id,
                                         call.message.id,
                                         parse_mode="HTML",
                                         reply_markup=choose_event_keyboard)


@bot.callback_query_handler(lambda call: "push_" in call.data)
def push_any_event(call: types.CallbackQuery) -> types.Message | None:
    """
    Обработчик кнопки отправки анонса без времени.
    :param call: полученный вызов от пользователя через кнопку
    :return: отправка анонса сейчас и отредактированное сообщение со списком анонсов
    """

    update_users_data(chat_id=call.message.from_user.id)

    event_id = call.data.split('_')[1]
    page = int(call.data.split('_')[2])

    msg = push_event_command(call.message, event_id, True)

    if msg is not None:
        if msg.id == call.message.id:
            return None

    return events_list_command(call.message, page, True)


@bot.callback_query_handler(lambda call: "delete_" in call.data)
def delete_any_event(call: types.CallbackQuery) -> types.Message | None:
    """
    Обработчик кнопки удаления анонсов.
    :param call: полученный вызов от пользователя через кнопку
    :return: удаление анонса и отредактированное сообщение со списком анонсов
    """

    update_users_data(chat_id=call.message.from_user.id)

    event_id = call.data.split('_')[1]
    page = int(call.data.split('_')[2])

    msg = delete_event_command(call.message, event_id, True)
    
    if msg.id == call.message.id:
        return None

    return events_list_command(call.message, page, True)


@bot.callback_query_handler(lambda call: "preview_" in call.data)
def show_event_preview_in_list(call: types.CallbackQuery) -> types.Message:
    """
    Обработчик кнопки предпросмотра анонса в списке.
    :param call: полученный вызов от пользователя через кнопку
    :return: редактирование сообщения со списком и для показа предпросмотра анонса
    """

    return show_event_preview_command(call.message, call.data.split('_')[1], True, "list_choose_"
                                                                                   f"{call.data.split('_')[2]}_"
                                                                                   f"{call.data.split('_')[3]}")


@bot.callback_query_handler(lambda call: "open_" in call.data)
def open_any_command(call: types.CallbackQuery) -> types.Message:
    """
    Обработчик кнопок для перехода к любой команде бота.
    :param call: полученный вызов от пользователя через кнопку
    :return: отредактированное сообщение с требуемой командой
    """

    update_users_data(chat_id=call.message.from_user.id)

    # очистка Reply клавиатуры
    if len(call.data.split('_')) == 3:
        if int(call.data.split('_')[2]) != 0:  # из create_event_command()
            bot.delete_message(call.message.chat.id, int(call.data.split('_')[2]))
        else:  # из event_catcher() и event_handler()
            msg = bot.send_message(call.message.chat.id, ".",
                                   disable_notification=True,
                                   reply_markup=types.ReplyKeyboardRemove())
            bot.delete_message(call.message.chat.id, msg.id)
    print(call.data)
    match call.data.split('_')[1]:
        case "mainmenu":
            bot.clear_step_handler_by_chat_id(call.message.chat.id)
            return main_menu_command(call.message, True)
        case "settings":
            return settings_command(call.message, True)
        case "create":
            return create_event_command(call.message, True)
        case "list":
            return events_list_command(call.message, 0, True)
        case "help":
            bot.clear_step_handler_by_chat_id(call.message.chat.id)
            return help_command(call.message, True)
        case "commands":
            return show_commands_command(call.message, True)
        case "support":
            return support_command(call.message, True)


@bot.callback_query_handler(lambda call: "mg_" in call.data)
def set_main_group(call: types.CallbackQuery) -> types.Message:
    """
    Обработчик кнопок выбора главной группы анонсов.
    :param call: полученный вызов от пользователя через кнопку
    :return: отредактированное сообщение из меню настроек анонсов
    """

    update_users_data(chat_id=call.message.from_user.id)

    group: int

    match call.data.split('_')[1]:
        case "next" | "prev":
            return choose_main_group(call.message, True, int(call.data.split('_')[2]))
        case _:
            group: int = int(call.data.split('_')[1])

    settings.users[call.message.chat.id].main_group = group

    allow_preview = "ON" if settings.users[call.message.chat.id].allow_preview else "OFF"
    mention_all = "ON" if settings.users[call.message.chat.id].mention_all else "OFF"

    allow_preview_button = types.InlineKeyboardButton(f"Превью ссылок: {allow_preview}", callback_data="settings_ap")
    mention_all_button = types.InlineKeyboardButton(f"Упоминать всех: {mention_all}", callback_data="settings_ma")
    time_zones_button = types.InlineKeyboardButton(f"Часовой пояс: {settings.users[call.message.chat.id].time_zone}",
                                                   callback_data="settings_tz")
    main_group_button = types.InlineKeyboardButton(
        f"Главная группа: "
        f"{bot.get_chat(settings.users[call.message.chat.id].main_group).title if settings.users[call.message.chat.id].main_group < -1 else 'не выбрана'}",
        callback_data="settings_mg"
    )
    open_mainmenu_button = types.InlineKeyboardButton("В главное меню", callback_data="open_mainmenu")

    settings_keyboard = types.InlineKeyboardMarkup(row_width=1)
    settings_keyboard.add(main_group_button, time_zones_button, mention_all_button, allow_preview_button,
                          open_mainmenu_button)

    return bot.edit_message_text("<b>Настройки анонсов //</b>\n\n"
                                 "Данные настройки распространяются на абсолютно все анонсы.",
                                 call.message.chat.id,
                                 call.message.id,
                                 parse_mode="HTML",
                                 reply_markup=settings_keyboard)


@bot.callback_query_handler(lambda call: "tz_" in call.data)
def set_time_zone(call: types.CallbackQuery) -> types.Message:
    """
    Обработчик кнопок выбора часового пояса.
    :param call: полученный вызов от пользователя через кнопку
    :return: отредактированное сообщение из меню настроек анонсов
    """

    update_users_data(chat_id=call.message.from_user.id)

    # ToDo: пересмотреть извлечение часового пояса и присвоение к User.time_zone:
    #  1) call.data.split()?
    #  2) call.data[:]?
    match call.data:
        case "tz_utc2":
            settings.users[call.message.chat.id].time_zone = timezone(timedelta(hours=2))
        case "tz_utc3":
            settings.users[call.message.chat.id].time_zone = timezone(timedelta(hours=3))
        case "tz_utc4":
            settings.users[call.message.chat.id].time_zone = timezone(timedelta(hours=4))
        case "tz_utc5":
            settings.users[call.message.chat.id].time_zone = timezone(timedelta(hours=5))
        case "tz_utc6":
            settings.users[call.message.chat.id].time_zone = timezone(timedelta(hours=6))
        case "tz_utc7":
            settings.users[call.message.chat.id].time_zone = timezone(timedelta(hours=7))
        case "tz_utc8":
            settings.users[call.message.chat.id].time_zone = timezone(timedelta(hours=8))
        case "tz_utc9":
            settings.users[call.message.chat.id].time_zone = timezone(timedelta(hours=9))
        case "tz_utc10":
            settings.users[call.message.chat.id].time_zone = timezone(timedelta(hours=10))
        case "tz_utc11":
            settings.users[call.message.chat.id].time_zone = timezone(timedelta(hours=11))
        case "tz_utc12":
            settings.users[call.message.chat.id].time_zone = timezone(timedelta(hours=12))

    allow_preview = "ON" if settings.users[call.message.chat.id].allow_preview else "OFF"
    mention_all = "ON" if settings.users[call.message.chat.id].mention_all else "OFF"

    allow_preview_button = types.InlineKeyboardButton(f"Превью ссылок: {allow_preview}", callback_data="settings_ap")
    mention_all_button = types.InlineKeyboardButton(f"Упоминать всех: {mention_all}", callback_data="settings_ma")
    time_zones_button = types.InlineKeyboardButton(f"Часовой пояс: {settings.users[call.message.chat.id].time_zone}",
                                                   callback_data="settings_tz")
    main_group_button = types.InlineKeyboardButton(
        f"Главная группа: "
        f"{bot.get_chat(settings.users[call.message.chat.id].main_group).title if settings.users[call.message.chat.id].main_group < -1 else 'не выбрана'}",
        callback_data="settings_mg"
    )
    open_mainmenu_button = types.InlineKeyboardButton("В главное меню", callback_data="open_mainmenu")

    settings_keyboard = types.InlineKeyboardMarkup(row_width=1)
    settings_keyboard.add(main_group_button, time_zones_button, mention_all_button, allow_preview_button,
                          open_mainmenu_button)

    return bot.edit_message_text("<b>Настройки анонсов //</b>\n\n"
                                 "Данные настройки распространяются на абсолютно все анонсы.",
                                 call.message.chat.id,
                                 call.message.id,
                                 parse_mode="HTML",
                                 reply_markup=settings_keyboard)


@bot.callback_query_handler(lambda call: "settings_" in call.data)
def settings_menues(call: types.CallbackQuery) -> types.Message:
    """
    Обработчик всех кнопок в меню настроек анонсов (команде settings).
    :param call: полученный вызов от пользователя через кнопку
    :return: отредактированное сообщение с выбираемыми (или выбранными) настройками
    """

    update_users_data(chat_id=call.message.from_user.id)

    match call.data:
        case "settings_mg":
            return choose_main_group(call.message, True)
        case "settings_tz":
            return choose_time_zone_command(call.message, True)
        case "settings_ma":  # установка обратного значения для булевых параметров
            settings.users[call.message.chat.id].mention_all = False if \
                settings.users[call.message.chat.id].mention_all else True
        case "settings_ap":
            settings.users[call.message.chat.id].allow_preview = False if \
                settings.users[call.message.chat.id].allow_preview else True

    allow_preview = "ON" if settings.users[call.message.chat.id].allow_preview else "OFF"
    mention_all = "ON" if settings.users[call.message.chat.id].mention_all else "OFF"

    allow_preview_button = types.InlineKeyboardButton(f"Превью ссылок: {allow_preview}", callback_data="settings_ap")
    mention_all_button = types.InlineKeyboardButton(f"Упоминать всех: {mention_all}", callback_data="settings_ma")
    time_zones_button = types.InlineKeyboardButton(f"Часовой пояс: {settings.users[call.message.chat.id].time_zone}",
                                                   callback_data="settings_tz")
    main_group_button = types.InlineKeyboardButton(
        f"Главная группа: "
        f"{bot.get_chat(settings.users[call.message.chat.id].main_group).title if settings.users[call.message.chat.id].main_group < -1 else 'не выбрана'}",
        callback_data="settings_mg"
    )
    open_mainmenu_button = types.InlineKeyboardButton("В главное меню", callback_data="open_mainmenu")

    settings_keyboard = types.InlineKeyboardMarkup(row_width=1)
    settings_keyboard.add(main_group_button, time_zones_button, mention_all_button, allow_preview_button,
                          open_mainmenu_button)

    return bot.edit_message_text("<b>Настройки анонсов //</b>\n\n"
                                 "Данные настройки распространяются на абсолютно все анонсы.",
                                 call.message.chat.id,
                                 call.message.id,
                                 parse_mode="HTML",
                                 reply_markup=settings_keyboard)


@bot.message_handler(content_types=["text"])
def alternative_all_command(message: types.Message) -> types.Message | None:
    """
    Альтернативный вызов команды all через @all в тексте сообщения.
    :param message: сообщение пользователя
    :return: сообщение с вызванной командой all в случае нахождения @all, иначе None
    """

    if message.chat.id < 0:
        update_groups_data(message.chat.id)

    update_users_data(
        chat_id=message.from_user.id,
        username=message.from_user.username,
        group=message.chat.id if message.chat.id < 0 else None
    )

    if str(message.text).find("@all") != -1:
        return mention_all_command(message)
    else:
        return None


@bot.message_handler(content_types=["web_app_data"])
def event_catcher(message) -> types.Message | None:
    """
    Ловец JSON-данных из веб-приложения и их шлифовщик.
    :param message: сообщение пользователя с данными из веб-приложения
    :return: сообщение отправителю в случае успешного создания анонса или возникновении ошибок в catcher, в остальных случаях None
    """
    if message.chat.id > 0:
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username
        )
    else:
        update_groups_data(message.chat.id)
        update_users_data(
            chat_id=message.from_user.id,
            username=message.from_user.username,
            group=message.chat.id,
            main_group=message.chat.id
        )
        return bot.reply_to(message,
                            "<b>Ошибка</b>: бот не способен получать данные об анонсе из группы. Пожалуйста, "
                            "перейдите в чат с <a href='https://t.me/announcements_robot?start=add'>ботом</a>, чтобы "
                            "создать новый анонс.\n\n<b>Ознакомиться со справкой – /help</b>",
                            parse_mode="HTML",
                            disable_web_page_preview=True,
                            reply_markup=types.InlineKeyboardMarkup().add(types.InlineKeyboardButton(
                                "Открыть чат с ботом",
                                url="https://t.me/announcements_robot?start=add"
                            )))

    event_catcher_keyboard = types.InlineKeyboardMarkup()

    event: dict = json.loads(message.web_app_data.data)

    # logger.debug(f"Получены данные об анонсе от {message.from_user.username} ({message.chat.id}): {event}")
    # bot.send_message(message.chat.id, f"{event}")

    # Проверка парсинга HTML
    if any([x in event["title"] for x in ['<', '>']]) or any([x in event["description"] for x in ['<', '>']]):
        validation_html_msg = bot.send_message(message.chat.id,
                                               "<b>Предупреждение</b>: производится проверка HTML-элементов в текстовых"
                                               " полях создаваемого анонса.",
                                               parse_mode="HTML")
        error_in_title: bool = False
        error_in_description: bool = False

        if any([x in event["title"] for x in ['<', '>']]):
            try:
                bot.edit_message_text("<b>Предупреждение</b>: производится проверка HTML-элементов в текстовых "
                                      f"полях создаваемого анонса.\n\n<b>Проверка заголовка:</b>\n\n{event['title']}",
                                      message.chat.id,
                                      validation_html_msg.id,
                                      parse_mode="HTML")
            except Exception as title_error:
                error_in_title = True
                event["title"] = event["title"].replace('<', "&lt;").replace('>', "&gt;")
                logger.debug("Найденные HTML-элементы в заголовке анонса были отключены заменой угловых скобок на "
                             f"специальные символы: {title_error}")

        if any([x in event["description"] for x in ['<', '>']]):
            try:
                bot.edit_message_text("<b>Предупреждение</b>: производится проверка HTML-элементов в текстовых"
                                      " полях создаваемого анонса.\n\n"
                                      f"<b>Проверка заголовка: {'успешно' if not error_in_title else 'ошибка'}</b>"
                                      f"\n<b>Проверка описания:</b>\n\n{event['description']}",
                                      message.chat.id,
                                      validation_html_msg.id,
                                      parse_mode="HTML")
            except Exception as description_error:
                error_in_description = True
                event["description"] = event["description"].replace('<', "&lt;").replace('>', "&gt;")
                logger.debug("Найденные HTML-элементы в описании анонса были отключены заменой угловых скобок на "
                             f"специальные символы: {description_error}")

        error_text = "Пожалуйста, перед созданием анонса, ознакомтесь с порядком использования HTML-синтаксиса в " \
                     "текстовых полях.\n\n<b>Ознакомиться со справкой – /help</b>"
        ok_text = "Проверки пройдены успешно. Спасибо, что используете корректный HTML-синтаксис!"

        bot.edit_message_text("<b>Предупреждение</b>: производится проверка HTML-элементов в текстовых"
                              " полях создаваемого анонса.\n\n"
                              f"<b>Проверка заголовка: {'успешно' if not error_in_title else 'ошибка'}</b>"
                              f"\n<b>Проверка описания: {'успешно' if not error_in_description else 'ошибка'}</b>\n\n"
                              f"{error_text if error_in_description or error_in_title else ok_text}",
                              message.chat.id,
                              validation_html_msg.id,
                              parse_mode="HTML")

    # Поиск адресатов в базе
    match event["sendTo"]:
        case "@all":  # для групп
            event["sendTo"] = settings.users[message.chat.id].main_group \
                if settings.users[message.chat.id].main_group != -1 else message.chat.id
            if event["sendTo"] == message.chat.id:
                bot.send_message(message.chat.id,
                                 "<b>Предупреждение</b>: главная группа для отправки данного анонса всем ее участникам "
                                 "не была выбрана в настройках бота, поэтому анонс будет отправлен в "
                                 "<a href='https://t.me/announcements_robot'>этот чат</a>. Пожалуйста, укажите главную "
                                 "группу для отправки анонсов всем ее участникам, используя команду /settings и "
                                 "создайте новый анонс.\n\n<b>Ознакомиться со справкой – /help</b>",
                                 parse_mode="HTML",
                                 disable_web_page_preview=True)
        case _:  # для одного получателя
            sendto_correct: bool = True
            # проверка на цифры для преобразования в int
            for sign in event["sendTo"]:
                if not sign.isdigit():
                    sendto_correct = False

            if sendto_correct:
                event["sendTo"] = int(event["sendTo"])
                if event["sendTo"] not in settings.users:
                    event["sendTo"] = message.chat.id
                    bot.send_message(message.chat.id,
                                     "<b>Предупреждение</b>: указанный получатель не найден в базе данных, поэтому "
                                     "анонс будет отправлен в <a href='https://t.me/announcements_robot'>этот чат</a>. "
                                     "Пожалуйста, попросите получателя запустить бота, выполнить команду (например, "
                                     "/id) или написать любое сообщение в чате или группе с ботом."
                                     "\n\n<b>Ознакомиться со справкой – /help</b>",
                                     parse_mode="HTML",
                                     disable_web_page_preview=True)
            else:  # если получателя нет, анонс получит отправитель
                bot.send_message(message.chat.id,
                                 "<b>Ошибка</b>: указан некорректный получатель анонса, поэтому анонс будет отправлен "
                                 "в <a href='https://t.me/announcements_robot'>этот чат</a>. Пожалуйста, отправьте "
                                 "обращение в техподдержку через /support, обязательно указав в тексте обращения этот "
                                 f"текст: \n\n<code>sendTo: {event['sendTo']}</code>"
                                 "\n\n<b>Ознакомиться со справкой – /help</b>",
                                 parse_mode="HTML",
                                 disable_web_page_preview=True)
                event["sendTo"] = message.chat.id

    event["with-sound"] = True if event["with-sound"] == "false" else False
    # ^~~ True на "false", потому что bot.send_message(..., disable_notifications=True) отправляет сообщение без звука

    match event["weekday"]:
        case "monday" | 1:
            event["weekday"] = 1
        case "tuesday" | 2:
            event["weekday"] = 2
        case "wednesday" | 3:
            event["weekday"] = 3
        case "thursday" | 4:
            event["weekday"] = 4
        case "friday" | 5:
            event["weekday"] = 5
        case "saturday" | 6:
            event["weekday"] = 6
        case "sunday" | 7:
            event["weekday"] = 7
        case _:
            event["weekday"] = 0  # день недели не выбран (откл.)

    current_time = datetime.now(tz=settings.users[message.chat.id].time_zone)

    match event["repeated"]:
        # неповторяющееся событие
        case "false":
            # Указан только день недели или день недели и время
            if event["date"] == "none" and event["weekday"] != 0:
                event["date"] = current_time.strftime("%Y-%m-%d")
                event["time"] = current_time.strftime("%H:%M") if event["time"] == "none" else event["time"]
                if current_time.strftime("%Y-%m-%d") == event["date"] and current_time.strftime("%H:%M") == \
                        event["time"]:
                    event["date"] = (current_time + timedelta(minutes=5)).strftime("%Y-%m-%d")
                    event["time"] = (current_time + timedelta(minutes=5)).strftime("%H:%M")
                while datetime.strptime(f"{event['date']} {event['time']}:00", "%Y-%m-%d %H:%M:%S").isoweekday() != \
                        event["weekday"] or \
                        date_is_in_past(
                            datetime.strptime(f"{event['date']} {event['time']}:00", "%Y-%m-%d %H:%M:%S").replace(
                                tzinfo=settings.users[message.chat.id].time_zone), current_time):
                    event["date"] = (datetime.strptime(f"{event['date']} {event['time']}:00", "%Y-%m-%d %H:%M:%S") +
                                     timedelta(days=1)).strftime("%Y-%m-%d")
                if current_time.strftime("%Y-%m-%d") == event["date"] and current_time.strftime("%H:%M") == \
                        event["time"]:
                    event["date"] = (current_time + timedelta(minutes=5)).strftime("%Y-%m-%d")
                    event["time"] = (current_time + timedelta(minutes=5)).strftime("%H:%M")
            # Указано только время или дата и время
            elif event["time"] != "none" and event["weekday"] == 0:
                if event["date"] == "none":
                    event["date"] = current_time.strftime("%Y-%m-%d")
                    if date_is_in_past(
                            datetime.strptime(
                                f"{event['date']} {event['time']}:00",
                                "%Y-%m-%d %H:%M:%S").replace(tzinfo=settings.users[message.chat.id].time_zone),
                            current_time):
                        event["date"] = (current_time + timedelta(days=1)).strftime("%Y-%m-%d")
                if current_time.strftime("%Y-%m-%d") == event["date"] and current_time.strftime("%H:%M") == \
                        event["time"]:
                    event["date"] = (current_time + timedelta(minutes=5)).strftime("%Y-%m-%d")
                    event["time"] = (current_time + timedelta(minutes=5)).strftime("%H:%M")
            # Указана дата и день недели
            elif event["date"] != "none" and event["weekday"] != 0 and event["time"] == "none":
                event["time"] = current_time.strftime("%H:%M")
                if event["date"] == current_time.strftime("%Y-%m-%d"):
                    event["date"] = (current_time + timedelta(minutes=5)).strftime("%Y-%m-%d")
                    event["time"] = (current_time + timedelta(minutes=5)).strftime("%H:%M")
            # Указана только дата
            elif event["date"] != "none" and event["time"] == "none" and event["weekday"] == 0:
                if event["date"] == current_time.strftime("%Y-%m-%d"):
                    event["date"] = (current_time + timedelta(minutes=5)).strftime("%Y-%m-%d")
                    event["time"] = (current_time + timedelta(minutes=5)).strftime("%H:%M")
                else:
                    event["time"] = current_time.strftime("%H:%M")
            # Данные о времени не указаны
            elif event["date"] == "none" and event["time"] == "none" and event["weekday"] == 0:
                event["date"] = (current_time + timedelta(minutes=5)).strftime("%Y-%m-%d")
                event["time"] = (current_time + timedelta(minutes=5)).strftime("%H:%M")
        # повторяющееся событие
        case "true":
            # данных о времени нет
            if event["date"] == event["time"] and event["weekday"] == 0:
                event_catcher_keyboard.add(
                    types.InlineKeyboardButton("В главное меню", callback_data="open_mainmenu_0"))
                return bot.send_message(message.chat.id,
                                        "<b>Ошибка</b>: при создании повторяющегося анонса не были указаны данные о "
                                        "его времени. Пожалуйста, создайте новый повторяющийся анонс через /add, "
                                        "указав время, которое должно регулярно повторяться."
                                        "\n\n<b>Ознакомиться со справкой – /help</b>",
                                        parse_mode="HTML",
                                        reply_markup=event_catcher_keyboard)
            else:
                event["date"] = f"none {current_time.strftime('%Y-%m-%d')}" if event["date"] == "none" \
                    else event["date"]
                event["time"] = f"none {current_time.strftime('%H:%M')}" if event["time"] == "none" else event["time"]

    event_codes = event_handler(
        message.chat.id,
        {
            "title": event["title"],
            "description": event["description"],
            "sendTo": event["sendTo"],
            "date": event["date"],
            "time": event["time"],
            "weekday": event["weekday"],
            "repeated": event["repeated"],
            "with_sound": event["with-sound"]
            # используем '-' в ключах словарей только в catcher, далее '_' из-за SQLite
        },
        from_database=False,
        message=message,
        current_time=current_time)

    # анонс или анонсы созданы
    if len(event_codes) != 0:
        text: str
        event_datetime = None

        for delayed in events.delayed:
            if event_codes[0] in delayed.id.split('__')[2]:
                event_datetime = delayed.next_run_time
                break

        if len(event_codes) > 1:
            text = f"<b>Оповещение</b>: анонсы под общим названием <b>{event['title']}</b> успешно созданы! Чтобы обратится к ним, " \
                   f"используйте данные коды:\n\n<code>{event_codes[0]}</code>\n<code>{event_codes[1]}</code>\n\n" \
                   f"Ближайший анонс будет отправлен: " \
                   f"<b>{event_datetime.strftime('%d.%m.%Y в %H:%M') if event_datetime is not None else 'ошибка'}</b>"
        else:
            text = f"<b>Оповещение</b>: анонс под названием <b>{event['title']}</b> успешно создан! Чтобы обратится к нему, используйте " \
                   f"данный код:\n\n<code>{event_codes[0]}</code>\n\n" \
                   f"Анонс будет отправлен: " \
                   f"<b>{event_datetime.strftime('%d.%m.%Y в %H:%M') if event_datetime is not None else 'ошибка'}</b>"

        event_catcher_keyboard.add(types.InlineKeyboardButton("К списку анонсов", callback_data="open_list_0"))
        event_catcher_keyboard.add(types.InlineKeyboardButton("В главное меню", callback_data="open_mainmenu_0"))

        return bot.send_message(message.chat.id, text, "HTML",
                                reply_markup=event_catcher_keyboard)
    # анонс не создан
    else:
        return None


def event_handler(chat_id: int, event: dict, from_database: bool = False, message=None,
                  current_time: datetime = None) -> list:
    """
    Обработчик анонсов, занимающийся заполнением events.delayed: list
    :param chat_id: chat.id пользователя, полученный из types.Message.chat.id (отправитель)
    :param event: анонс, переведенный в тип dict из JSON, полученного из types.Message.web_app_data.data
    :param from_database: если False, то обработка анонса идет в теле event_catcher(), иначе при запуске программы
    :param message: необходим только в случае обработки анонса из event_catcher()
    :param current_time: текущее время, измеренное в event_catcher()
    :return: event_ids: list[Job.id] - список созданных id анонсов
    """

    event_ids: list = []

    open_mainmenu_button = types.InlineKeyboardButton("В главное меню", callback_data="open_mainmenu_0")
    event_handler_keyboard = types.InlineKeyboardMarkup().add(open_mainmenu_button)

    # дата неповторяющегося анонса в прошлом (при создании из чата)
    if not from_database and event["repeated"] == "false":
        if date_is_in_past(
                datetime.strptime(
                    f"{event['date']} {event['time']}:00",
                    "%Y-%m-%d %H:%M:%S").replace(tzinfo=settings.users[chat_id].time_zone), current_time):
            error_date = datetime.strptime(f"{event['date']} {event['time']}", "%Y-%m-%d %H:%M"). \
                strftime("%d.%m.%Y, %H:%M")
            logger.info(f"Ошибка при заполнении массива events.delayed: анонс {event['title']} "
                        f"имеет дату из прошлого ({error_date}).")
            bot.send_message(message.chat.id,
                             "<b>Ошибка</b>: при создании анонса была указана дата из "
                             f"прошлого (<i>{error_date}</i>). Пожалуйста, создайте "
                             "новый анонс через /add, используя корректную дату."
                             "\n\n<b>Ознакомиться со справкой – /help</b>",
                             parse_mode="HTML",
                             reply_markup=event_handler_keyboard)
            return event_ids
    # дата неповторяющегося анонса в прошлом (при заполнении из БД)
    elif from_database and event["repeated"] == "false":
        if date_is_in_past(
                datetime.strptime(
                    f"{event['date']} {event['time']}:00",
                    "%Y-%m-%d %H:%M:%S").replace(tzinfo=settings.users[chat_id].time_zone), current_time, delay_sec=20):
            error_date = datetime.strptime(f"{event['date']} {event['time']}", "%Y-%m-%d %H:%M"). \
                strftime("%d.%m.%Y, %H:%M")
            logger.info(f"Ошибка при заполнении массива delayed_events: анонс {event['title']} "
                        f"имеет дату из прошлого ({error_date}).")
            return event_ids

    if not from_database:  # внесение анонса к анонсам пользователя после всех проверок
        if message.chat.id not in events.users:
            events.users[message.chat.id] = [
                {
                    "title": event["title"],
                    "description": event["description"],
                    "sendTo": event["sendTo"],
                    "date": event["date"],
                    "time": event["time"],
                    "weekday": event["weekday"],
                    "repeated": event["repeated"],
                    "with_sound": event["with_sound"]
                }
            ]
        else:
            events.users[message.chat.id].append(
                {
                    "title": event["title"],
                    "description": event["description"],
                    "sendTo": event["sendTo"],
                    "date": event["date"],
                    "time": event["time"],
                    "weekday": event["weekday"],
                    "repeated": event["repeated"],
                    "with_sound": event["with_sound"]
                }
            )

    if chat_id not in events.previews:
        events.previews[chat_id] = []

    match event["repeated"]:

        case "false":

            if current_time is None:
                current_time = datetime.now(tz=settings.users[chat_id].time_zone)

            event_datetime = datetime.strptime(f"{event['date']} {event['time']}:00", "%Y-%m-%d %H:%M:%S")

            event_ids.append(f"{event_datetime.strftime('%d%m%y%H%M')}{current_time.strftime('%S%f')}")

            text = "\n\n" if event["description"] in ["none", ""] or \
                event["description"][0] * len(event["description"]) == ' ' * len(event["description"]) \
                else f"\n\n{event['description']}\n\n"

            if chat_id in settings.users:
                text += f"@{settings.users[chat_id].username}"
            else:
                text = f"\n\n{event['description']}"
                update_users_data(
                    chat_id=chat_id
                )

            if text == "\n\n":
                text = ""

            events.delayed.append(
                scheduler.add_job(
                    send_event, "date", run_date=f"{event['date']} {event['time']}:00",
                    timezone=settings.users[chat_id].time_zone,
                    args=[event["sendTo"], f"<b>{event['title']}</b>{text}",
                          "HTML", event["with_sound"], chat_id, event["title"], event_ids[0]],
                    id=f"{chat_id}__date__{event_ids[0]}",
                    name=event["title"]
                )
            )

            events.previews[chat_id].append({event_ids[0]: f"<b>{event['title']}</b>{text}"})

            # создание второго анонса при дне недели != дате
            if event["weekday"] != 0 and \
                    datetime.strptime(f"{event['date']} {event['time']}:00", "%Y-%m-%d %H:%M:%S").isoweekday() \
                    != event["weekday"]:

                sleep(1)

                current_time = datetime.now(tz=settings.users[chat_id].time_zone)

                end_date = datetime.strptime(f"{event['date']} {event['time']}:00", "%Y-%m-%d %H:%M:%S")

                while end_date.isoweekday() != event["weekday"] or \
                        end_date == current_time:
                    end_date += timedelta(days=1)

                event_ids.append(f"{end_date.strftime('%d%m%y%H%M')}{current_time.strftime('%S%f')}")

                events.delayed.append(
                    scheduler.add_job(
                        send_event, "date", run_date=end_date,
                        timezone=settings.users[chat_id].time_zone,
                        args=[event["sendTo"], f"<b>{event['title']}</b>{text}",
                              "HTML", event["with_sound"], chat_id, event["title"], event_ids[1]],
                        id=f"{chat_id}__date__{event_ids[1]}",
                        name=event["title"]
                    )
                )

                events.previews[chat_id].append({event_ids[1]: f"<b>{event['title']}</b>{text}"})

            return event_ids

        case "true":

            if current_time is None:
                current_time = datetime.now(tz=settings.users[chat_id].time_zone)

            text = "\n\n" if event["description"] in ["none", ""] or \
                event["description"][0] * len(event["description"]) == ' ' * len(event["description"]) \
                else f"\n\n{event['description']}\n\n"

            if chat_id in settings.users:
                text += f"@{settings.users[chat_id].username}"
            else:
                text = f"\n\n{event['description']}"
                update_users_data(
                    chat_id=chat_id
                )

            if text == "\n\n":
                text = ""

            # Указаны только дата и время
            if event["weekday"] == 0 and "none" not in event["date"] and "none" not in event["time"]:

                event_datetime = datetime.strptime(f"{event['date']} {event['time']}:00", "%Y-%m-%d %H:%M:%S")

                event_ids.append(f"{event_datetime.strftime('%d%m%y%H%M')}{current_time.strftime('%S%f')}")

                events.delayed.append(
                    scheduler.add_job(
                        send_event, "cron", day=event_datetime.strftime('%d'),
                        hour=event_datetime.strftime('%H'),
                        minute=event_datetime.strftime('%M'),
                        timezone=settings.users[chat_id].time_zone,
                        args=[event["sendTo"], f"<b>{event['title']}</b>{text}",
                              "HTML", event["with_sound"], chat_id, event["title"], event_ids[0]],
                        id=f"{chat_id}__cron__{event_ids[0]}",
                        name=event["title"]
                    )
                )

                events.previews[chat_id].append({event_ids[0]: f"<b>{event['title']}</b>{text}"})

            # Указано только время
            elif "none" in event["date"] and "none" not in event["time"] and event["weekday"] == 0:

                event_datetime = datetime.strptime(f"{event['date'].split(' ')[1]} {event['time']}", "%Y-%m-%d %H:%M")

                event_ids.append(f"{event_datetime.strftime('%d%m%y%H%M')}{current_time.strftime('%S%f')}")

                events.delayed.append(
                    scheduler.add_job(
                        send_event, "cron", hour=event["time"][:2], minute=event["time"][3:],
                        timezone=settings.users[chat_id].time_zone,
                        args=[event["sendTo"], f"<b>{event['title']}</b>{text}",
                              "HTML", event["with_sound"], chat_id, event["title"], event_ids[0]],
                        id=f"{chat_id}__cron__{event_ids[0]}",
                        name=event["title"]
                    )
                )

                events.previews[chat_id].append({event_ids[0]: f"<b>{event['title']}</b>{text}"})

            # Указана только дата
            elif "none" in event["time"] and "none" not in event["date"] and event["weekday"] == 0:

                event_datetime = datetime.strptime(f"{event['date']} {event['time'].split(' ')[1]}", "%Y-%m-%d %H:%M")

                event_ids.append(f"{event_datetime.strftime('%d%m%y%H%M')}{current_time.strftime('%S%f')}")

                events.delayed.append(
                    scheduler.add_job(
                        send_event, "cron", day=event_datetime.strftime("%d"),
                        hour=event_datetime.strftime("%H"),
                        minute=event_datetime.strftime("%M"),
                        timezone=settings.users[chat_id].time_zone,
                        args=[event["sendTo"], f"<b>{event['title']}</b>{text}",
                              "HTML", event["with_sound"], chat_id, event["title"], event_ids[0]],
                        id=f"{chat_id}__cron__{event_ids[0]}",
                        name=event["title"]
                    )
                )

                events.previews[chat_id].append({event_ids[0]: f"<b>{event['title']}</b>{text}"})

            # Указан только день недели или день недели и время
            elif event["weekday"] != 0 and "none" in event["date"]:

                event["time"] = event["time"].split(' ')[1] if "none" in event["time"] else event["time"]

                event_datetime = datetime.strptime(f"{event['date'].split(' ')[1]} {event['time']}",
                                                   "%Y-%m-%d %H:%M")
                event_ids.append(f"{event_datetime.strftime('%d%m%y%H%M')}{current_time.strftime('%S%f')}")

                events.delayed.append(
                    scheduler.add_job(
                        send_event, "cron", day_of_week=event["weekday"] - 1,
                        hour=event_datetime.strftime("%H"),
                        minute=event_datetime.strftime("%M"),
                        timezone=settings.users[chat_id].time_zone,
                        args=[event["sendTo"], f"<b>{event['title']}</b>{text}",
                              "HTML", event["with_sound"], chat_id, event["title"], event_ids[0]],
                        id=f"{chat_id}__cron__{event_ids[0]}",
                        name=event["title"]
                    )
                )

                events.previews[chat_id].append({event_ids[0]: f"<b>{event['title']}</b>{text}"})

            # Указан день недели во всех остальных случаях
            elif event["weekday"] != 0 and "none" not in event["date"]:

                event["time"] = event["time"].split(' ')[1] if "none" in event["time"] else event["time"]

                event_datetime = datetime.strptime(f"{event['date']} {event['time']}", "%Y-%m-%d %H:%M")

                event_ids.append(f"{event_datetime.strftime('%d%m%y%H%M')}{current_time.strftime('%S%f')}")

                events.delayed.append(
                    scheduler.add_job(
                        send_event, "cron", day=f"{event_datetime.strftime('%d')}",
                        day_of_week=event["weekday"] - 1,
                        hour=event_datetime.strftime("%H"),
                        minute=event_datetime.strftime("%M"),
                        timezone=settings.users[chat_id].time_zone,
                        args=[event["sendTo"], f"<b>{event['title']}</b>{text}",
                              "HTML", event["with_sound"], chat_id, event["title"], event_ids[0]],
                        id=f"{chat_id}__cron__{event_ids[0]}",
                        name=event["title"]
                    )
                )

                events.previews[chat_id].append({event_ids[0]: f"<b>{event['title']}</b>{text}"})

            return event_ids


def update_users_data(chat_id: int, username: str = None, main_group: int = None, mention_all: bool = None,
                      group: int = None, time_zone: timezone = None, allow_preview: bool = None) -> None:
    """
    Инициализация и обновление объектов-пользователей Settings.User в списке settings.users
    :param chat_id: уникальный идентификатор пользователя телеграм
    :param username: никнейм пользователя
    :param main_group: главная группа для анонсов (по умолчанию - -1)
    :param mention_all: параметр "упоминать всех"
    :param group: все группы, где присутствует и бот, и пользователь
    :param time_zone: часовой пояс пользователя (по умолчанию - UTC+3 (МСК))
    :param allow_preview: параметр "предпоказ ссылок"
    """
    # создание нового пользователя в базе
    if chat_id not in settings.users:
        settings.users[chat_id] = settings.User(
            chat_id=chat_id,
            username=username if not None and not "None" else ""
        )
        if main_group is not None:
            settings.users[chat_id].main_group = main_group
        if group is not None:
            settings.users[chat_id].groups.append(group)
        if mention_all is not None:
            settings.users[chat_id].mention_all = mention_all
        if allow_preview is not None:
            settings.users[chat_id].allow_preview = allow_preview
        if time_zone is not None:
            settings.users[chat_id].time_zone = time_zone
    else:  # обновление данных по существующему пользователю
        if username != settings.users[chat_id].username and username is not None:
            settings.users[chat_id].username = username
        # # Обновление главной группы происходит по более быстрому пути через прямое обращение к
        # # settings.users[chat_id].main_group, необходимости в данных строчках ниже здесь нет,
        # # т.к. их отсутствие не дает переназначать главную группу для существующих пользователей без их участия
        # if main_group != settings.users[chat_id].main_group and main_group is not None:
        #     settings.users[chat_id].main_group = main_group
        if group not in settings.users[chat_id].groups and group is not None:
            settings.users[chat_id].groups.append(group)
        if mention_all != settings.users[chat_id].mention_all and mention_all is not None:
            settings.users[chat_id].mention_all = mention_all
        if allow_preview != settings.users[chat_id].allow_preview and allow_preview is not None:
            settings.users[chat_id].allow_preview = allow_preview
        if time_zone != settings.users[chat_id].time_zone and time_zone is not None:
            settings.users[chat_id].time_zone = time_zone

    return None


def update_groups_data(chat_id: int, banned_admin_chat_id: int = None, banned_admin_username: str = None,
                       unbanned_admin_chat_id: int = None, unbanned_admin_username: str = None,
                       delete_group: bool = False) -> None | bool:
    """
    Инициализация и обновление объектов-групп и объектов-админов в словаре settings.groups.
    :param chat_id: уникальный идентификатор группы телеграм
    :param banned_admin_chat_id: уникальный идентификатор админа для блокировки доступа к анонсам в данной группе
    :param banned_admin_username: никнейм админа для блокировки доступа к анонсам в данной группе
    :param unbanned_admin_chat_id: уникальный идентификатор админа для разблокировки доступа к анонсам в данной группе
    :param unbanned_admin_username: никнейм админа для разблокировки доступа к анонсам в данной группе
    :param delete_group: флаг для удаления группы
    :return: True в случае успешного бана/разбана, иначе - None
    """

    if chat_id not in settings.groups:
        if delete_group:
            return None
        settings.groups[chat_id] = database.Settings.Group(chat_id=chat_id)
        admins = bot.get_chat_administrators(chat_id)
        for admin in admins:
            update_users_data(
                chat_id=admin.user.id,
                username=admin.user.username,
                main_group=chat_id,
                group=chat_id)
            if admin.status != "creator":
                settings.groups[chat_id].white_list.append(
                    database.Settings.Group.Admin(
                        chat_id=admin.user.id,
                        username=admin.user.username
                    )
                )
        return None
    else:
        i: int = 0
        if delete_group:
            for group in settings.groups:
                if chat_id == group:
                    settings.groups.pop(i)
                    return None
                i += 1
        if banned_admin_chat_id is not None or banned_admin_username is not None:
            for admin in settings.groups[chat_id].white_list:
                if admin.chat_id == banned_admin_chat_id or admin.username == banned_admin_username:
                    settings.groups[chat_id].white_list.pop(i)
                    return True
                i += 1
        elif unbanned_admin_chat_id is not None or unbanned_admin_username is not None:
            admins = bot.get_chat_administrators(chat_id)
            for admin in admins:
                update_users_data(
                    chat_id=admin.user.id,
                    username=admin.user.username,
                    main_group=chat_id,
                    group=chat_id)
                if admin.status != "creator":
                    if unbanned_admin_chat_id == admin.user.id or unbanned_admin_username == admin.user.username:
                        settings.groups[chat_id].white_list.append(
                            database.Settings.Group.Admin(
                                chat_id=admin.user.id,
                                username=admin.user.username
                            )
                        )
                        return True
        return None


def send_event(to_chat_id: int, text: str, parse_mode: str, sound: bool, from_chat_id: int, event_title: str,
               event_id: str) -> None:
    """
    Функция для отправки анонса получателю, уведомления об отправке отправителю и очистки списка events.delayed.
    :param to_chat_id: chat.id получателя
    :param text: текст анонса
    :param parse_mode: язык разметки для редактирования текста анонса (всегда HTML)
    :param sound: звуковое уведомление при отправке анонса
    :param from_chat_id: chat.id отправителя
    :param event_title: название анонса
    :param event_id: уникальный идентификатор анонса
    """
    try:
        # отправка анонса
        admins = bot.get_chat_administrators(to_chat_id) if to_chat_id < 0 else None
        is_success: bool = False

        if admins is not None:
            for admin in settings.groups[to_chat_id].white_list:
                if admin.chat_id == from_chat_id:
                    msg = bot.send_message(to_chat_id, text, parse_mode,
                                           disable_notification=sound,
                                           disable_web_page_preview=settings.users[from_chat_id].allow_preview)
                    # нужно ли вызывать mention_all
                    if settings.users[from_chat_id].mention_all and not sound:
                        mention_all_command(msg)
                    is_success = True

        if to_chat_id == from_chat_id:
            is_success = True
            msg = bot.send_message(to_chat_id, text, parse_mode,
                                   disable_notification=sound,
                                   disable_web_page_preview=settings.users[from_chat_id].allow_preview)
            if settings.users[from_chat_id].mention_all and not sound:
                mention_all_command(msg)

        # удаление анонса из списка отложенных
        is_repeated: str = "Данный код анонса более недоступен для использования."
        i: int = 0
        for event in events.delayed:
            if event.id.split("__")[2] == event_id:
                if event.id.split("__")[1] == "cron":
                    is_repeated = ""
                else:
                    events.delayed.pop(i)
                    # поиск и удаление превью данного анонса
                    i = 0
                    for previews in events.previews[from_chat_id]:
                        for preview in previews:
                            if event_id == preview:
                                events.previews[from_chat_id].pop(i)
                            i += 1
                    break
            i += 1

        if is_success:  # уведомление отправителю об успешной отправке
            msg = bot.send_message(from_chat_id,
                                   f"<b>Оповещение</b>: анонс <b>{event_title}</b> (код: <code>{event_id}</code>) отправлен "
                                   f"указанн{'ому' if to_chat_id > 0 else 'ым'} "
                                   f"получател{'ю' if to_chat_id > 0 else 'ям'} с заданными настройками. {is_repeated}",
                                   parse_mode="HTML")
            bot.edit_message_reply_markup(from_chat_id, msg.id,
                                          reply_markup=types.InlineKeyboardMarkup().add(
                                              types.InlineKeyboardButton("OK", callback_data=f"system_delete_{msg.id}")
                                          ))
        else:
            msg = bot.send_message(from_chat_id,
                                   f"<b>Ошибка</b>: анонс <b>{event_title}</b> (код: <code>{event_id}</code>) не был отправлен, т.к. "
                                   f"отправитель не является админом в указанной группе или доступ к отправке анонсов ограничен создателем группы. "
                                   f"{is_repeated}"
                                   f"\n\n<b>Ознакомиться со справкой – /help</b>",
                                   parse_mode="HTML")
            bot.edit_message_reply_markup(from_chat_id, msg.id,
                                          reply_markup=types.InlineKeyboardMarkup().add(
                                              types.InlineKeyboardButton("OK", callback_data=f"system_delete_{msg.id}")
                                          ))
        return None

    except Exception as error:
        logger.error(f"Анонс {event_id} не был отправлен получателю {to_chat_id} (отправитель {from_chat_id}):"
                     f"\n{str(error)}")
        return None


# Функция для проверки даты на прошлое время (с возможностью добавить откат в мин. и сек.)
def date_is_in_past(date_time, now_time, delay_min=0, delay_sec=0):
    return True if date_time + timedelta(minutes=delay_min, seconds=delay_sec) <= now_time else False


if __name__ == "__main__":

    scheduler.start()

    while True:
        try:
            logger.info("Бот активен")
            bot.infinity_polling(timeout=60, long_polling_timeout=5)
        except Exception as e:
            logger.critical(f"Бот упал: {str(e)}")
            if len(events.users) != 0:
                events.upload_all()
            if len(settings.users) != 0:
                settings.upload_all_users()
                settings.upload_all_groups()
            continue
