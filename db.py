# Модуль операций с SQL
import psycopg2
import datetime


def db_check(conn): #проверка есть ли база вообще
    result = 'error'
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='users';")
            result = cur.fetchall()
            if result:
                if len(result) > 0:
                    result = 'check'
            else:
                result = 'empty'
    except:
        pass
    return result


def create_db(conn):
    #создаём таблицы и зависимости
    """
    1. Таблица клиентов: user_id, bdate, sex, city_id, relation, (groups, books, music, interests,) last_update (timestamp последнего обновления анкеты)
    2. Таблица настроек: age_to, age_from, data_lifetime (актуальность записей из таблицы профилей по умочанию - 2 дня), weights
    3. Таблица временных значений temp_list: !user_id, profile_id, fname, lname, bdate, sex, city_id, relation, (groups, books, music, interests,) timestamp этой записи #портируем сюда данные из поиска.
    4. Таблица выданных результатов: !user_id, profile_id, like, timestamp
    5. Таблица друзей: !user_id, friend_id #Добавляем все id-профили друзей этого юзверя
    """

    with conn.cursor() as cur:
    #1 Таблица клиентов программы
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
        user_id integer NOT NULL,
        first_name varchar(60) NOT NULL,
        last_name varchar(60) NOT NULL,
        bdate date NOT NULL,
    	city_id integer NOT NULL,
        sex integer NOT NULL,
        relation integer NOT NULL,
        last_update timestamp NOT NULL,
        CONSTRAINT pk_users PRIMARY KEY (user_id));
        """)
    #2 Таблица настроек пользователя
        cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
        user_id integer NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
        age_from integer,
        age_to integer,
        data_lifetime interval NOT NULL,
		last_search timestamp NOT NULL,
        CONSTRAINT pk_settings PRIMARY KEY (user_id));
        """)
    #3 Таблица временных значений
        cur.execute("""
        CREATE TABLE IF NOT EXISTS temp_list (
        user_id integer NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
        profile_id integer NOT NULL,
        first_name varchar(60) NOT NULL,
        last_name varchar(60),
        bdate date,
    	city_id integer,
        sex integer,
        relation integer,
        last_update timestamp NOT NULL);
        """)
    #4 Таблица выданных результатов (история выдачей)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
        user_id integer NOT NULL REFERENCES users (user_id) ON DELETE CASCADE,
        profile_id integer NOT NULL,
        banned boolean NOT NULL,
        favorit boolean NOT NULL,
        result_time timestamp NOT NULL);
        """)
    conn.commit()


def drop_db(conn):
    if db_check(conn) == 'check':
        with conn.cursor() as cur:
            cur.execute("""
            DROP TABLE users CASCADE; 
            DROP TABLE temp_list CASCADE;
            DROP TABLE settings CASCADE;
            DROP TABLE photos CASCADE;
            DROP TABLE results CASCADE;
            """)
            # DROP TABLE blacklist CASCADE;
            # DROP TABLE favorits CASCADE;
        conn.commit()


def check_user(conn, user_id):
    check = 'initial'
    now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    with conn.cursor() as cur:
        cur.execute("""
        SELECT u.user_id, %s-last_update, data_lifetime FROM users u
        JOIN settings s ON u.user_id = s.user_id
        WHERE u.user_id = %s
        """, (now, user_id))
        result = cur.fetchall()
    if len(result) > 0:
        check = result
        _, check_lifetime, delta = check[0]
        if check_lifetime >= delta:
            check = 'Желательно обновить данные профиля. (автор бота пока не придумал как это обыграть)'
        if check_lifetime < delta:
            check = 'Данные пользователя актуальны.'
    return check


def add_user(conn, user_id, first_name, last_name, bdate, city_id, sex, relation):
    with conn.cursor() as cur:
        today = datetime.date.today()
        timestamp = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
        # добавляем пользователя
        cur.execute("""
        INSERT INTO users (user_id, first_name, last_name, bdate, city_id, sex, relation, last_update)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
        """, (user_id, first_name, last_name, bdate, city_id, sex, relation, timestamp))
        # записываем ему настройки пользователя по умолчанию (+-2 года от возраста пользователя; срок "свежести" анкеты и данных для поиска)
        cur.execute("""
        INSERT INTO settings (user_id, age_from, age_to, data_lifetime, last_search)
        VALUES (%s, %s, %s, %s, %s);
        """, (user_id, (today-bdate).days//365-2, (today-bdate).days//365+2, '2 days', today-datetime.timedelta(days=2)))
        conn.commit()


def update_user(conn, user_id, first_name=None, last_name=None, bdate=None, city_id=None, sex=None, relation=None):
    now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    params = [] # Параметры, что мы передадим в изменения
    str_params = '' #переменные, что передадутся в изменения в виде строки
    if first_name not in (None, 'NULL', ''):
        str_params += 'first_name=%'+'s, '
        params += [first_name]
    if last_name not in (None, 'NULL', ''):
        str_params += 'last_name=%'+'s, '
        params += [last_name]
    if bdate not in (None, 'NULL', ''):
        str_params += 'bdate=%'+'s, '
        params += [bdate]
    if city_id not in (None, 'NULL', ''):
        str_params += 'city_id=%'+'s, '
        params += [city_id]
    if sex not in (None, 'NULL', ''):
        str_params += 'sex=%'+'s, '
        params += [sex]
    if relation not in (None, 'NULL', ''):
        str_params += 'relation=%'+'s, '
        params += [relation]
    params += [now, user_id] #можно просто перезаписать время последнего обновления анкеты, без изменений профиля. чтобы при проверке не было предупреждения
    with conn.cursor() as cur:
        SQL = f"UPDATE users SET {str_params}last_update=%s WHERE user_id=%s;"
        cur.execute(SQL, params)
    conn.commit()


def change_settings(conn, user_id, age_from=None, age_to=None, data_lifetime=None, last_search=None):
    params = [] # Параметры, что мы передадим в изменения
    str_params = '' #переменные, что передадутся в изменения в виде строки
    if age_from not in (None, 'NULL', ''):
        str_params += 'age_from=%'+'s, '
        params += [age_from]
    if age_to not in (None, 'NULL', ''):
        str_params += 'age_to=%'+'s, '
        params += [age_to]
    if data_lifetime not in (None, 'NULL', ''):
        str_params += 'data_lifetime=%'+'s, '
        params += [data_lifetime]
    if last_search not in (None, 'NULL', ''):
        str_params += 'last_search=%'+'s, '
        params += [last_search]
    # print('СТРОКА:', str_params)
    # print('ПАРАМЕТРЫ:', params)
    if str_params:
        params += [user_id]
        with conn.cursor() as cur:
            SQL = f"UPDATE settings SET {str_params[0:-2:1]} WHERE user_id=%s;"
            cur.execute(SQL, params)
        conn.commit()


def add_results(conn, user_id, profiles): #список профилей не должен быть пустым! проверить перед отправкой
    now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    SQL = "INSERT INTO results (user_id, profile_id, banned, favorite, result_time) VALUES "
    for profile in profiles:
        SQL += f"({user_id}, {profile}, {False}, {False}, '{now}'), "
    with conn.cursor() as cur:
        cur.execute(SQL[0:-2:1]+";")
    conn.commit()


def del_results(conn, user_id): #Очистка истории поисков (ну вдруг нужна? :))
    with conn.cursor() as cur:
        cur.execute("""
        DELETE FROM results WHERE user_id=%s;    
        """, user_id)
    conn.commit()


def make_temp_list(conn, user_id, profiles, city_filter=True):
    now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    with conn.cursor() as cur:
        cur.execute("SELECT city_id FROM users WHERE user_id = %s;", (user_id,))
        user_city_id = cur.fetchone()
        # cur.execute("SELECT data_lifetime FROM settings WHERE user_id = %s;", (user_id,))
        # lifetime = cur.fetchall()
    for profile in profiles:
        profile_id = profile['id']
        first_name = profile['first_name']
        last_name = profile['last_name']
        try:
            if len(profile['bdate']) > 5:
                bdate = datetime.datetime.strptime(profile['bdate'], '%d.%m.%Y').date()
            else:
                bdate = datetime.datetime.strptime(profile['bdate'], '%d.%m').date()
        except:
            bdate = None
        try: 
            city_id = profile['city']['id']
        except:
            city_id = None
        try:
            sex = profile['sex']
        except:
            sex = 0
        try: 
            relation = profile['relation']
        except:
            relation = 0
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO temp_list (user_id, profile_id, first_name, last_name, bdate, city_id, sex, relation, last_update)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
            """, (user_id, profile_id, first_name, last_name, bdate, city_id, sex, relation, now))
    conn.commit()
    if city_filter:
        with conn.cursor() as cur: #и удалить тех, у кого анкета свежая, и город соответствующий!
            cur.execute(" SELECT * FROM temp_list WHERE user_id = %s AND city_id = %s;", (user_id, user_city_id))
            result = cur.fetchall()
    else:
        with conn.cursor() as cur: #и удалить тех, у кого анкета свежая, и город соответствующий!
            cur.execute(" SELECT * FROM temp_list WHERE user_id = %s;", (user_id,))
            result = cur.fetchall()
    return list(result)


def del_temp_list(conn, user_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM temp_list WHERE user_id = %s;", (user_id,)) #очистка таблицы 
    conn.commit()


def get_settings(conn, user_id):
    result = {}
    with conn.cursor() as cur:
        cur.execute(f"SELECT city_id, sex FROM users WHERE user_id={user_id};")
        result['city_id'], result['sex'] = cur.fetchone()
        cur.execute(f"SELECT age_from, age_to, data_lifetime, last_search FROM settings WHERE user_id={user_id};")
        result['age_from'], result['age_to'], result['lifetime'], result['last_search'] = list(cur.fetchone())
    return result
    

def add_photos(conn, profile_id, photo_id_0=None, photo_url_0=None, photo_id_1=None, photo_url_1=None, photo_id_2=None, photo_url_2=None):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO photos (profile_id, photo_id, photo_url) VALUES (%s, %s, %s);", (profile_id, photo_id_0, photo_url_0))
        cur.execute("INSERT INTO photos (profile_id, photo_id, photo_url) VALUES (%s, %s, %s);", (profile_id, photo_id_1, photo_url_1))
        cur.execute("INSERT INTO photos (profile_id, photo_id, photo_url) VALUES (%s, %s, %s);", (profile_id, photo_id_2, photo_url_2))
        conn.commit()


def get_photos(conn, profile_id):
    result = []
    with conn.cursor() as cur:
        cur.execute(f"SELECT photo_id, photo_url FROM photos WHERE profile_id = {profile_id};")
        photos = cur.fetchall()
    return [profile_id, *photos]
    

with psycopg2.connect(database="test", user="postgres", password="+") as conn:
    # drop_db(conn)
    # create_db(conn)
    # add_user(conn, user_id=12, first_name='New', last_name='User', bdate=datetime.datetime.strptime('24.11.1988', '%d.%m.%Y').date(), city_id=148, sex=2, relation=0)
    # check = check_user(conn, user_id=1)
    # print(check)
    # if check == 'initial':
    #     print('Первый вход')
    # check = check_user(conn, user_id=12)
    # print(check)    
    # update_user(conn, user_id=12, bdate='25.11.1989', city_id=2, sex=1, relation=2)
    # update_user(conn, user_id=1252, last_name=None)
    # change_settings(conn, user_id=12, age_from=22, age_to=27)
    # print(db_check(conn))
    # print(get_photos(conn, 1))
    # add_photos(conn, profile_id=0, photo_id_0=1, photo_url_0=None, photo_id_1=2, photo_url_1=None, photo_id_2=3, photo_url_2=None)
    pass
conn.close()