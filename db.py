# Модуль операций с SQL
import datetime


def db_check(conn): #проверка есть ли база вообще
    result = 'error'
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME='results';")
            result = cur.fetchall()
            if result:
                if len(result) > 0:
                    result = 'check'
            else:
                result = 'empty'
    except:
        pass
    return result


def create_db(conn): #комментарии внутри
    print('- Recreate DB')
    """ Решил ограничиться двумя таблицами, чтобы СУБД занимала как можно меньше места.
        Временная таблица должна очищаться после каждого поискового запроса пользователя, смены параметров запроса.
        В БД хранятся только результаты (profile_id) конкретного пользователя (user_id),
        который, вероятно, ещё может вернуться, чтобы снова поискать. 
        
        Результаты можно очистить в настройках #(не реализовано)
    """
    with conn.cursor() as cur:
        cur.execute("""
        CREATE TABLE IF NOT EXISTS temp_list (
        user_id integer,
        profile_id integer NOT NULL,
        first_name varchar(32) NOT NULL,
        last_name varchar(32) NOT NULL,
        city_id integer,
        relation integer);
        """)
    #4 Таблица выданных результатов (история выдачей)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
        user_id integer NOT NULL,
        profile_id integer NOT NULL,
		profile_name varchar(70) NOT NULL,
        photo_ids varchar(40) NOT NULL,
        marked_photos varchar(80),
        seen boolean NOT NULL,
        banned boolean NOT NULL,
        favorite boolean NOT NULL,
        result_time timestamp NOT NULL);
        """)
        conn.commit()


def drop_db(conn):
    if db_check(conn) == 'check':
        with conn.cursor() as cur:
            cur.execute("""
            DROP TABLE temp_list CASCADE;
            DROP TABLE results CASCADE;
            """)
        conn.commit()


def add_results(conn, user_id, profiles): #список профилей не должен быть пустым! проверить перед отправкой
    now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    checklist = get_results(conn, user_id=user_id)
    for profile in profiles:
        remove_from_temp(conn, user_id, profile['id'])
        if profile['profile_photos'] != None:
            photo_ids = ','.join(str(photo) for photo in profile['profile_photos'])
            if (profile['marked_photos'] == None) or (profile['marked_photos'] == ''):
                marked_photos = None
            else:
                marked_photos = ','.join(str(photo) for photo in profile['marked_photos'])
            if profile['id'] not in checklist:
                try:
                    with conn.cursor() as cur:
                        cur.execute("""INSERT INTO results (
                            user_id,
                            profile_id,
                            profile_name,
                            photo_ids,
                            marked_photos,
                            seen,
                            banned,
                            favorite,
                            result_time)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);""",
                            (user_id, profile['id'], profile['name'], photo_ids, marked_photos, False, False, False, now))
                        conn.commit()
                except:
                    pass


def remove_from_temp(conn, user_id, profile_id): #список профилей не должен быть пустым! проверить перед отправкой
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM temp_list WHERE profile_id = {profile_id} AND user_id = {user_id};")
    conn.commit()


def del_results(conn, user_id, temp=False): #Очистка истории поисков
    if temp:
        appendix = " AND seen = FALSE"
    else:
        appendix = ""
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM results WHERE user_id = {user_id}{appendix};")
    conn.commit()


def make_temp_list(conn, user_id, profiles):
    for profile in profiles:
        try: 
            city_id = profile['city']['id']
        except:
            city_id = None
        try: 
            relation = profile['relation']
        except:
            relation = 0
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO temp_list (user_id, profile_id, first_name, last_name, city_id, relation)
            VALUES (%s, %s, %s, %s, %s, %s);
            """, (user_id, profile['id'], profile['first_name'], profile['last_name'], city_id, relation))
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM temp_list WHERE user_id = {user_id}")
        profiles = cur.fetchall()


def clear_temp(conn, user_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM temp_list WHERE user_id = %s;", (user_id,)) #очистка таблицы 
    conn.commit()


def get_results(conn, profile_id=None, user_id=None, favorite=None, banned=None, not_seen=None):
    appendix = ''
    if favorite:
        appendix += ' AND favorite = true'
    if banned:
        appendix += ' AND banned = true'
    if not_seen:
        appendix += ' AND seen = false LIMIT 1'
    if user_id == None:
        SQL = f"SELECT * FROM results WHERE profile_id = {profile_id}{appendix};"
    elif profile_id == None:
        SQL = f"SELECT * FROM results WHERE user_id = {user_id}{appendix};"
    else:
        SQL = f"SELECT * FROM results WHERE profile_id = {profile_id} AND user_id = {user_id}{appendix};"
    result = []
    try:
        with conn.cursor() as cur:
            cur.execute(SQL)
            if favorite or banned:
                for item in cur.fetchall():
                    result += [[*item]]
            else:
                for item in cur.fetchall():
                    result += [*item]
        return result
    except:
        return None
    

def update_results(conn, profile_id, user_id, favorite=None, banned=None, seen=None):
    appendix = ''
    if favorite:
        appendix += 'favorite = true '
    elif favorite == False:
        appendix += 'favorite = false '
    if banned:
        appendix += 'banned = true '
    elif banned == False:
        appendix += 'banned = false '
    if seen:
        appendix += 'seen = true '
    try:
        with conn.cursor() as cur:
            cur.execute(f"UPDATE results SET {appendix} WHERE profile_id = {profile_id} AND user_id = {user_id};")
        conn.commit()
    except:
        pass


def get_profiles(conn, user_id):
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT profile_id, first_name, last_name, relation FROM temp_list WHERE user_id = {user_id} LIMIT 10;")
            results_temp = cur.fetchall()
            results = []
            keys = ["id", "first_name", "last_name", "relation"]                
            for result in results_temp:
                profile = dict(zip(keys, result))
                results.append(profile)
        return results
    except:
        return None
