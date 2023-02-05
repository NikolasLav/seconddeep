# модуль взаимодействия с ВК
import db # модуль /работы с БД
import vk_api
from config import bot_config as config

def get_user_info(id, vk): #получение данных о пользователе бота
    try:
        return vk.users.get(user_ids=id, fields=("sex","city","relation", "bdate"))[0]
    except:
        return None


def get_ready_to_search(conn, user, vk): #подготовка к поисковому запросу
    quantity = 1000 #максимальная выдача
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
    request = vk.users.search(count=quantity, city_id=user['city']['id'], sex=sex, age_from=user['age_from'], age_to=user['age_to'], fields=("bdate", "city", "relation"))
    profiles += request['items']
    print('- users.search result:', len(profiles))
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
    db.make_temp_list(conn, user['id'], result)
    return result


def get_city(vk, query):
    cities = vk.database.getCities(q=query)



def _get_top3_photos(vk, profile):
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
        return None #анкета нам не подходит (скорее всего это закрытая анкета)


def get_top3_photo(conn, vk, user_id):
    profile = {'id': None, 'first_name': None, 'last_name': None, 'bdate': None, 'city_id': None, 'relation': None}
    person = 'anything or anyone'
    while person != None:
        try:
            _, profile['id'], profile['first_name'], profile['last_name'], profile['bdate'], profile['city_id'], profile['relation'] = db.get_profiles(conn, user_id)
            person = _get_top3_photos(vk, profile)
            db.remove_from_temp(conn, user_id, profile['id'])
            if person == None:
                person = 'go next'
            else:
                return person
        except:
            person = None


# def test(vk_session, persons):
#     profiles = []
#     with vk_api.VkRequestsPool(vk_session) as pool:
#         for item in range(len(persons)):
#             # photos = vk.photos.get(owner_id=profile['id'], album_id="profile", rev=1, extended=1)
#             profiles += [pool.method('photos.get', {"owner_id":persons[item]['id'],"album_id":"profile","rev":1,"extended":1})]
    
#     for item in range(len(persons)):
#         # print('profile.result')
#         print(len(profiles[item].result['items']))
#         # print(profile.result['items'])
#         # try:
#         photos = profiles[item].result['items']
#         if len(photos) < 3: #По условию три фото, значит берем только те, в которых три фото) //Гежин Олег
#             return None #анкета нам не подходит
#         result = []
#         for photo in photos:
#             likes = photo['likes']['count']
#             comments = photo['comments']['count']
#             rate = likes + comments
#             result += [[rate, photo['id']]]
#         result.sort(reverse=True) #сортируем полученный список по убыванию суммы лайков и 
#         photos = [] #нужен ещё один массив
#         result = result[0:3]  #обрезаем до 3х фотографий
#         for photo in result:
#             photos += [photo[1]]
#         name = f"{persons[item]['first_name']} {persons[item]['last_name']}"
#         person = {'id': persons[item]['id'], 'name': name}
#         print([person, *photos])
#         # i += 1
#             # return [person, *photos]
#         # except:
#             # return None
#         #    pass



# user_token = config['user_token']
# # group_token = config['group_token']
# # group_id = config['group_id']

# vk_session = vk_api.VkApi(token=user_token, api_version='5.131')
# profiles = [{'id': 245720141, 'first_name': 'Vasya', 'last_name': 'Ivanova', 'bdate': None, 'city_id': None, 'relation': None}, {'id': 8386755, 'first_name': 'Ivanna', 'last_name': 'Vasilieva', 'bdate': None, 'city_id': None, 'relation': None}]
# # persons = [245720141, 8386755]
# print(test(vk_session, profiles))