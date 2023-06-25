import os
import logging
from datetime import datetime, timezone, timedelta
from src.app.slack import SlackLoggingHandler
import setting

def setup_loggers(logger):
    logger.setLevel(logging.DEBUG)
    logging.Formatter.converter = lambda *args: datetime.now(tz=timezone(timedelta(hours=+9), 'JST')).timetuple()

    os.makedirs(setting.LOG_DIR, exist_ok=True)
    file_handler = logging.FileHandler(f'{setting.LOG_DIR}/app.log')
    file_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)-9s [%(pathname)s - %(funcName)s - %(lineno)d] %(message)s'))
    logger.addHandler(file_handler)

    slack_handler = SlackLoggingHandler()
    slack_handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(slack_handler)

    return logger
