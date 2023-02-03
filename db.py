# Модуль операций с SQL
import psycopg2
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
        Временная таблица должна очищаться после запроса пользователя, смены параметров запроса.
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
        bdate date,
        relation integer);
        """)
    #4 Таблица выданных результатов (история выдачей)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS results (
        user_id integer NOT NULL,
        profile_id integer NOT NULL,
		profile_name varchar(70) NOT NULL,
        photo_ids varchar(40) NOT NULL,
        banned boolean NOT NULL,
        favorit boolean NOT NULL,
        result_time timestamp NOT NULL);
        """)


def drop_db(conn):
    if db_check(conn) == 'check':
        with conn.cursor() as cur:
            cur.execute("""
            DROP TABLE temp_list CASCADE;
            DROP TABLE results CASCADE;
            """)
        conn.commit()


def add_results(conn, user_id, profile): #список профилей не должен быть пустым! проверить перед отправкой
    now = datetime.datetime.today().strftime("%Y-%m-%d %H:%M:%S")
    photo_ids = f'{str(profile[1])},{str(profile[2])},{str(profile[3])}'
    if profile[0]['id'] not in get_results(conn, user_id=user_id):
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO results (
                user_id, 
                profile_id, 
                profile_name, 
                photo_ids, 
                banned, 
                favorite, 
                result_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s);""",
                (user_id, profile[0]['id'], profile[0]['name'], photo_ids, False, False, now))
        conn.commit()


def remove_from_temp(conn, user_id, profile_id): #список профилей не должен быть пустым! проверить перед отправкой
    with conn.cursor() as cur:
        cur.execute(f"DELETE FROM temp_list WHERE profile_id = {profile_id} AND user_id = {user_id};")
    conn.commit()


def del_results(conn, user_id): #Очистка истории поисков (ну вдруг нужна? :))
    with conn.cursor() as cur:
        cur.execute("""
        DELETE FROM results WHERE user_id=%s;    
        """, user_id)
    conn.commit()


def make_temp_list(conn, user_id, profiles):
    for profile in profiles:
        try:
            if len(profile['bdate']) > 5:
                bdate = datetime.datetime.strptime(profile['bdate'], '%d.%m.%Y').date()
            else:
                bdate = datetime.datetime.strptime(profile['bdate'], '%d.%m').date()
        except:
            bdate = None
        try: 
            relation = profile['relation']
        except:
            relation = 0
        with conn.cursor() as cur:
            cur.execute("""
            INSERT INTO temp_list (user_id, profile_id, first_name, last_name, bdate, relation)
            VALUES (%s, %s, %s, %s, %s, %s);
            """, (user_id, profile['id'], profile['first_name'], profile['last_name'], bdate, relation))
    conn.commit()
    with conn.cursor() as cur:
        cur.execute(f"SELECT * FROM temp_list WHERE user_id = {user_id}")
        profiles = cur.fetchall()
    return profiles


def del_temp_list(conn, user_id):
    with conn.cursor() as cur:
        cur.execute("DELETE FROM temp_list WHERE user_id = %s;", (user_id,)) #очистка таблицы 
    conn.commit()


def get_results(conn, profile_id=None, user_id=None):
    if user_id == None:
        SQL = f"SELECT * FROM results WHERE profile_id = {profile_id};"
    elif profile_id == None:
        SQL = f"SELECT profile_id FROM results WHERE user_id = {user_id};"
    else:
        SQL = f"SELECT * FROM results WHERE profile_id = {profile_id} AND user_id = {user_id};"
    with conn.cursor() as cur:
        cur.execute(SQL)
        result = []
        for item in cur.fetchall():
            result += [*item]

    return result
    

def get_profiles(conn, user_id):
    pass


with psycopg2.connect(database="test", user="postgres", password="+") as conn:
    # drop_db(conn)
    # create_db(conn)
    print(get_results(conn, profile_id=None, user_id=31687273))

    pass
conn.close()