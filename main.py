""" Запуск программы """
from bot import Bot

""" главная часть """
def main() -> None:
    bot_start = Bot()
    bot_start.activate()


if __name__ == '__main__':
    main()
