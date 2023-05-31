import os
from dotenv import load_dotenv

load_dotenv()


# Slack
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]
SLACK_SIGNING_SECRET = os.environ["SLACK_SIGNING_SECRET"]
SLACK_WORKSPACE_TEAM_ID = os.environ["SLACK_WORKSPACE_TEAM_ID"]
ERROR_CHANNEL = os.environ["ERROR_CHANNEL"]

# Google Spread Sheet
PATH_TO_JSON_KEYFILE = os.environ["PATH_TO_JSON_KEYFILE"]
SPREAD_SHEET_KEY = os.environ["SPREAD_SHEET_KEY"]
MASTER_SHEET_KEY = os.environ["MASTER_SHEET_KEY"]

# MySQL
MYSQL_ROOT_PASSWORD = os.environ["MYSQL_ROOT_PASSWORD"]
MYSQL_DATABASE = os.environ["MYSQL_DATABASE"]
MYSQL_USER = os.environ["MYSQL_USER"]
MYSQL_PASSWORD = os.environ["MYSQL_PASSWORD"]
MYSQL_HOST = os.environ["MYSQL_HOST"]

# Work space and Game info
LOG_DIR = os.environ["LOG_DIR"]
STAFF_BOT_INFO_FILE_PATH=os.environ["STAFF_BOT_INFO_FILE_PATH"]
CASE_FILE = os.environ["CASE_FILE"]
