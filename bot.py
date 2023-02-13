# Команды для бота
import manage
import db
from config import bot_config as config
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id, json
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import psycopg2
import datetime
import time

user_token = config['user_token']
group_token = config['group_token']
group_id = config['group_id']
vku_session = vk_api.VkApi(token=user_token, api_version='5.131') #нужен для VkPoolRequest
vku_api = vku_session.get_api() #API с токеном пользователя, для методов "ключом доступа пользователя".
vkg_api = vk_api.VkApi(token=group_token).get_api() #API с токеном группы, для методов "ключом доступа группы".
bot_longpoll = VkBotLongPoll(vk_api.VkApi(token=group_token), group_id) #лонгполл Бота для перехвата VkBotEventType
longpoll = VkLongPoll(vk_api.VkApi(token=group_token)) #лонгполл для перехвата VkEventType


class Bot:
    def __init__(self):
        self.checklist = ['id', 'city', 'relation', 'sex', 'first_name', 'last_name', 'bdate', 'age_from', 'age_to'] #минимальный комплект для полноты анкеты пользователя
        self.users = {} # пробовал многопользовательский режим - работает вроде :)


    def _check_db(self, user): #проверяем сессию БД
        try:
            conn = start_db() 
            check = db.db_check(conn) #чекаем работает ли БД, есть ли нужные таблицы
            if check == 'error':
                message_send(user, "⛔ Что-то не так с базой. Проверьте настройки бота")
            elif check == 'check':  # возвращает значение 'check' если база готова к работе
                message_send(user, "✅ Базаданных готова к работе.")
            elif check == 'empty':
                message_send(user, "❗ Подготавливаем таблицы...")
                try:
                    db.create_db(conn)
                    message_send(user, "✅ Базаданных готова к работе.")
                except:
                    message_send(user, "⛔ Что-то пошло не так.")
            conn.close()
        except:
            check == 'error'
            message_send(user, "⛔ Что-то не так с базой. Проверьте настройки бота")
        return check


    def initial(self, user): # берем данные пользователя
        userdata = manage.get_user_info(user['id'], vku_api)
        if userdata == None:
            message_send(user, '⛔ Проблемы инициализации пользователя. Проверьте настроки access_token пользователя.')
        else:
            user.update(userdata)
            user.pop('is_closed')
            user.pop('can_access_closed')
            userdata_check = True
            while userdata_check: # дополняем недостающую информацию
                userdata_check, user= self.supplement_userdata(user)


    def _supplement(self, items, obj): # подпрограмма для ввода и обработки/проверки уточнений
        for item in items:
            new_value = None
            if item == 'first_name':
                message_send(obj, "уточните имя: ")
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            new_value = event.text.capitalize()
                            break
            elif item == 'last_name':
                message_send(obj, "уточните фамилию: ")
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            new_value = event.text.capitalize()
                            break
            elif item == 'city':
                message_send(obj, 'уточните название города, или его ID (если знаете): ')
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            try:
                                cities = manage.get_cities(vku_api, event.text.lower())
                                if len(cities) > 1:
                                    message_send(obj, 'Вот несколько подходящих городов:')
                                    for city in cities[0:5]:
                                        try:
                                            message_send(obj, f"(ID={city['id']}). {city['title']} ({city['region']}, {city['area']})")
                                        except:
                                            message_send(obj, f"(ID={city['id']}). {city['title']}")
                                    city = cities
                                    message_send(obj, f"""Пока мы автоматически выбрали наиболее подходящий вариант.
                                    Чтобы выбрать точнее - повторите поиск, но укажите уже ID.""")
                                else:
                                    city = cities
                                new_value = {'id': city[0]['id'], 'title': city[0]['title']}
                                message_send(obj, f"В настройки поиска сохранён город: (ID={city[0]['id']}) {city[0]['title']}")
                            except:
                                message_send(obj, 'Мы не нашли такого города. Попробуйте изменить запрос или поиск по ID.')
                            finally:
                                break
            elif item == 'relation':
                message_send(obj, f"""уточните тип отношений:
                                            (для справки. введите соответствующую цифру
                                            1 — не женат (не замужем),
                                            2 — встречаюсь,
                                            3 — помолвлен(-а),
                                            4 — женат (замужем),
                                            5 — всё сложно,
                                            6 — в активном поиске,
                                            7 — влюблен(-а),
                                            8 — в гражданском браке.): """)
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            try:
                                new_value = int(event.text)
                                if new_value not in range(0, 9):
                                    message_send(obj, 'Вы ввели недопустимые символы. Смотрите подсказку.')
                                    new_value = None
                            except:
                                message_send(obj, 'Вы ввели недопустимые символы. Смотрите подсказку.')
                            finally:
                                break       
            elif item == 'sex':
                message_send(obj, "уточните пол (введите М или Ж): ")
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
                    message_send(obj, 'Вы ввели недопустимые символы.')
                    new_value = None
            elif item == 'bdate':
                message_send(obj, 'уточните дату рождения в формате "ДД.ММ.ГГГГ": ')
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            try:
                                new_value = datetime.datetime.strptime(event.text, '%d.%m.%Y').date()
                            except:
                                message_send(obj, 'Вы ввели недопустимые символы. Следуйте подсказке.')
                            finally:
                                break
            elif item == 'age_from':
                message_send(obj, 'укажите "ОТ" какого возраста ищем пару: ')
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            try:
                                new_value = int(event.text)
                            except:
                                message_send(obj, 'Вы ввели недопустимые символы. Можно вводить только цифры')
                            finally:
                                break
            elif item == 'age_to':
                message_send(obj, 'укажите "ДО" какого возраста ищем пару: ')
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            try:
                                new_value = int(event.text)
                            except:
                                message_send(obj, 'Вы ввели недопустимые символы. Можно вводить только цифры')
                            finally:
                                break
            if new_value != None:
                new_value = {item : new_value}
                obj.update(new_value)


    def supplement_userdata(self, user, initial=True): #запрашиваем уточнения, если данных из профиля нехватает
        need_to_supplement = True
        if initial:
            msg = "Для начала работы не хватает данных. Пожалуйста,"
        else:
            msg = "Хорошо, изменим данные:"
        while need_to_supplement:
            to_supplement = list(filter(lambda parametr: parametr not in list(user), self.checklist))
            if ('age_from' not in to_supplement) and ('age_to' not in to_supplement):
                try:
                    if user['age_from'] > user['age_to']:
                        user['age_from'] = None
                        user['age_to'] = None
                        message_send(user, 'Возраст "ДО" должен быть не меньше возраста "ОТ".')
                        to_supplement += ['age_from', 'age_to']
                except:
                    pass
            if len(to_supplement) > 0:
                message_send(user, msg)
                msg = 'Вы где-то ошиблись... Давайте повторим. Сердечно прошу Вас быть внимательнее :). Пожалуйста,'
                self._supplement(to_supplement, user)
            else:
                need_to_supplement = False
        return need_to_supplement, user

    #активация "слушателей"
    def activate(self):
        for event in bot_longpoll.listen():
            if event.type == VkBotEventType.MESSAGE_EVENT: #действия при нажатии кнопки
                event_id = event.object.event_id, #генерируем ответ на ивент нажатия кнопки
                user_id = event.object.user_id,
                peer_id = event.object.user_id,
                func = event.object.payload['text']
                event.object.payload['text'] = self.ex[func]['description']
                event_data = json.dumps(event.object.payload)
                result = vkg_api.messages.sendMessageEventAnswer( # отправляем его, иначе callback кнопка будет работать с ошибкой.
                    event_id=event_id,
                    user_id=user_id,
                    peer_id=peer_id,
                    event_data=event_data)
                if func in self.ex:
                    user = self.users.setdefault(list(user_id)[0], dict())
                    self.ex[func]['func'](self, user)
                if func == 'stop':  # колхозная остановка бота (работает только если активна кнопка в клавиатуре ниже)
                    break
            if event.type == VkBotEventType.MESSAGE_TYPING_STATE:
                if event.obj['from_id'] != -group_id: # исключить реакцию на сообщения отправляемых от имени сообщества
                    user = self.users.setdefault(event.obj['from_id'], dict())
                    value = {'id': event.obj['from_id']}
                    if len(user) == 0: # добавляем пользователя, если в текущей сессии бота он впервые
                        user.update(value)
                        keyboard_send(user, "Добро пожаловать!", switch=False)
                        checkbd = self._check_db(user)
                        if checkbd != 'error':
                            self.initial(user)
                            keyboard_send(user, "Приложение для поиска пары V_К_i_n_d_е_r готово к работе!")
                            message_send(user,
                             '✅ Можете изменить параметры поиска в "Настройках".')
                            with start_db() as conn:
                                manage.get_ready_to_search(conn, user, vku_api)
                                manage.prepare_results(conn, user['id'], vku_session)
            if event.type == 'like_add':
                try:
                    db.update_results(conn, profile_id=user['last_search'], user_id=event.object['liker_id'], favorite=True)
                except:
                    pass
            if event.type == 'like_remove':
                try:
                    db.update_results(conn, profile_id=user['last_search'], user_id=event.object['liker_id'], favorite=False)
                except:
                    pass


    def stop(self, user):  # закрываем сессию подключения к БД
        with start_db() as conn:
          try:
              db.clear_temp(conn, user['id']) #очистка временной таблицы
              db.del_results(conn, user['id'], temp=True) #очистка подготовленных, но не показанных результатов
          except:
              pass
        keyboard_send(user, "⛔ Бот остановлен. Заходите ещё! 🤗", switch=False)


    def settings(self, user):  # установка настроек поиска
        message_send(user, f"""Информация о пользователе: {user['last_name']} {user['first_name']}
        Город поиска: {user['city']['title']}
        Возраст поиска: от {user['age_from']} до {user['age_to']}""")
        keyboard_send(user, "А вот что мы умеем в настройках (список команд):", False)
        message_send(user, f"""- возраст (изменить настройки возраста "ОТ" и "ДО")
        - город (изменить или уточнить город поиска)
        - очистить (удаляет все результаты прошлых поисков)
        Что бы вы хотели изменить?""")
        #- город (изменить город поиска)
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
                            manage.get_ready_to_search(conn, user, vku_api)
                            manage.prepare_results(conn, user['id'], vku_session)
                        conn.close()
                        break
                    elif command == 'ничего':
                        break
                    else:
                        message_send(user, 'Извините, ответ не распознан. Если ничего менять не нужно, то так и напишите :). Итак, что бы вы хотели изменить?')
        to_supplement = list(filter(lambda parametr: parametr not in list(user), self.checklist))
        if len(to_supplement) > 0:
            self.supplement_userdata(user, initial=False)
            with start_db() as conn:
                db.clear_temp(conn, user['id'])
                db.del_results(conn, user['id'], temp=True)
                manage.get_ready_to_search(conn, user, vku_api)
                manage.prepare_results(conn, user['id'], vku_session)
            keyboard_send(user, 'Готово. Можно попробовать снова подобрать пару 😉')
            conn.close()
        else:
            keyboard_send(user, 'Ок. Настройки поиска остались прежними.')
        # blacklist
        return


    def search(self, user): # вывод результата на экран пользователя
        message_send(user, "Секундочку...")
        with start_db() as conn:
            person = db.get_results(conn, user_id=user['id'], not_seen=True)
            if (person != None) and (len(person) > 0):
                id = person[1]
                user.update({'last_search': id})
                photos = person[3].split(',')
                attachment = f'photo{id}_'+f',photo{id}_'.join(photos)
                url = "http://vk.com/id"+str(id)
                message_send(user, f"""{person[2]} {url}
                Чтобы добавить в ИЗБРАННОЕ оставьте ❤ лайк на любой фотографии (доступно только для текущего результата поиска).
                """, attachment)
                if person[4] == None or person[4] == '':
                    pass
                else:
                    marked = person[4].split(',')
                    attachments = []
                    urls = []
                    for item in range(0, len(marked), 2):
                        attachment = f'photo{marked[item]}_{marked[item+1]}'
                        attachments += [attachment]
                        urls += ["http://vk.com/"+attachment]
                    urls = ('\n').join(urls)
                    message_send(user, f"""Фотографии с отметками:
                    (в виде фото отображаются только те, что доступны боту;
                    по ссылкам можете перейти на оригинал.)
                    {urls}""", (',').join(attachments))

                # подготовка новой пачки, пока пользователь просматривает результат.
                db.update_results(conn, profile_id=person[1], user_id=user['id'], seen=True)
                manage.prepare_results(conn, user['id'], vku_session)
            else:
                message_send(user, f"Список кандидатов по вашим параметрам пуст, либо все результаты уже у Вас. Попробуйте осуществить поиск по другим параметрам.")


    def show_favorite(self, user):
        message_send(user, "Список ИЗБРАННЫХ анкет")
        persons = ''
        with start_db() as conn:
            favorite_profiles = db.get_results(conn, user_id=user['id'], favorite=True)
            if len(favorite_profiles) > 0:
                for favorite in favorite_profiles:
                    persons += favorite[2]+" http://vk.com/id"+str(favorite[1])+'\n'
                message_send(user, persons)
            else:
                message_send(user, "Пока ещё пуст.")


    ex = { #cловарь функций
        'stop': {'func': stop, 'description': 'Останавливаем бота'},
        'settings': {'func': settings, 'description': 'Меняем настройки пользователя'},
        'search': {'func': search, 'description': 'Пробуем сделать поиск...'},
        'show_favirits': {'func': show_favorite, 'description': 'Открываем список избранных'}
        }


def keyboard_send(user, msg, switch=True): # клавиатуры
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
        # # Кнопка для остановки бота
        # keyboard.add_line()
        # keyboard.add_callback_button(label='Остановить сервер', color=VkKeyboardColor.SECONDARY,
        #                             payload={"type": "show_snackbar", "text": "stop"})
    attempt = 0
    while True and attempt < 3: # 3 попытки на успешную отправку клавиатуры, на случай сбоя работы ВК
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
            print(user['id'], f"Ошибка отправки клавиатуры. Повторная попытка №{attempt}.") # надо было логгер изучить, конечно, но не успел.
            time.sleep(1)


def message_send(user, msg, attachment=None): # сообщения
    attempt = 0
    while True and attempt < 3: # 3 попытки на успешную отправку сообщения, на случай сбоя работы ВК
        try:
            if attachment == None:
                vkg_api.messages.send(user_id=user['id'], message=msg,  random_id=get_random_id())
                break
            else:
                vkg_api.messages.send(user_id=user['id'], message=msg,  random_id=get_random_id(), attachment=attachment)
                break
        except:
            attempt += 1
            print(user['id'], f"Ошибка отправки сообщения. Повторная попытка №{attempt}.") # надо было логгер изучить, конечно, но не успел.
            time.sleep(1)


def start_db(): # создаем сессию БД
        return psycopg2.connect(database=config['pgbase'], user="postgres", password=config['pgpwd'])