import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

FIRST_WORK = 0
RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}

logger = logging.getLogger(__name__)


class APIError(Exception):
    """API response error."""

    pass


class APICodeError(Exception):
    """API response code error."""

    pass


class APIConnectionError(Exception):
    """API connection error."""

    pass


class TelegramMessageError(Exception):
    """Telegram message error."""

    pass


class ParseStatusError(Exception):
    """Parse status error."""

    pass


def check_tokens():
    """Проверка наличия переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot, message):
    """Логика работы отправки сообщения в телеграм."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message,
        )
    except telegram.error.TelegramError as error:
        logger.error('Ошибка при отправке сообщения в телеграм')
        raise TelegramMessageError(error)
    logger.debug('Сообщение успешно отправленно.')


def get_api_answer(timestamp):
    """Возврат ответа API приведенный к типам данным Python."""
    try:
        homework_status = requests.get(
            url=ENDPOINT,
            headers=HEADERS,
            params={'from_date': timestamp},
        )
        if homework_status.status_code != HTTPStatus.OK:
            raise APICodeError(
                f'Код ошибки ответа API: {homework_status.status_code}'
            )
        homework_json = homework_status.json()
        if not isinstance(homework_json, dict):
            raise TypeError('Ответ API не приведен к типам данных Python.')
    except requests.exceptions.RequestException as error:
        raise APIConnectionError(error)
    except Exception as error:
        raise APIError(error)
    logger.debug('Возврат ответа API приведен к типам данныx Python.')
    return homework_json


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if isinstance(response, dict) is False:
        raise TypeError('Ответ API не соответствует типу dict.')
    if 'homeworks' not in response:
        raise KeyError('Не найден ключ: current_date.')
    if 'current_date' not in response:
        raise KeyError('Не найден ключ: homeworks.')
    if isinstance(response.get('homeworks'), list) is False:
        raise TypeError('homeworks не соответствует типу list.')
    logger.debug('Ответ API соответствует документации.')
    return response.get('homeworks')


def parse_status(homework):
    """Проверка статуса домашней работы."""
    if isinstance(homework, dict) is False:
        raise TypeError('homework не соответствует типу dict.')
    if 'status' not in homework:
        raise KeyError('Не найден ключ: status.')
    if 'homework_name' not in homework:
        raise KeyError('Не найден ключ: homework_name.')
    homework_name = homework.get('homework_name')
    status = homework.get('status')
    if status not in HOMEWORK_VERDICTS:
        raise ParseStatusError('Неожиданный статус домашней работы.')
    verdict = HOMEWORK_VERDICTS.get(status)
    logger.debug(f'Статус работы {verdict}')
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if check_tokens() is False:
        logger.critical(
            'Отсутствуют необходимые токены. '
            'Программа принудительно остановлена.'
        )
        raise SystemExit('Отсутствуют необходимые токены.')
    logger.debug('Все токены на месте!')

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time()) - RETRY_PERIOD
    message_info = 'Бот начал отслеживание домашних работ...'
    message_empty = True
    error_empty = ''

    while True:
        try:
            if message_empty:
                logger.debug(message_info)
                send_message(bot, message_info)
                message_empty = False
            response = get_api_answer(timestamp)
            homework = check_response(response)
            timestamp = response.get('current_date')
            if homework:
                message = parse_status(homework[FIRST_WORK])
                send_message(bot, message)
                logger.debug(message)
            else:
                logger.debug('Новых статусов нет!')
        except TelegramMessageError as error:
            logger.error(
                f'Ошибка при отправке сообщения в телеграм: {error}'
            )
        except Exception as error:
            message_error = f'Сбой в работе программы: {error}'
            logger.error(message_error)
            if str(error) != str(error_empty):
                send_message(bot, message_error)
                error_empty = error
        finally:
            logger.debug('Начат отсчет времени!')
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    LOG_FORMAT = '%(asctime)s - [%(levelname)s] - %(message)s'
    handler = logging.StreamHandler(stream=sys.stdout)
    logger.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(LOG_FORMAT))
    logger.addHandler(handler)

    main()
