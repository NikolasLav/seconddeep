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


def get_ready_to_search(conn, vk_session, user_id): #подготовка к поисковому запросу
    start_time = datetime.datetime.today()
    print('-начало запроса', start_time) #delete
    vk = vk_session.get_api()
    # db.del_temp_list(conn, user_id)
    quantity = 1000 #максимальная выдача
    repeat_search = True
    while repeat_search:
        profiles = _get_search(vk, user_id, quantity)
        print(f'-в текущем запросе users.search найдено {len(profiles)} анкеты (из возможных {quantity})') #delete
        if len(profiles) == quantity: #если вернулось столько же анкет, сколько в макс. выдаче, значит есть ещё кандидаты. Нужно повторить поиск
            repeat_search = True
        else:
            repeat_search = False
        # db.make_temp_list(conn, user_id, profiles) 
        # items = []
        # req_in_sec = 0
        # start_time = datetime.datetime.today() 
        # print(f'-с учетом настроек отсеяно {len(profiles)} анкеты') #delete


        # for element in range(len(profiles)):
        #     if (element != 0) and (element % 1000 == 0): #execute для фото работает пока и при 1000 запросов одновременно
        #         profile_photos = _get_rate_user(vk_session, items)
        #         db.rate_temp_list(conn, user_id, profile_photos)
        #         req_in_sec += 1
        #         items = [list(profiles)[element][1]]
        #         print(f'-запрос №{req_in_sec} : в запросе {len(profile_photos)} анкет.') #delete
        #         if req_in_sec % 3 == 0:
        #             end_time = datetime.datetime.today()
        #             print('-секунд затрачено на 3 запроса:', (end_time-start_time).seconds) #delete
        #             print('-отсечка', end_time) #delete
        #             while (end_time-start_time).seconds == 0:
        #                 time.sleep(0.1) #возможно не нужна?
        #                 print('--поспим (понять, нужна ли пауза)') #delete
        #                 end_time = datetime.datetime.today()
        #             start_time = datetime.datetime.today()
        #             print('-начало запроса', start_time) #delete
        #     else:
        #         items.append(list(profiles)[element][1])
        # if len(items) != 0: #если что-то осталось для запроса...
        #     profile_photos = _get_rate_user(vk_session, items)
        #     print(f'-запрос №{req_in_sec+1} : в запросе {len(profile_photos)} анкет.') #delete
        #     db.rate_temp_list(conn, 31687273, profile_photos)
        #     end_time = datetime.datetime.today()
        #     print('-затрачено', end_time-start_time) #delete
        #     print('конец', end_time) #delete


    db.change_settings(conn, user_id, last_search=start_time)


def _get_search(vk, user_id, quantity): #простой поиск, с ограничением до 1000 результатов в одной выдаче. без пересчёта запросов в секунду (обычно это не требуется, т.к. выдачи мало очень)
    #можно организовать пулл реквест, чтобы сразу до 3000 в одной выдаче получать.
    offset = 0
    profiles = []
    search_settings = db.get_settings(conn, user_id) #параметры поиска
    print('-search_settings', search_settings) #delete
    if search_settings['sex'] == 1:
        search_settings['sex'] = 2
    elif search_settings['sex'] == 2:
        search_settings['sex'] = 1
    quantity = 1000 #максимальное кол-во выдаваемых профилей.
    repeat_search = True
    while repeat_search:
        request = vk.users.search(count=quantity, city_id=search_settings['city_id'], sex=search_settings['sex'], age_from=search_settings['age_from'], age_to=search_settings['age_to'], fields=("bdate", "city", "sex", "relation"))
        profiles += request['items']
        if len(profiles) == quantity:
            repeat_search = True
            offset += quantity
        else:
            repeat_search = False
    return profiles


def _get_top3_photos(vk, profile_id):
    try:
        photos = vk.photos.get(owner_id=profile_id, album_id="profile", rev=1, extended=1)
        photos = photos['items']
        i = 0
        result = []
        for photo in photos:
            likes = photo['likes']['count']
            comments = photo['comments']['count']
            rate = likes + comments
            result += [[rate, photo['sizes'][1]['url']]]
        result.sort(reverse=True) #сортируем полученный список по убыванию суммы лайков и 
        photos = [] #нужен ещё один массив
        result = result[0:3]  #обрезаем до 3х фотографий
        if len(result) < 3: #По условию три фото, значит берем только те, в которых три фото) //Гежин Олег
            return None #анкета нам не подходит
        for photo in result:
            photos += [photo[1]]         
        return [profile_id, *photos]
    except:
        return None #анкета нам не подходит (скорее всего это закрытая анкета)


def get_top3_photo(conn, profile_id, vk_session=None):
    check_profile = db.get_photos(conn, profile_id) #проверяем есть уже в базе? возможно другой пользователь уже запрашивал рейтинг данной анкеты
    print(check_profile)
    # with vk_api.VkRequestsPool(vk_session) as pool:
    #     for user in user_list:
    #         #добавляем в пулл запрос фото
    #         pass
    # #добавляем в кортеж userlist ссылку на профиль и фотографию.
    # return user_list


def _try_get_photos_from_db(conn, profile_id):
    try:
        db.get_photos(conn, profile_id)
    except:
        pass


with psycopg2.connect(database=config['pgbase'], user="postgres", password=config['pgpwd']) as conn:
    # get_ready_to_search(conn, vk_session, 31687273, vk)
    pass


user_token = config['user_token']
group_token = config['group_token']
group_id = config['group_id']

vk_session = vk_api.VkApi(token=user_token, api_version='5.131')
vk = vk_session.get_api() #сессия ВК
# lis = _get_top3_photos(vk_session, 31687273)
# print(lis)
# get_top3_photo(conn, 0)



#442068022 м
#615273465 полигон
#185512524 b
#31687273 я
