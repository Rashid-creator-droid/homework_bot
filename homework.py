import logging
import os
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

LOG_FORMAT = f'%(asctime)s - [%(levelname)s] - %(message)s'

logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
logger.setLevel(logging.DEBUG)
handler.setFormatter(logging.Formatter(LOG_FORMAT))
logger.addHandler(handler)


def check_tokens():
    """Проверка наличия переменных окружения."""
    tokens = {
        'practicum_token': PRACTICUM_TOKEN,
        'telegram_token': TELEGRAM_TOKEN,
        'telegram_chat_id': TELEGRAM_CHAT_ID,
    }
    try:
        for name, token in tokens.items():
            if token is None:
                raise SystemExit(
                    f'Отсутствует токен {name}.'
                    f'Программа принудительно остановлена.'
                )
    except SystemExit as error:
        logger.critical(error)
    else:
        return True


def send_message(bot, message):
    """Логика работы отправки сообщения в телеграм."""
    try:
        bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=message
        )
    except Exception as error:
        logger.error(f'Ошибка при отправке сообщения {error}.')
    else:
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
            raise Exception(f'Код ошибки {homework_status.status_code}')
    except requests.exceptions.RequestException as error:
        logger.error(error)
    else:
        if not isinstance(homework_status.json(), dict):
            raise TypeError(f'Ответа API не приведен к типам данных Python.')
        else:
            logger.debug(f'Ответа API приведен к типам данных Python.')
            return homework_status.json()


def check_response(response):
    """Проверка ответа API на соответствие документации."""
    if isinstance(response, dict):
        if 'homeworks' in response:
            if 'current_date' in response:
                if isinstance(response.get('homeworks'), list):
                    logger.debug(f'Ответ API соответствует документации.')
                    return response.get('homeworks')
                raise TypeError('homeworks не соответсвует типу list.')
            raise KeyError('Не найден ключ: homeworks.')
        raise KeyError('Не найден ключ: current_date.')
    raise TypeError('Ответ API не соответсвует типу dict.')


def parse_status(homework):
    """Проверка статуса домашней работы."""
    if isinstance(homework, dict):
        if 'status' in homework:
            if 'homework_name' in homework:
                homework_name = homework.get('homework_name')
                status = homework.get('status')
                if status in HOMEWORK_VERDICTS:
                    verdict = HOMEWORK_VERDICTS.get(status)
                    logger.debug(f'Статус работы {verdict}')
                    return (
                        f'Изменился статус проверки работы '
                        f'"{homework_name}". {verdict}'
                    )
                else:
                    raise Exception('Неожиданный статус домашней работы.')
            raise KeyError('Не найден ключ: homework_name.')
        raise KeyError('Не найден ключ: status.')
    raise TypeError('homework не соответсвует типу dict.')


def main():
    """Основная логика работы бота."""
    if check_tokens() is True:
        bot = telegram.Bot(token=TELEGRAM_TOKEN)
        timestamp = int(time.time()) - RETRY_PERIOD
        error_0 = ''
        message_info = 'Бот начал отслеживание домашних работ...'
        logger.debug(message_info)
        send_message(bot, message_info)
        while True:
            try:
                response = get_api_answer(timestamp)
                homework = check_response(response)
                if len(homework) > 0:
                    message = parse_status(homework[FIRST_WORK])
                    send_message(bot, message)
                else:
                    logger.debug('Новых статусов нет!')
                time.sleep(RETRY_PERIOD)
            except Exception as error:
                message_error = f'Сбой в работе программы: {error}'
                logger.error(message_error)
                if str(error) != str(error_0):
                    send_message(bot, message_error)
                    error_0 = error
                time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
