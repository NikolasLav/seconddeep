# модуль взаимодействия с ВК
import db # модуль /работы с БД
import vk_api
import datetime
import time
import psycopg2
from config import bot_config as config


from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.utils import get_random_id
from vk_api.bot_longpoll import VkBotLongPoll
from vk_api.bot_longpoll import VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

""" Функции. Описание и состав.
1. Получение списка по предварительному поиску - формирование temp_list
    * разделение выдачи на результаты не более 1000 штук
А   * формирование цикличности запросов, но не более 3 запросов (с результатом по 1000) в секунду
    * передача данных в другой обработчик
2. Конкретизация запросов с учетом:
    * записей в общей базе (минусуем записи не подходящие под критерии)
    * записей выдачи (минусуем итоги из таблицы results)
    на основании этого уже формируем список и отправляем его далее:
3. Выбираем из списка любой профиль с открытыми фото
    * пробегаемся по всем фото, высчитывая рейтинг
    * разделение выдачи на результаты не более 1000 штук
А   * формирование цикличности запросов, но не более 3 запросов (с результатом по 1000) в секунду
    * передача данных в другой обработчик
4. Выбираем из результата топ-3 рейтинга
    * отправляем эти фотографии пользователю
    * отправляем ссылку на профиль пользователю
"""

def get_user_info(id, vk): #получение данных о пользователе бота
    try:
        return vk.users.get(user_ids=id, fields=("sex","city","relation", "bdate"))[0]
    except:
        return None


def get_ready_to_search(conn, user, vk): #подготовка к поисковому запросу
    start_time = datetime.datetime.today()
    print('-начало запроса', start_time) #delete
    # db.del_temp_list(conn, user_id)
    quantity = 1000 #максимальная выдача
    profiles = _get_search(conn, vk, user, quantity)
    print(f'-в текущем запросе users.search найдено {len(profiles)} анкеты (из возможных {quantity})') #delete
    return profiles #delete


def _get_search(conn, vk, user, quantity):
    #простой поиск, с ограничением до 1000 результатов в одной выдаче. без пересчёта запросов в секунду (обычно это не требуется, т.к. выдачи мало очень)
    #можно организовать пулл реквест, чтобы сразу до 3000 в одной выдаче получать.
    #добавить опцию дополнительного отсева? проверка города.
    profiles = []
    result = []
    if user['sex'] == 1:
        sex = 2
    elif user['sex'] == 2:
        sex = 1
    else:
        sex = 0
    quantity = 1000 #максимальное кол-во выдаваемых профилей.
    check_results = db.get_results(conn, user_id=user['id']) #проверяем выдавался ли уже результат?
    print('-check_results', check_results)
    for age in range(user['age_from'],user['age_to']+1):
        request = vk.users.search(count=quantity, city_id=user['city']['id'], sex=sex, age_from=age, age_to=age, fields=("bdate", "city", "relation"))
        print(age)
        profiles += request['items']
        print(len(profiles))
        for profile in profiles:
            try:
                if profile['id'] not in check_results:
                    if profile['city']['id'] == user['city']['id']:
                        profile.pop('track_code')
                        profile.pop('can_access_closed')
                        profile.pop('is_closed')
                        result += [profile]
            except:
                pass
    return result


def _get_top3_photos(vk, profile):
    print(profile)
    try:
        photos = vk.photos.get(owner_id=profile['id'], album_id="profile", rev=1, extended=1)
        photos = photos['items']
        if len(photos) < 3: #По условию три фото, значит берем только те, в которых три фото) //Гежин Олег
            return None #анкета нам не подходит
        i = 0
        result = []
        for photo in photos:
            likes = photo['likes']['count']
            comments = photo['comments']['count']
            rate = likes + comments
            result += [[rate, photo['id']]]
        result.sort(reverse=True) #сортируем полученный список по убыванию суммы лайков и 
        photos = [] #нужен ещё один массив
        result = result[0:3]  #обрезаем до 3х фотографий
        for photo in result:
            photos += [photo[1]]
        name = f"{profile['first_name']} {profile['last_name']}"
        person = {'id': profile['id'], 'name': name}
        return [person, *photos]
    except:
        print('следущий except')
        return None #анкета нам не подходит (скорее всего это закрытая анкета)


def get_top3_photo(conn, profiles, vk, user_id):
    for profile in profiles:
        person = _get_top3_photos(vk, profile)
        db.remove_from_temp(conn, user_id, profile['id'])
        if person == None:
            pass
        else:
            return person
    
    # print(check_profile)
    # with vk_api.VkRequestsPool(vk_session) as pool:
    #     for user in user_list:
    #         #добавляем в пулл запрос фото
    #         pass
    # #добавляем в кортеж userlist ссылку на профиль и фотографию.
    # return user_list
    pass


def _try_get_photos_from_db(conn, profile_id):
    try:
        db.get_photos(conn, profile_id)
    except:
        pass



# user_token = config['user_token']
# group_token = config['group_token']
# group_id = config['group_id']

# vk_session = vk_api.VkApi(token=user_token, api_version='5.131')
# vk = vk_session.get_api() #сессия ВК
# # lis = _get_top3_photos(vk_session, 31687273)
# # print(lis)
# # get_top3_photo(conn, 0)

# with psycopg2.connect(database=config['pgbase'], user="postgres", password=config['pgpwd']) as conn:
#     get_ready_to_search(conn, vk_session, 31687273)
#     pass


#442068022 м
#615273465 полигон
#185512524 b
#31687273 я
