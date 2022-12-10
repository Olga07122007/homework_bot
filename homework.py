import logging
import os
import requests
import sys
import telegram
import time

from dotenv import load_dotenv
from http import HTTPStatus


logging.basicConfig(
    level=logging.DEBUG,
    filename='main.log',
    format='%(asctime)s, %(levelname)s, %(message)s',
    filemode='a',
)
logger = logging.getLogger(__name__)
logger.addHandler(
    logging.StreamHandler(sys.stdout)
)


load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

DAY = 86400


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def check_tokens():
    """Проверяет доступность переменных окружения."""
    return all([TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, PRACTICUM_TOKEN])


def send_message(bot, message):
    """Сообщение в Телеграм."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено!')
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения: {error}')


def get_api_answer(timestamp):
    """Запрос на сервер Практикума."""
    payload = {'from_date': timestamp}

    try:
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            raise Exception('Ошибка при запросе на сервер Практикума')

        return response.json()
    except requests.RequestException as error:
        message = f'Код ответа сервера: {error}'
        logger.error(message)
        raise Exception(message)


def check_response(response):
    """Проверяет ответ сервера на соответствие документации.
    Возвращает первый элемент из списка домашних работ.
    """
    if isinstance(response, dict):
        if 'homeworks' in response:
            if isinstance(response.get('homeworks'), list):
                return response.get('homeworks')[0]
            raise TypeError('homeworks представлены не в виде списка')
        raise KeyError('В ответе сервера нет ключа homeworks')
    raise TypeError('Сервер возвращает не словарь')


def parse_status(homework):
    """Извлекает статус домашней работы, возвращает результат проверки."""
    if isinstance(homework, dict):
        if 'homework_name' in homework:
            if 'status' in homework:
                homework_name = homework.get('homework_name')
                status = homework.get('status')
                if status in HOMEWORK_VERDICTS:
                    verdict = HOMEWORK_VERDICTS.get(status)
                    message = (
                        f'Изменился статус проверки работы'
                        f' "{homework_name}". {verdict}'
                    )
                    return message
                else:
                    raise KeyError('Неожиданный статус проверки')
            raise KeyError('В ответе сервера нет ключа status')
        raise KeyError('В ответе сервера нет ключа homework_name')
    raise KeyError('Сервер возвращает не словарь')


def main():
    """Основная логика работы бота."""
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - DAY
    previous_status = ''
    logger.debug('Запустили бот!')
    send_error = True

    while check_tokens():
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)

            if homework.get('status') != previous_status:
                message = parse_status(homework)
                previous_status = homework.get('status')
                send_message(bot, message)
            else:
                logger.debug('Статус работы не изменился!')

        except Exception as error:
            message = f'Ошибка при запуске бота: {error}'
            logger.error(message)
            if send_error:
                send_message(bot, message)
                send_error = False

        time.sleep(RETRY_PERIOD)

    else:
        logger.critical('Нет переменных окружения!')
        logger.debug('Остановили бот!')
        sys.exit(0)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.debug('Остановили бот!')
        sys.exit(0)
