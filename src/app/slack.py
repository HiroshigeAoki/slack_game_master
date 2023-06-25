from slack_sdk import WebClient
import setting
import logging

logger = logging.getLogger("slack_game_master")
logger.setLevel(logging.DEBUG)


def handle_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            raise e

    return wrapper


class SlackClientWrapper:
    def __init__(self):
        self.slack_client = WebClient(token=setting.SLACK_BOT_TOKEN)

    @handle_errors
    def post_message(self, channel_id, message=None, blocks=None, ephermal=False, user_id=None):
        assert message or blocks, "Message or blocks must be provided"

        if ephermal:
            assert user_id, "User id must be provided when you send ephermal message"
            self.slack_client.chat_postEphemeral(channel=channel_id, user=user_id, text=message, blocks=blocks)
        else:    
            self.slack_client.chat_postMessage(channel=channel_id, text=message, blocks=blocks)

    @handle_errors
    def send_direct_message(self, user_id, message=None, blocks=None):
        response = self.slack_client.conversations_open(users=user_id)
        channel = response['channel']['id']
        self.slack_client.chat_postMessage(channel=channel, text=message, blocks=blocks)

    @handle_errors
    def get_user_id_by_email(self, email):
        response = self.slack_client.users_lookupByEmail(email=email)
        user_id = response['user']['id']
        return user_id

    @handle_errors
    def get_displayed_name(self, user_id):
        response = self.slack_client.users_info(user=user_id)
        user_profile = response['user']['profile']
        display_name = user_profile.get('display_name') or user_profile.get('real_name')
        return display_name

    @handle_errors
    def get_worckspace_members(self):
        response = self.slack_client.users_list()
        members = response['members']
        return members

    @handle_errors
    def get_channel_members(self, channel_id):
        response = self.slack_client.conversations_members(channel=channel_id)
        members = response['members']
        return members

    @handle_errors
    def get_channel_id_list(self):
        response = self.slack_client.conversations_list(types="public_channel,private_channel")
        channels = response['channels']
        channel_id_list = list(map(lambda x: x.get("id"), channels))
        return channel_id_list

    @handle_errors
    def conversations_history(self):
        return self.slack_client.conversations_history()


class SlackLoggingHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.channel = setting.ERROR_CHANNEL
        self.client = WebClient(setting.SLACK_BOT_TOKEN)
        self.level = logging.ERROR

    @handle_errors
    def emit(self, record):
        if record.levelno >= self.level:
            log_entry = self.format(record)
            self.client.chat_postMessage(channel=self.channel, text=log_entry)