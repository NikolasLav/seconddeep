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


class Bot:
    def __init__(self, user_token, group_token, group_id):
        self.vk_session = vk_api.VkApi(token=user_token, api_version='5.131') #сессия ВК
        self.vku_api = self.vk_session.get_api() #API с токеном пользователя, для методов "ключом доступа пользователя".
        self.bot_longpoll = VkBotLongPoll(vk_api.VkApi(token=group_token), group_id) #лонгполл Бота для перехвата VkBotEventType
        self.longpoll = VkLongPoll(vk_api.VkApi(token=group_token)) #лонгполл для перехвата VkEventType
        self.vk_api = vk_api.VkApi(token=group_token).get_api() #API с токеном группы, для методов "ключом доступа группы".


    def start_db(self): # создаем сессию БД
        with psycopg2.connect(database=config['pgbase'], user="postgres", password=config['pgpwd']) as conn:
            return conn


    def check_db(self, user): #проверяем сессию БД
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
            print('Из инишиал', user) #delete
            user.pop('is_closed')
            user.pop('can_access_closed')
            userdata_check = True
            while userdata_check:
                userdata_check, user= self.supplement_userdata(user)
                print(userdata_check, user)  #delete
            self.message_send(user, '✅ В "Настройках поиска" можете изменить параметры поиска.')


    def _supplement(self, items, obj):
        longpoll = self.longpoll
        for item in items:
            new_value = None
            if item == 'first_name':
                self.message_send(obj, f"уточните имя: ")
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            new_value = event.text.capitalize()
                            break
            elif item == 'last_name':
                self.message_send(obj, f"уточните фамилию: ")
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            new_value = event.text.capitalize()
                            break
            elif item == 'city':
                    self.message_send(obj, f'уточните id города: ')
                    for event in longpoll.listen():
                        if event.type == VkEventType.MESSAGE_NEW:
                            if event.to_me:
                                try:
                                    city_id = int(event.text)
                                except:
                                    self.message_send(obj, f'Вы ввели недопустимые символы. Можно вводить только цифры')
                                finally:
                                    break
                    new_value = {'id': city_id}
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
                                    self.message_send(obj, f'Вы ввели недопустимые символы. Смотрите подсказку.')
                                    new_value = None
                            except:
                                self.message_send(obj, f'Вы ввели недопустимые символы. Смотрите подсказку.')
                            finally:
                                break       
            elif item == 'sex':
                self.message_send(obj, f"уточните пол (введите М или Ж): ")
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
                    self.message_send(obj, f'Вы ввели недопустимые символы.')
                    new_value = None
            elif item == 'bdate':
                self.message_send(obj, f'уточните дату рождения в формате "ДД.ММ.ГГГГ": ')
                for event in longpoll.listen():
                    if event.type == VkEventType.MESSAGE_NEW:
                        if event.to_me:
                            try:
                                new_value = datetime.datetime.strptime(event.text, '%d.%m.%Y').date()
                            except:
                                self.message_send(obj, f'Вы ввели недопустимые символы. Следуйте подсказке.')
                            finally:
                                break
            
            if new_value != None:
                new_value = {item : new_value}
                obj.update(new_value)
        print(obj)


    def supplement_userdata(self, user): # запрашиваем уточнения, если данных из профиля нехватает
        need_to_supplement = True
        while need_to_supplement:
            checklist = ['id', 'city', 'relation', 'sex', 'first_name', 'last_name', 'bdate']
            to_supplement = list(filter(lambda it: it not in list(user), checklist))
            print('to_supplement:', to_supplement) #delete
            if len(to_supplement) > 0:
                self.message_send(user, f"Не хватает данных для поиска. Пожалуйста,")
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
                user.update(value)
                print('MESSAGE_EVENT:', user) #delete
                if func in self.ex:
                    self.ex[func](self, user)
                if func == 'Останавливаем бота':  # колхозная остановка бота надоело выключать его через Ctrl+C
                    break
            if event.type == VkBotEventType.MESSAGE_TYPING_STATE:
                if just_begin:
                    just_begin = False
                    value = {'id': event.obj['from_id']}
                    user.update(value)
                    print('MESSAGE_TYPING_STATE:', user) #delete
                    checkbd = self.check_db(user)
                    if checkbd != 'error':
                        self.initial(user)
                    self.keyboard_send(user, f"Приложение для поиска пары V-К-i-n-d-е-r готово к работе!")


    def keyboard_send(self, user, msg, switch=True):
        settings = dict(one_time=False, inline=False)
        keyboard = VkKeyboard(**settings)
        if switch:
            keyboard.add_callback_button(label='Поиск пары', color=VkKeyboardColor.PRIMARY,
                                        payload={"type": "show_snackbar", "text": "Ищем пару"})
            keyboard.add_line()
            keyboard.add_callback_button(label='Настройки поиска', color=VkKeyboardColor.PRIMARY,
                                        payload={"type": "show_snackbar", "text": "Открываем настройки"})
            keyboard.add_callback_button(label='Проверка соединения', color=VkKeyboardColor.POSITIVE,
                                        payload={"type": "show_snackbar", "text": "Проверка настроек и подключения"})
            keyboard.add_line()
            keyboard.add_callback_button(label='Остановить сервер', color=VkKeyboardColor.SECONDARY,
                                        payload={"type": "show_snackbar", "text": "Останавливаем бота"})
            self.vk_api.messages.send(user_id=user['id'], message=msg,  random_id=get_random_id(
        ), keyboard=keyboard.get_keyboard())
        else:
            self.vk_api.messages.send(user_id=user['id'], message=msg,  random_id=get_random_id(
        ), keyboard=keyboard.get_empty_keyboard())


    def message_send(self, user, msg):
        self.vk_api.messages.send(
            user_id=user['id'], message=msg,  random_id=get_random_id())


    def stop(self, user):  # закрываем сессию подключения к БД
        # with self.start_db() as conn:
        #   try:
        #       db.del_temp_list(conn, user_id)
        #       print('-очистили темп_лист')
        #   except:
        #       pass
        self.keyboard_send(user, "⛔ Бот остановлен", switch=False)


    def settings(self, user):  # установка настроек поиска
        conn = self.start_db()
        print('Lets manage search settings')
        conn.close()
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
        with self.start_db() as conn:
            string = ''
            # top3 = manage.get_top3(conn, user_id, self.vk_session)
            # for top in top3:
            #     string += f'\n{top}'
            self.message_send(user, f"""✅ Вот такой получился результат:{string}""")
        

    ex = {
        'Проверка настроек и подключения': check_db,
        'Останавливаем бота': stop,
        'Открываем настройки': settings,
        'Ищем пару': search
    }
