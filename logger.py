import os
import logging
import traceback
import setting
from datetime import datetime, timezone, timedelta
from logging.handlers import RotatingFileHandler
from slack_sdk import WebClient
from src.app.slack import SlackClientWrapper

class LoggerWrapper:
    def __init__(self):
        self.logger = self.create_logger()

    def create_logger(self):
        os.makedirs(setting.LOG_DIR, exist_ok=True)
        
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter(fmt='%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
        logging.Formatter.converter = lambda *args: datetime.now(tz=timezone(timedelta(hours=+9), 'JST')).timetuple()
        
        handler = logging.FileHandler(f'{setting.LOG_DIR}/app.log')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    def info(self, message):
        self.logger.info(message)
    
    def debug(self, message):
        self.logger.debug(message)

    def error(self, message, slack_client: WebClient=None, corresponding_channel_id=None, body=None, post_to_corresponding_channel=False):
        self.logger.error(message)
        self.logger.error(traceback.format_exc())

        if corresponding_channel_id:
            message += f" <#{corresponding_channel_id}>"
        if body:
            message += f", <@{body['user_id']}>, `{body['command']}` "

        try:
            if slack_client:
                if corresponding_channel_id and post_to_corresponding_channel:
                    SlackClientWrapper.post_message(slack_client, channel_id=corresponding_channel_id, message=str(message))
                    
                SlackClientWrapper.post_message(slack_client, channel_id=setting.ERROR_CHANNEL, message=str(message))

        except Exception as e:
            self.logger.error(traceback.format_exc())
            self.logger.error(f"Failed to send Slack message: {e}")