class TelegramError(Exception):
    """Кастомное исключение.
    Если при отправке сообщения в Телеграм произошла ошибка.
    """
    pass

    
class ConnectionError(Exception):
    """Кастомное исключение.
    Если при запросе на сервер произошла ошибка.
    """
    pass