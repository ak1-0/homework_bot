class RequestExceptionError(Exception):
    """Ошибка при отправке запроса."""


class NotJsonError(Exception):
    """Ошибка: формат не JSON."""


class HTTPStatusStatusError(Exception):
    """Ошибка: HTTPStatus не равен 200."""
