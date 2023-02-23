""" Бот, и команды для бота """
from config import bot_config as config
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id, json
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import psycopg2
import time
from manage import get_ready_to_search as prepare, get_cities, get_user_info, prepare_results
import db

user_token = config['user_token']
group_token = config['group_token']
group_id = config['group_id']

vku_session = vk_api.VkApi(token=user_token, api_version='5.131')
vkg_api = vk_api.VkApi(token=group_token).get_api()

# Лонгполл Бота для перехвата VkBotEventType
bot_longpoll = VkBotLongPoll(vk_api.VkApi(token=group_token), group_id)
# Лонгполл для перехвата VkEventType
longpoll = VkLongPoll(vk_api.VkApi(token=group_token))


""" Бот """
class Bot:

    """ Инициализация """
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
        userdata = get_user_info(user['id'], vku_session.get_api())
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
                                prepare(conn, user, vku_session)
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
        message_send(user, f"""Информация о пользователе: {user['last_name']} {user['first_name']}
Город поиска: {user['city']['title']}
Возраст поиска: от {user['age_from']} до {user['age_to']}""")
        keyboard_send(
            user, "А вот что мы умеем в настройках (список команд):", False)
        message_send(user, f"""- возраст (изменить настройки возраста "ОТ" и "ДО")
- город (изменить или уточнить город поиска)
- очистить (удаляет все результаты прошлых поисков)
Что бы вы хотели изменить?""")
        # - город (изменить город поиска)
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW:
                if event.to_me:
                    command = event.text.lower()
                    if command == 'возраст':
                        user.pop('age_from', None)
                        user.pop('age_to', None)
                        break
                    if command == 'город':
                        user['city'].pop('id', None)
                        user['city'].pop('title', None)
                        user.pop('city', None)
                        break
                    if command == 'очистить':
                        with start_db() as conn:
                            db.del_results(conn, user['id'])
                            message_send(user, 'Список результатов очищен.')
                            prepare(conn, user, vku_session)
                        conn.close()
                        break
                    elif command == 'ничего':
                        break
                    else:
                        message_send(
                            user, 'Извините, ответ не распознан. Если НИЧЕГО менять не нужно, то так и напишите :). Итак, что бы вы хотели изменить?')
        to_supplement = list(
            filter(lambda parametr: parametr not in list(user), self.checklist))
        # при изменении критических параметров поиска нужно перезапустить
        if len(to_supplement) > 0:
            self._supplement_userdata(user, initial=False)
            with start_db() as conn:
                """ 
                1) подготовить/очистить базу временных данных
                2) удалить результаты, что ещё не выдавались
                3) снова подготовить вывод
                """
                db.remove_from_temp(conn, user['id'], profile_id=None)
                db.del_results(conn, user['id'], temp=True)
                prepare(conn, user, vku_session)
            keyboard_send(
                user, 'Готово. Можно попробовать снова подобрать пару 😉')
            conn.close()
        else:
            keyboard_send(user, 'Ок. Настройки поиска остались прежними.')
        return

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
                message_send(user, f"""{person[2]} {url}
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
                prepare_results(conn, user['id'], vku_session)
            else:
                message_send(
                    user, f"Список кандидатов по вашим параметрам пуст, либо все результаты уже у Вас. Попробуйте осуществить поиск по другим параметрам.")

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


""" Отправка клавиатур """
def keyboard_send(user, msg, switch=True) -> None:  # клавиатуры
    settings = dict(one_time=False, inline=False)
    keyboard = VkKeyboard(**settings)
    if switch:
        keyboard.add_callback_button(label='Поиск пары', color=VkKeyboardColor.PRIMARY,
                                     payload={"type": "show_snackbar", "text": "search"})
        keyboard.add_line()
        keyboard.add_callback_button(label='Настройки', color=VkKeyboardColor.PRIMARY,
                                     payload={"type": "show_snackbar", "text": "settings"})
        keyboard.add_callback_button(label='Избранные', color=VkKeyboardColor.PRIMARY,
                                     payload={"type": "show_snackbar", "text": "show_favirits"})
        # Кнопка для остановки бота
        keyboard.add_line()
        keyboard.add_callback_button(label='Остановить сервер', color=VkKeyboardColor.SECONDARY,
                                     payload={"type": "show_snackbar", "text": "stop"})
    attempt = 0
    while True and attempt < 3:  # 3 попытки на успешную отправку клавиатуры, на случай сбоя работы ВК
        try:
            if switch:
                vkg_api.messages.send(user_id=user['id'], title=msg, message='&#13;',  random_id=get_random_id(
                ), keyboard=keyboard.get_keyboard())
            else:
                vkg_api.messages.send(user_id=user['id'], title=msg, message='&#13;',  random_id=get_random_id(
                ), keyboard=keyboard.get_empty_keyboard())
            break
        except:
            attempt += 1
            # надо было логгер изучить, конечно, но не успел.
            print(
                user['id'], f"Ошибка отправки клавиатуры. Повторная попытка №{attempt}.")
            time.sleep(1)


""" Отправка сообщений """
def message_send(user, msg, attachment=None) -> None:  # сообщения
    attempt = 0
    while True and attempt < 3:  # 3 попытки на успешную отправку сообщения, на случай сбоя работы ВК
        try:
            if attachment == None:
                vkg_api.messages.send(
                    user_id=user['id'], message=msg,  random_id=get_random_id())
                break
            else:
                vkg_api.messages.send(
                    user_id=user['id'], message=msg,  random_id=get_random_id(), attachment=attachment)
                break
        except:
            attempt += 1
            # надо было логгер изучить, конечно, но не успел.
            print(
                user['id'], f"Ошибка отправки сообщения. Повторная попытка №{attempt}.")
            time.sleep(1)


""" Сессия БД """
def start_db() -> any:  # создаем сессию БД
    return psycopg2.connect(database=config['pgbase'], user="postgres", password=config['pgpwd'])


""" Уточняем имя или фамилию """
def name_sup(item, user, longpoll) -> object:
    new_value = None
    while new_value is None:
        if item == 'first_name':
            name_type = 'своё имя'
        else:
            name_type = 'фамилию'
        message_send(user, f"уточните {name_type}: ")
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW:
                if event.to_me:
                    new_value = event.text.capitalize()
                    break
    new_value = {item: new_value}
    return new_value


""" Уточняем город """
def city_sup(item, user, longpoll) -> object:
    new_value = None
    while new_value is None:
        message_send(
            user, 'уточните название города, или его ID (если знаете): ')
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW:
                if event.to_me:
                    try:
                        cities = get_cities(
                            vku_session.get_api(), event.text.lower())
                        if len(cities) > 1:
                            message_send(user, 'Вот несколько подходящих городов:')
                            for city in cities[0:5]:
                                try:
                                    message_send(
                                        user, f"(ID={city['id']}). {city['title']} ({city['region']}, {city['area']})")
                                except:
                                    message_send(
                                        user, f"(ID={city['id']}). {city['title']}")
                            city = cities
                            message_send(user,
                            """Пока мы автоматически выбрали наиболее подходящий вариант.
                            Чтобы выбрать точнее - повторите поиск, но укажите уже ID.""")
                        else:
                            city = cities
                        new_value = {
                            'id': city[0]['id'], 'title': city[0]['title']}
                        message_send(
                            user, f"В настройки поиска сохранён город: (ID={city[0]['id']}) {city[0]['title']}")
                    except:
                        message_send(
                            user, 'Мы не нашли такого города. Попробуйте изменить запрос или поиск по ID.')
                    finally:
                        break
    new_value = {item: new_value}
    return new_value


""" Уточняем тип отношений """
def rel_sup(item, user, longpoll) -> object:
    new_value = None
    while new_value is None:
        message_send(user, 
            f"""уточните тип отношений:
            (для справки. введите соответствующую цифру
            1 — не женат (не замужем),
            2 — встречаюсь,
            3 — помолвлен(-а),
            4 — женат (замужем),
            5 — всё сложно,
            6 — в активном поиске,
            7 — влюблен(-а),
            8 — в гражданском браке)""")
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW:
                if event.to_me:
                    try:
                        new_value = int(event.text)
                        if new_value not in range(0, 9):
                            message_send(
                                user, 'Вы ввели недопустимые символы. Смотрите подсказку.')
                            new_value = None
                    except:
                        message_send(
                            user, 'Вы ввели недопустимые символы. Смотрите подсказку.')
                    finally:
                        break
    new_value = {item: new_value}
    return new_value


""" Уточняем принадлежность к полу """
def sex_sup(item, user, longpoll) -> object:
    new_value = None
    while new_value is None:
        message_send(user, "уточните пол (введите М или Ж): ")
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW:
                if event.to_me:
                    new_value = event.text.lower()
                    break
        if new_value in ('м', 'ж'):
            if new_value == 'м':
                new_value = 2
            elif new_value == 'ж':
                new_value = 1
        else:
            message_send(user, 'Вы ввели недопустимые символы.')
            new_value = None
    new_value = {item: new_value}
    return new_value


""" Уточняем возраст поиска """
def age_sup(item, user, longpoll) -> object:
    new_value = None
    while new_value is None:
        if item == 'age_from':
            age_type = 'ОТ'
        else:
            age_type = 'ДО'
        message_send(user, f'укажите "{age_type}" какого возраста ищем пару: ')
        for event in longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW:
                if event.to_me:
                    try:
                        new_value = int(event.text)
                    except:
                        message_send(
                            user, 'Вы ввели недопустимые символы. Можно вводить только цифры')
                    finally:
                        break
    new_value = {item: new_value}
    return new_value


""" Словарик для уточнений """
supplement_dict = {
    'city': city_sup,
    'relation': rel_sup,
    'sex': sex_sup,
    'first_name': name_sup,
    'last_name': name_sup,
    'age_from': age_sup,
    'age_to': age_sup,
}
