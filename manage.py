# модуль взаимодействия с ВК
import db # модуль /работы с БД


def get_user_info(id, vk): #получение данных о пользователе бота
    try:
        return vk.users.get(user_ids=id, fields=("sex","city","relation", "bdate"))[0]
    except:
        return None


def get_ready_to_search(conn, user, vk): #подготовка к поисковому запросу
    quantity = 1000 #максимальная выдача
    profiles = _get_search(conn, vk, user, quantity)
    print(f'-в текущем запросе users.search найдено {len(profiles)} анкеты (из возможных {quantity})') #delete
    return profiles #delete


def _get_search(conn, vk, user, quantity):
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


def get_city(vk):
    cities = vk.database.getCities()



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