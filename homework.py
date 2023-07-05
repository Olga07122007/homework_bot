from http import HTTPStatus
import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests
import telegram

from exceptions import exceptions


load_dotenv()

logger = logging.getLogger(__name__)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
RETRY_PERIOD = int(os.getenv('RETRY_PERIOD', 600))

ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


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
        logger.debug('Начали отправку сообщения...')
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено!')
    except telegram.error.TelegramError as error:
        # если здесь не логгировать, то не проходят тесты
        logger.error(f'Ошибка при отправке сообщения: {error}')
        raise exceptions.TelegramError(
            f'Не удалось отправить сообщение: {error}'
        )
    except Exception as error:
        raise exceptions.TelegramError(
            f'Не удалось отправить сообщение: {error}'
        )


def get_api_answer(timestamp):
    """Запрос на сервер."""
    payload = {'from_date': timestamp}
    try:
        logger.debug(
            'Запрос на сервер '
            'https://practicum.yandex.ru/api/user_api/homework_statuses/'
        )
        response = requests.get(ENDPOINT, headers=HEADERS, params=payload)
        if response.status_code != HTTPStatus.OK:
            raise exceptions.ConnectionError(
                f'Status_code ответа сервера = {response.status_code}'
            )
        logger.debug('Запрос прошел успешно!')
        return response.json()
    except requests.RequestException as error:
        msg = (
            f'Код ответа Сервера (RequestException): {error}'
        )
        raise exceptions.ConnectionError(msg)
    except ValueError as error:
        msg = f'Код ответа сервера (ValueError): {error}'
        raise exceptions.ConnectionError(msg)


def check_response(response):
    """Проверяет ответ сервера на соответствие документации.
    Возвращает первый элемент из списка домашних работ.
    """
    logger.debug('Проверка отвера от сервера...')
    if isinstance(response, dict):
        if 'homeworks' in response:
            if isinstance(response.get('homeworks'), list):
                logger.debug('Ответ сервера соответствует ожидаемому.')
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
    if not check_tokens():
        logger.critical('Нет переменных окружения!')
        logger.debug('Остановили бот!')
        sys.exit(0)
    try:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = int(time.time()) - 86400 * 30
        previous_status = ''
        logger.debug('Запустили бот!')
        send_error = True
    except Exception as error:
        message = f'Не удалось создать бот: {error}'
        logger.error(message)
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)

            if homework.get('status') != previous_status:
                message = parse_status(homework)
                previous_status = homework.get('status')
                send_message(bot, message)
            else:
                logger.debug('Статус работы не изменился!')

        except exceptions.TelegramError as error:
            message = f'Ошибка при отправке сообщения: {error}'
            logger.error(message)

        except Exception as error:
            message = f'Ошибка: {error}'
            logger.error(message)
            if send_error:
                send_message(bot, message)
                send_error = False

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        filename='main.log',
        format=(
            '%(asctime)s, '
            '%(levelname)s, '
            'func:%(funcName)s,'
            'line№%(lineno)d, '
            '%(message)s'
        ),
        filemode='a',
    )
    logger.addHandler(
        logging.StreamHandler(sys.stdout)
    )

    try:
        main()
    except KeyboardInterrupt:
        logger.debug('Остановили бот!')
        sys.exit(0)
