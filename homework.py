import logging
import os
import sys
import time
from http import HTTPStatus
from sys import stdout
from time import ctime

import requests
import telegram
from dotenv import load_dotenv
from telegram import TelegramError

import exceptions as err

load_dotenv()


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


logger = logging.getLogger(__name__)


def check_tokens() -> bool:
    """Проверяет переменные окружения."""
    if not all((PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)):
        error_message = 'Отсутствуют переменные окружения'
        logger.critical(error_message)
        sys.exit(error_message)


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщения в Telegram чат."""
    logger.info(
        f'Попытка отправить сообщение: {message}')
    try:
        bot.send_message(
            TELEGRAM_CHAT_ID,
            message,
        )
    except TelegramError as telegram_error:
        logger.error(
            f'Сбой отправки сообщения: {message}, {telegram_error}',
            exc_info=True)
    else:
        logger.debug(
            f'Сообщение отправлено: {message}')


def get_api_answer(timestamp: int) -> dict:
    """Запрашивает получение ответа."""
    params = {'from_date': timestamp}
    logger.info(f'Попытка отправки запроса: {ENDPOINT}, '
                f'{HEADERS}, {params}, ')
    try:
        homework_status = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params)
    except requests.RequestException as error:
        raise err.RequestExceptionError(f'Ошибка {error}, {timestamp}, ')
    if homework_status.status_code != HTTPStatus.OK:
        raise err.HTTPStatusStatusError(
            f'Сбой доступа {ENDPOINT}, '
            f'Статус ответа: {homework_status.status_code}, '
            f'Текст ответа: {homework_status.text}.'
        )
    return homework_status.json()


def check_response(response: dict) -> dict:
    """Проверяет ответ API на соответствие документации."""
    logger.debug('Проверка ответа API')
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    if 'homeworks' not in response:
        raise KeyError(
            'Ответ API не содержит ключа "homeworks"'
        )
    if 'current_date' not in response:
        raise KeyError(
            'Ответ API не содержит ключа "current_date"'
        )
    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise TypeError('homeworks не является списком')
    return homeworks


def parse_status(homework) -> str:
    """Информация о статусе домашней работы."""
    logger.debug('Начало сбора сведений о статусе домашней работы')
    if 'homework_name' not in homework:
        raise KeyError(
            'Ответ API не содержит ключа "homework_name"'
        )
    if 'status' not in homework:
        raise KeyError(
            'Ответ API не содержит ключа "status"')
    homework_name = homework['homework_name']
    homework_status = homework['status']
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(
            f'У домашней работы нет статуса - {homework_status}')
    logger.info('Домашняя работа получила статус.')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы программы."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    last_status = ''
    now = ctime
    logger.info(f'Бот запустился {now}')
    while True:
        try:
            response = get_api_answer(timestamp)
            homeworks = check_response(response)
            if not homeworks:
                message = 'Список домашек пуст'
                logging.debug(message)
            else:
                message = parse_status(homeworks[0])
            if message == last_status:
                logger.debug('Обновлений нет')
            else:
                send_message(bot, message)
                last_status = message
            timestamp = response.get('current_date')
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.error(message, exc_info=True)
            if message != last_status:
                send_message(bot, message)
                last_status = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(levelname)s - %(message)s - %(name)s',
        stream=stdout)
    main()
