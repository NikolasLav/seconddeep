import bot
from config import bot_config as config


def main():
    user_token = config['user_token']
    group_token = config['group_token']
    group_id = config['group_id']
    bot_start = bot.Bot(user_token, group_token, group_id)
    bot_start.activate()

    
if __name__ == '__main__':
    main()