import os
from sys import stdout
import time
from http import HTTPStatus
import json.decoder

import requests
import telegram
import logging
from telegram import TelegramError

import exceptions as err

from dotenv import load_dotenv
from time import ctime

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

logging.basicConfig(
    level=logging.DEBUG,
    filename='test.log',
    format='%(asctime)s - %(levelname)s - %(message)s - %(name)s')

logger = logging.getLogger(__name__)


def check_tokens() -> bool:
    """Проверяет переменные окружения."""
    context = {
        'PRACTICUM_TOKEN': PRACTICUM_TOKEN,
        'TELEGRAM_TOKEN': TELEGRAM_TOKEN,
        'TELEGRAM_CHAT_ID': TELEGRAM_CHAT_ID}
    for token_name, token in context.items():
        if token is None:
            msg = 'Отсутствуют переменные окружения: {}'.format(token_name)
            logger.critical(msg)
            raise SystemExit(msg)
    return all(context)


def send_message(bot: telegram.Bot, message: str) -> None:
    """Отправляет сообщения в Telegram чат."""
    logger.info(
        f'Попытка отправить сообщение: {message}')
    try:
        bot.send_message(
            TELEGRAM_CHAT_ID,
            message,
        )
        logger.debug(
            f'Сообщение отправлено: {message}')
        return True
    except TelegramError as telegram_error:
        logger.error(
            f'Сбой отправки сообщения: {telegram_error}')
        return False


def get_api_answer(timestamp: int) -> dict:
    """Запрашивает получение ответа."""
    params = {'from_date': timestamp}
    try:
        homework_status = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
        logger.info(f'Запрос {ENDPOINT}, '
                     f'{HEADERS}, {params}, '
                     f'успешно отправлен.')
    except requests.RequestException as error:
        raise err.RequestExceptionError(f'Ошибка {error}, {timestamp}')
    if homework_status.status_code != HTTPStatus.OK:
        raise err.HTTPStatusStatusError(
            f'Сбой доступа {ENDPOINT}, '
            f'Статус ответа: {homework_status.status_code}, '
            f'Текст ответа: {homework_status.text}.'
        )
    try:
        return homework_status.json()
    except json.JSONDecodeError as error:
        raise err.NotJsonError(f'Формат ответа не JSON: {error}')


def check_response(response: dict) -> dict:
    """Проверяет ответ API на соответствие документации."""
    logger.debug('Проверка ответа API')
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем')
    if response.get('homeworks') is None:
        raise KeyError('Список пуст')
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
    try:
        homework_name = homework['homework_name']
        homework_status = homework['status']
    except KeyError as error:
        msg = f'Несуществующий ключ {error}'
        logger.error(msg)
        raise KeyError(msg)
    if homework_status not in HOMEWORK_VERDICTS:
        raise KeyError(
            f'У домашней работы нет статуса - {homework_status}')
    logger.info('Домашняя работа получила статус.')
    verdict = HOMEWORK_VERDICTS.get(homework_status)
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы программы."""
    check_tokens()
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = 0
    last_status = ''
    now = ctime()
    send_message(
        bot, f'Бот запустился {now}'
    )
    logger.info(send_message)
    while True:
        try:
            response = get_api_answer(timestamp)
            homework = check_response(response)
            timestamp = response.get('current_date')
            message = parse_status(homework[0])
            if message == last_status:
                logger.debug('Обновлений нет')
            if message != last_status:
                send_message(bot, message)
            time.sleep(RETRY_PERIOD)
        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logger.critical(message)
            raise SystemExit
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logger.addHandler(
        logging.StreamHandler(stream=stdout))
    main()
