# Команды для бота
import manage
import db
from config import bot_config as config
import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api.bot_longpoll import VkBotLongPoll
from vk_api.bot_longpoll import VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
import psycopg2
import json
import datetime
import chardet #необходим для работы приложения с телефона


class Bot:
    def __init__(self, user_token, group_token, group_id):
        self.vk_session = vk_api.VkApi(token=user_token, api_version='5.131') #сессия ВК
        self.vku_api = self.vk_session.get_api() #API с токеном пользователя, для методов "ключом доступа пользователя".
        self.bot_longpoll = VkBotLongPoll(vk_api.VkApi(token=group_token), group_id) #лонгполл Бота для перехвата VkBotEventType
        self.longpoll = VkLongPoll(vk_api.VkApi(token=group_token)) #лонгполл для перехвата VkEventType
        self.vk_api = vk_api.VkApi(token=group_token).get_api() #API с токеном группы, для методов "ключом доступа группы".
        self.checklist = ['id', 'city', 'relation', 'sex', 'first_name', 'last_name', 'bdate', 'age_from', 'age_to'] #минимальный комплект для полноты анкеты пользователя

    def start_db(self): # создаем сессию БД
        with psycopg2.connect(database=config['pgbase'], user="postgres", password=config['pgpwd']) as conn:
            return conn


    def _check_db(self, user): #проверяем сессию БД
        try:
            conn = self.start_db() 
            check = db.db_check(conn) #чекаем работает ли БД, есть ли нужные таблицы
            if check == 'error':
                self.message_send(user, "⛔ Что-то не так с базой. Проверьте настройки бота")
            elif check == 'check':  # возвращает значение 'check' если база готова к работе
                self.message_send(user, "✅ Базаданных готова к работе.")
            elif check == 'empty':
                self.message_send(user, "❗ Подготавливаем таблицы...")
                try:
                    db.create_db(conn)
                    self.message_send(user, "✅ Базаданных готова к работе.")
                except:
                    self.message_send(user, "⛔ Что-то пошло не так.")
            conn.close()
        except:
            check == 'error'
            self.message_send(user, "⛔ Что-то не так с базой. Проверьте настройки бота")
        return check


    def initial(self, user): # берем данные пользователя
        userdata = manage.get_user_info(user['id'], self.vku_api)
        if userdata == None:
            self.message_send(user, '⛔ Проблемы инициализации пользователя. Проверьте настроки access_token пользователя.')
        else:
            user.update(userdata)
            user.pop('is_closed')
            user.pop('can_access_closed')
            userdata_check = True
            while userdata_check:
                userdata_check, user= self.supplement_userdata(user)


    def _supplement(self, items, obj):
        longpoll = self.longpoll
        for item in items:
            new_value = None
            if item == 'first_name':
                self.message_send(obj, "уточните имя: ")
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            new_value = event.text.capitalize()
                            break
            elif item == 'last_name':
                self.message_send(obj, "уточните фамилию: ")
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            new_value = event.text.capitalize()
                            break
            elif item == 'city':
                self.message_send(obj, 'уточните id города: ')
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            try:
                                city_id = int(event.text)
                                new_value = {'id': city_id}
                            except:
                                self.message_send(obj, 'Вы ввели недопустимые символы. Можно вводить только цифры')
                            finally:
                                break                
            elif item == 'relation':
                self.message_send(obj, f"""уточните тип отношений:
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
                                    self.message_send(obj, 'Вы ввели недопустимые символы. Смотрите подсказку.')
                                    new_value = None
                            except:
                                self.message_send(obj, 'Вы ввели недопустимые символы. Смотрите подсказку.')
                            finally:
                                break       
            elif item == 'sex':
                self.message_send(obj, "уточните пол (введите М или Ж): ")
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
                    self.message_send(obj, 'Вы ввели недопустимые символы.')
                    new_value = None
            elif item == 'bdate':
                self.message_send(obj, 'уточните дату рождения в формате "ДД.ММ.ГГГГ": ')
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            try:
                                new_value = datetime.datetime.strptime(event.text, '%d.%m.%Y').date()
                            except:
                                self.message_send(obj, 'Вы ввели недопустимые символы. Следуйте подсказке.')
                            finally:
                                break
            elif item == 'age_from':
                self.message_send(obj, 'укажите "ОТ" какого возраста ищем пару: ')
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            try:
                                new_value = int(event.text)
                            except:
                                self.message_send(obj, 'Вы ввели недопустимые символы. Можно вводить только цифры')
                            finally:
                                break
            elif item == 'age_to':
                self.message_send(obj, 'укажите "ДО" какого возраста ищем пару: ')
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            try:
                                new_value = int(event.text)
                            except:
                                self.message_send(obj, 'Вы ввели недопустимые символы. Можно вводить только цифры')
                            finally:
                                break
            if new_value != None:
                new_value = {item : new_value}
                obj.update(new_value)
        print(obj)


    def supplement_userdata(self, user, initial=True): # запрашиваем уточнения, если данных из профиля нехватает
        need_to_supplement = True
        if initial:
            msg = "Для начала работы не хватает данных. Пожалуйста,"
        else:
            msg = "Хорошо, изменим данные:"
        while need_to_supplement:
            to_supplement = list(filter(lambda parametr: parametr not in list(user), self.checklist))
            if ('age_from' not in to_supplement) and ('age_to' not in to_supplement):
                print("-Сработал if ['age_from', 'age_to'] not in to_supplement")
                try:
                    if user['age_from'] > user['age_to']:
                        user['age_from'] = None
                        user['age_to'] = None
                        self.message_send(user, 'Возраст "ДО" должен быть не меньше возраста "ОТ".')
                        to_supplement += ['age_from', 'age_to']
                except:
                    pass
            print('to_supplement:', to_supplement) #delete
            if len(to_supplement) > 0:
                self.message_send(user, msg)
                msg = 'Вы где-то ошиблись... Давайте повторим. Сердечно прошу Вас быть внимательнее :). Пожалуйста,'
                self._supplement(to_supplement, user)
            else:
                need_to_supplement = False
        return need_to_supplement, user

    #активация "слушателей"
    def activate(self):
        user = dict()
        just_begin = True # для отправки клавиатуры и операций под капотом
        for event in self.bot_longpoll.listen():

            if event.type == VkBotEventType.MESSAGE_EVENT: #действия при нажатии кнопки
                event_id = event.object.event_id,
                user_id = event.object.user_id,
                peer_id = event.object.user_id,
                event_data = json.dumps(event.object.payload)
                func = event.object.payload['text']
                result = self.vk_api.messages.sendMessageEventAnswer(
                    event_id=event_id,
                    user_id=user_id,
                    peer_id=peer_id,
                    event_data=event_data)
                value = {'id': list(user_id)[0]}
                if func in self.ex:
                    self.ex[func](self, user)
                if func == 'Останавливаем бота':  # колхозная остановка бота надоело выключать его через Ctrl+C
                    break
            if event.type == VkBotEventType.MESSAGE_TYPING_STATE:
                if just_begin:
                    just_begin = False
                    value = {'id': event.obj['from_id']}
                    user.update(value)
                    self.keyboard_send(user, "Добро пожаловать!", switch=False)
                    checkbd = self._check_db(user)
                    if checkbd != 'error':
                        self.initial(user)
                        conn = self.start_db()
                        manage.get_ready_to_search(conn, user, self.vku_api)
                        conn.close()
                        self.keyboard_send(user, "Приложение для поиска пары V-К-i-n-d-е-r готово к работе!")
                        self.message_send(user, '✅ Можете изменить параметры поиска в "Настройках".')

    def keyboard_send(self, user, msg, switch=True):
        settings = dict(one_time=False, inline=False)
        keyboard = VkKeyboard(**settings)
        if switch:
            keyboard.add_callback_button(label='Поиск пары', color=VkKeyboardColor.PRIMARY,
                                        payload={"type": "show_snackbar", "text": u"Ищем пару"})
            keyboard.add_line()
            keyboard.add_callback_button(label='Настройки', color=VkKeyboardColor.PRIMARY,
                                        payload={"type": "show_snackbar", "text": u"Открываем настройки"})
            keyboard.add_callback_button(label='Проверка соединения', color=VkKeyboardColor.POSITIVE,
                                        payload={"type": "show_snackbar", "text": u"Проверка настроек и подключения"})
            keyboard.add_line()
            keyboard.add_callback_button(label='Остановить сервер', color=VkKeyboardColor.SECONDARY,
                                        payload={"type": "show_snackbar", "text": "Останавливаем бота"})
            self.vk_api.messages.send(user_id=user['id'], title=msg, message='&#13;',  random_id=get_random_id(
        ), keyboard=keyboard.get_keyboard())
        else:
            self.vk_api.messages.send(user_id=user['id'], title=msg, message='&#13;',  random_id=get_random_id(
        ), keyboard=keyboard.get_empty_keyboard())


    def message_send(self, user, msg, attachment=None):
        if attachment == None:
            self.vk_api.messages.send(user_id=user['id'], message=msg,  random_id=get_random_id())
        else:
            try:
                self.vk_api.messages.send(user_id=user['id'], message=msg,  random_id=get_random_id(), attachment=attachment)
            except:
                self.vk_api.messages.send(user_id=user['id'], message="у нас тут какая-то ошибка...",  random_id=get_random_id())


    def stop(self, user):  # закрываем сессию подключения к БД
        with self.start_db() as conn:
          try:
              db.clear_temp(conn, user['id'])
              print('-очистили темп_лист')
          except:
              pass
        self.keyboard_send(user, "⛔ Бот остановлен. Заходите ещё! 🤗", switch=False)


    def settings(self, user):  # установка настроек поиска
        print('Lets manage search settings')
        self.message_send(user, 'Можно изменить возраст поиска. Что бы вы хотели изменить?')
        for event in self.longpoll.listen():
            if event.type == VkEventType.MESSAGE_NEW:
                if event.to_me:
                    command = event.text.lower()
                    if command == 'возраст':
                        user.pop('age_from', None)
                        user.pop('age_to', None)
                        break
                    elif command == 'ничего':
                        self.message_send(user, 'Ок. Продолжим со старыми настройками.')
                        break
                    else:
                        self.message_send(user, 'Извините, не понял ответ. Если ничего менять не нужно, то так и напишите :). Итак, что бы вы хотели изменить?')
        to_supplement = list(filter(lambda parametr: parametr not in list(user), self.checklist))
        if len(to_supplement) > 0:
            self.supplement_userdata(user, initial=False)
            conn = self.start_db()
            db.clear_temp(conn, user['id'])
            manage.get_ready_to_search(conn, user, self.vku_api)
            self.message_send(user, 'Готово. Можно попробовать снова подобрать пару 😉')
        # изменить "возраст от"
        # изменить "возраст до"
        # изменить весы:
        # город
        # лайки и комменты к фото
        # группы
        # книги
        # общие интересы
        # общие друзья
        # фильмы?
        return


    def search(self, user):
        self.message_send(user, "Секундочку...")
        with self.start_db() as conn:
            person = manage.get_top3_photo(conn, self.vku_api, user['id'])
            if person != None:
                print(person)
                url = person[0]['id']
                attachment = tuple("photo"+str(url)+"_"+str(photo) for photo in person[1:4])
                url = "http://vk.com/id"+str(url)
                self.message_send(user, f"""✅ Оцените:
                {person[0]['name']}
                {url}
                """, attachment)
                db.add_results(conn, user['id'], person)
            else:
                self.message_send(user, f"Список кандидатов по вашим параметрам пуст, либо все результаты уже у Вас. Попробуйте осуществить поиск по другим параметрам.")

    ex = {
        'Проверка настроек и подключения': _check_db,
        'Останавливаем бота': stop,
        'Открываем настройки': settings,
        'Ищем пару': search
    }
