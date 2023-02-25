""" Модуль взаимодействия с ВК, и прочих вспомогательных функций """
from config import bot_config as config
import vk_api
from vk_api import VkRequestsPool
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor
from vk_api.utils import get_random_id
from db import add_results, get_results, get_profiles, make_temp_list, del_results
import time


user_token = config['user_token']
group_token = config['group_token']
longpoll = VkLongPoll(vk_api.VkApi(token=group_token))
vk_session = vk_api.VkApi(token=user_token, api_version='5.131')
vku_api = vk_session.get_api()
vkg_api = vk_api.VkApi(token=group_token).get_api()


""" Получение данных о пользователе бота """
def get_user_info(id: int) -> (dict | None):
    try:
        return vku_api.users.get(user_ids=id, fields=("sex", "city", "relation"))[0]
    except:
        return None


""" Агрегация функций подготовки к поисковому запросу """
def get_ready_to_search(conn: object, user: dict) -> None:
    result = []
    if user['sex'] == 1:
        sex = 2
    elif user['sex'] == 2:
        sex = 1
    else:
        sex = 0
    quantity = 1000
    check_results = get_results(conn, user_id=user['id'])
    request = vku_api.users.search(
        count=quantity,
        city_id=user['city']['id'],
        sex=sex,
        age_from=user['age_from'],
        age_to=user['age_to'],
        fields=("city", "relation"))
    profiles = request['items']
    for profile in profiles:
        try:
            # есть ли найденный профиль среди прошлых результатов?
            if profile['id'] not in check_results:
                # соответствует ли город поиска?
                if profile['city']['id'] == user['city']['id']:
                    # Выкидываем ненужное, для экономии трафика
                    profile.pop('track_code')
                    profile.pop('can_access_closed')
                    profile.pop('is_closed')
                    result += [profile]
        except:
            pass
    make_temp_list(conn, user['id'], result)
    prepare_results(conn, user['id'])


""" Работа с городами """
def get_cities(query: str) -> any:
    try:
        id = int(query)
        request = vku_api.database.getCitiesById(city_ids=id)
        cities = request
    except:
        request = vku_api.database.getCities(q=query)
        cities = request['items']
    return cities


""" Получаем топ-3 фото профиля или отметок """
def _get_top3(photos: dict, owner_id=False) -> (list | None):
    try:
        photos = photos.result['items']
        # Доступно более 3-х фото для оценки или это отметки
        if len(photos) >= 3 or owner_id:
            result = []
            for photo in photos:
                    rate = photo['likes']['count'] + photo['comments']['count']
                    if owner_id:
                        result += [[rate, photo['owner_id'], photo['id']]]
                    else:
                        result += [[rate, photo['id']]]
            result.sort(reverse=True)
            result = result [0:3]
            photos = []
            if owner_id:
                for _, owner_id, photo in result:
                    photos += [owner_id, photo]
            else:
                for _, photo in result:
                    photos.append(photo)
                    
            return photos
        else:
            return None    
    except:
        return None


""" Оценка профилей """
def rate_profiles(persons) -> list:
    profile_photos = []
    marked_photos = []
    new_persons = []
    with VkRequestsPool(vk_session) as pool:
        for person in persons:
            profile_photos += [pool.method('photos.get', {
                                     "owner_id": person['id'], "album_id":"profile", "rev":1, "extended":1})]
            marked_photos += [pool.method('photos.getUserPhotos',
                                   {"user_id": person['id'], "extended":1})]
    
    for person, photos, marked in zip(persons, profile_photos, marked_photos):
        photos = _get_top3(photos)
        marked = _get_top3(marked, owner_id=True)
        name = f"{person['first_name']} {person['last_name']}"
        person = {'id': person['id'],
                  'name': name, 'profile_photos': photos, 'marked_photos': marked}
    
        new_persons.append(person)
    return new_persons


""" Подготовка для вывода под капотом """
def prepare_results(conn, user_id) -> None:
    person = get_results(conn, user_id=user_id, not_seen=True)
    if person == []:
        while person == []:
            profiles = get_profiles(conn, user_id)
            if len(profiles) > 0:
                profiles = rate_profiles(profiles)
                if len(profiles) > 0:
                    add_results(conn, user_id, profiles)
                    person = get_results(
                        conn, user_id=user_id, not_seen=True)
            elif len(profiles) == 0:
                break


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


""" Вспомогательный класс для реализации запроса недостающийх данных,
или изменения настроек поиска """
class Supplement:
    
    def __init__(self) -> None:
        pass
    
    """ Уточняем имя или фамилию """
    def name(item, user) -> object:
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
    def city(item, user) -> object:
        new_value = None
        while new_value is None:
            message_send(
                user, 'уточните название города, или его ID (если знаете): ')
            for event in longpoll.listen():
                if event.type == VkEventType.MESSAGE_NEW:
                    if event.to_me:
                        try:
                            cities = get_cities(event.text.lower())
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
    def rel(item, user) -> object:
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
    def sex(item, user) -> object:
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
    def age(item, user) -> object:
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


""" Изменяем настройки """
def change_settings(conn, user):
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
                    del_results(conn, user['id'])
                    get_ready_to_search(conn, user)
                    prepare_results(conn, user)
                    message_send(user, 'Список результатов очищен.')
                    break
                elif command == 'ничего':
                    break
                else:
                    message_send(
                        user, 'Извините, ответ не распознан. Если НИЧЕГО менять не нужно, то так и напишите :). Итак, что бы вы хотели изменить?')
    return user
