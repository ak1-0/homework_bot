class RequestExceptionError(Exception):
    """Ошибка при отправке запроса."""


class HTTPStatusStatusError(Exception):
    """Ошибка: HTTPStatus не равен 200."""
