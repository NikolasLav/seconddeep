import os

env_vars = os.environ

bot_config = {
	'user_token' : env_vars['USERTOKEN'], #токен пользователя
	'group_token' : env_vars['GROUPTOKEN'], #токен группы
	'group_id' : int(env_vars['vkgroup_id']),
	'pgbase' : env_vars['pgbase'], #название базы данных в Postgres к которой подключаемся
	'pgpwd' : env_vars['pgpwd'] #пароль
}