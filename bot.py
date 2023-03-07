""" Бот, и команды для бота """
from config import bot_config as config
import vk_api
from vk_api.utils import json
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
import psycopg2
from manage import get_ready_to_search as prepare, get_user_info, prepare_results, message_send, keyboard_send, change_settings, Supplement
import db


group_token = config['group_token']
group_id = config['group_id']
vkg_api = vk_api.VkApi(token=group_token).get_api()
bot_longpoll = VkBotLongPoll(vk_api.VkApi(token=group_token), group_id)


""" Бот """
class Bot:

    def __init__(self) -> None:
        # минимальный комплект для полноты анкеты пользователя
        self.checklist = ['id', 'city', 'relation', 'sex', 'first_name', 'last_name',
                          'age_from', 'age_to']
        # многопользовательский режим - работает вроде :)
        self.users = {}

    """ Проверка сессии БД """
    def _check_db(self, user) -> any:
        try:
            with start_db() as conn:
                # Проверяем работает ли БД, есть ли нужные таблицы
                check = db.db_check(conn)
                if check == 'error':
                    message_send(
                        user, "⛔ Что-то не так с базой. Проверьте настройки бота")
                # возвращает значение 'check' если база готова к работе
                elif check == 'check':
                    message_send(user, "✅ Базаданных готова к работе.")
                elif check == 'empty':
                    message_send(user, "❗ Подготавливаем таблицы...")
                    try:
                        db.create_db(conn)
                        message_send(user, "✅ Базаданных готова к работе.")
                    except:
                        message_send(user, "⛔ Что-то пошло не так.")
        except:
            check == 'error'
            message_send(
                user, "⛔ Что-то не так с базой. Проверьте настройки бота")
        return check

    """ Инициализируем пользователя """
    def _initial(self, user) -> None:
        userdata = get_user_info(user['id'])
        if userdata is None:
            message_send(
                user, '⛔ Проблемы инициализации пользователя. Проверьте настроки access_token пользователя.')
        else:
            user.update(userdata)
            user.pop('is_closed')
            user.pop('can_access_closed')
            userdata_check = True
            # дополняем недостающую информацию в цикле
            while userdata_check:
                userdata_check, user = self._supplement_userdata(user)

    """ Запрашиваем уточнения, если данных из профиля нехватает """
    def _supplement_userdata(self, user, initial=True) -> tuple[bool, any]:
        need_to_supplement = True
        if initial:
            msg = "Для начала работы не хватает данных. Пожалуйста,"
        else:
            msg = "Давайте изменим данные. Пожалуйста,"
        while need_to_supplement:
            to_supplement = list(
                filter(lambda parametr: parametr not in list(user), self.checklist))
            if ('age_from' not in to_supplement) and ('age_to' not in to_supplement):
                try:
                    if user['age_from'] > user['age_to']:
                        user['age_from'] = None
                        user['age_to'] = None
                        message_send(
                            user, 'Возраст "ДО" должен быть не меньше возраста "ОТ".')
                        to_supplement += ['age_from', 'age_to']
                except:
                    pass
            if len(to_supplement) > 0:
                message_send(user, msg)
                msg = 'Вы где-то ошиблись... Давайте повторим. Сердечно прошу Вас быть внимательнее :). Пожалуйста,'
                for item in to_supplement:
                    user.update(supplement_dict[item](item,user))
            else:
                need_to_supplement = False
        return need_to_supplement, user

    """ активация "слушателей" """
    def activate(self) -> None:
        for event in bot_longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_EVENT:  # действия при нажатии кнопки
                # Генерируем ответ на ивент нажатия кнопки
                event_id = event.object.event_id,
                user_id = event.object.user_id,
                peer_id = event.object.user_id,
                func = event.object.payload['text']
                event.object.payload['text'] = self.ex[func]['description']
                event_data = json.dumps(event.object.payload)
                # Отправляем ответ, иначе callback кнопка будет работать с ошибкой.
                vkg_api.messages.sendMessageEventAnswer(
                    event_id=event_id,
                    user_id=user_id,
                    peer_id=peer_id,
                    event_data=event_data)
                if func in self.ex:
                    user = self.users.setdefault(list(user_id)[0], dict())
                    self.ex[func]['func'](self, user)
                # колхозная остановка бота (работает, если активна кнопка в клавиатуре ниже)
                if func == 'stop':
                    break
            if event.type == VkBotEventType.MESSAGE_TYPING_STATE:
                # исключить реакцию на сообщения отправляемых от имени сообщества
                if event.obj['from_id'] != -group_id:
                    user = self.users.setdefault(event.obj['from_id'], dict())
                    value = {'id': event.obj['from_id']}
                    if len(user) == 0:  # добавляем пользователя, если в текущей сессии бота он впервые
                        user.update(value)
                        keyboard_send(user, "Добро пожаловать!", switch=False)
                        checkbd = self._check_db(user)
                        if checkbd != 'error':
                            self._initial(user)
                            keyboard_send(
                                user, "Приложение для поиска пары V_К_i_n_d_е_r готово к работе!")
                            message_send(user,
                                         '✅ Можете изменить параметры поиска в "Настройках".')
                            with start_db() as conn:
                                prepare(conn, user)
            # Поставить лайк = добавить в избранное
            if event.type == 'like_add':
                try:
                    db.update_results(
                        conn, profile_id=user['last_search'], user_id=event.object['liker_id'], favorite=True)
                except:
                    pass
            if event.type == 'like_remove':
                try:
                    db.update_results(
                        conn, profile_id=user['last_search'], user_id=event.object['liker_id'], favorite=False)
                except:
                    pass

    """ остановка бота """
    def stop(self, user) -> None:
        with start_db() as conn:
            try:
                # очистка временной таблицы
                db.remove_from_temp(conn, user['id'], profile_id=None)
                # очистка подготовленных, но не показанных результатов
                db.del_results(conn, user['id'], temp=True)
            except:
                pass
        keyboard_send(user, "⛔ Бот остановлен. Заходите ещё! 🤗", switch=False)

    """ настройки поиска """
    def settings(self, user) -> None:
        with start_db() as conn:
            message_send(user, f"""Информация о пользователе: {user['last_name']} {user['first_name']}
    Город поиска: {user['city']['title']}
    Возраст поиска: от {user['age_from']} до {user['age_to']}""")
            keyboard_send(
                user, "А вот что мы умеем в настройках (список команд):", False)
            message_send(user, """- возраст (изменить настройки возраста "ОТ" и "ДО")
    - город (изменить или уточнить город поиска)
    - очистить (удаляет все результаты прошлых поисков)
    Что бы вы хотели изменить?""")
            user = change_settings(conn, user)
            to_supplement = list(
                filter(lambda parametr: parametr not in list(user), self.checklist))
            # при изменении критических параметров поиска нужно перезапустить
            if len(to_supplement) > 0:
                self._supplement_userdata(user, initial=False)
                """ 
                1) подготовить/очистить базу временных данных
                2) удалить результаты, что ещё не выдавались
                3) снова подготовить вывод
                """
                db.remove_from_temp(conn, user['id'], profile_id=None)
                db.del_results(conn, user['id'], temp=True)
                prepare(conn, user)
                keyboard_send(
                    user, 'Готово. Можно попробовать снова подобрать пару 😉')
            else:
                keyboard_send(user, 'Ок. Настройки поиска остались прежними.')

    """ Вывод результата на экран пользователя """
    def search(self, user) -> None:
        message_send(user, "Секундочку...")
        with start_db() as conn:
            person = db.get_results(conn, user_id=user['id'], not_seen=True)
            if (person is not None) and (len(person) > 0):
                id = person[1]
                user.update({'last_search': id})
                photos = person[3].split(',')
                attachment = f'photo{id}_'+f',photo{id}_'.join(photos)
                url = "http://vk.com/id"+str(id)
                message_send(user, 
                f"""{person[2]} {url}
                Чтобы добавить в ИЗБРАННОЕ оставьте ❤ лайк на любой фотографии (доступно только для текущего результата поиска).
                """, attachment)
                if person[4] is None or person[4] == '':
                    pass
                else:
                    marked = person[4].split(',')
                    favorite_attachments = []
                    urls = []
                    for item in range(0, len(marked), 2):
                        attachment = f'photo{marked[item]}_{marked[item+1]}'
                        favorite_attachments.append(attachment)
                        urls.append("http://vk.com/"+attachment)
                    urls = ('\n').join(urls)
                    message_send(user, f"""Фотографии с отметками:
                    (в виде фото отображаются только те, что доступны боту;
                    по ссылкам можете перейти на оригинал.)
                    {urls}""", (',').join(favorite_attachments))
                # записать выдачу
                db.update_results(
                    conn, profile_id=person[1], user_id=user['id'], seen=True)
                # подготовить новую, пока пользователь оценивает выдачу
                prepare_results(conn, user['id'])
            else:
                message_send(
                    user, "Список кандидатов по вашим параметрам пуст, либо все результаты уже у Вас. Попробуйте осуществить поиск по другим параметрам.")

    """ Вывод списка ИЗБРАННЫХ """
    def show_favorite(self, user) -> None:
        message_send(user, "Список ИЗБРАННЫХ анкет")
        persons = ''
        with start_db() as conn:
            favorite_profiles = db.get_results(
                conn, user_id=user['id'], favorite=True)
            if len(favorite_profiles) > 0:
                for favorite in favorite_profiles:
                    persons += favorite[2] + \
                        " http://vk.com/id"+str(favorite[1])+'\n'
                message_send(user, persons)
            else:
                message_send(user, "Пока ещё пуст.")

    """ Словарь callback-функций (реакция на кнопки) """
    ex = {
        'stop': {'func': stop, 'description': 'Останавливаем бота'},
        'settings': {'func': settings, 'description': 'Меняем настройки пользователя'},
        'search': {'func': search, 'description': 'Пробуем сделать поиск...'},
        'show_favirits': {'func': show_favorite, 'description': 'Открываем список избранных'}
    }


""" Сессия БД """
def start_db() -> any:  # создаем сессию БД
    return psycopg2.connect(database=config['pgbase'], user="postgres", password=config['pgpwd'])


""" Словарик для уточнений """
us = Supplement #user supplement
supplement_dict = {
    'city': us.city,
    'relation': us.rel,
    'sex': us.sex,
    'first_name': us.name,
    'last_name': us.name,
    'age_from': us.age,
    'age_to': us.age
}
