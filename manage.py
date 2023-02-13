# модуль взаимодействия с ВК
import db # модуль /работы с БД
from vk_api import VkRequestsPool


def get_user_info(id, vk): #получение данных о пользователе бота
    try:
        return vk.users.get(user_ids=id, fields=("sex","city","relation", "bdate"))[0]
    except:
        return None


def get_ready_to_search(conn, user, vk): #подготовка к поисковому запросу
    result = []
    if user['sex'] == 1:
        sex = 2
    elif user['sex'] == 2:
        sex = 1
    else:
        sex = 0
    quantity = 1000 #максимальное кол-во выдаваемых профилей.
    check_results = db.get_results(conn, user_id=user['id']) #проверяем выдавался ли уже результат?
    request = vk.users.search(count=quantity, city_id=user['city']['id'], sex=sex, age_from=user['age_from'], age_to=user['age_to'], fields=("city", "relation"))
    profiles = request['items']
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


def get_cities(vk, query):
    try:
        id = int(query)
        request = vk.database.getCitiesById(city_ids=id)
        cities = request
    except:
        request = vk.database.getCities(q=query)
        cities = request['items']
    return cities


def rate_profiles(vk_session, persons):
    profiles = []
    marked = []
    new_persons = []
    with VkRequestsPool(vk_session) as pool:
        for item in range(len(persons)):
            profiles += [pool.method('photos.get', {"owner_id":persons[item]['id'],"album_id":"profile","rev":1,"extended":1})]
            marked += [pool.method('photos.getUserPhotos', {"user_id":persons[item]['id'],"extended":1})]
    item = 0
    for person in persons:
        try:
            photos = profiles[item].result['items']
            if len(photos) >= 3:
                result = []
                result_marked = []
                try:
                    _marked = marked[item].result['items']
                    for mark in _marked:
                        likes = mark['likes']['count']
                        comments = mark['comments']['count']
                        rate = likes + comments
                        result_marked += [[rate, mark['owner_id'], mark['id']]]
                    result_marked.sort(reverse=True)
                    _marked = []
                    result_marked = result_marked[0:3]
                    for photo in result_marked:
                        _marked += [photo[1], photo[2]]
                except:
                    _marked = None
                for photo in photos:
                    likes = photo['likes']['count']
                    comments = photo['comments']['count']
                    rate = likes + comments
                    result += [[rate, photo['id']]]
                result.sort(reverse=True)
                photos = []
                result = result[0:3]
                for photo in result:
                    photos += [photo[1]]
            else:
                photos = None
            name = f"{person['first_name']} {person['last_name']}"
            person = {'id': person['id'], 'name': name, 'profile_photos': photos, 'marked_photos': _marked}
        except:
            name = f"{person['first_name']} {person['last_name']}"
            person = {'id': persons[item]['id'], 'name': name, 'profile_photos': None}   
        item += 1
        new_persons.append(person)
    return new_persons


def prepare_results(conn, user_id, vk_session):
    person = db.get_results(conn, user_id=user_id, not_seen=True)
    if person == []:
        while person == []:
            profiles = db.get_profiles(conn, user_id)
            if len(profiles) > 0:
                profiles = rate_profiles(vk_session, profiles)
                if len(profiles) > 0:
                    db.add_results(conn, user_id, profiles)
                    person = db.get_results(conn, user_id=user_id, not_seen=True)
            elif len(profiles) == 0:
                break