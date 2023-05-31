import os
import re
import json
from dotenv import load_dotenv
load_dotenv()


def load_secrets(name):
    with open(f"/run/secrets/{name}") as f:
        try:
            secrets = json.load(f)
        except json.decoder.JSONDecodeError:
            f.seek(0)
            secrets = f.read().strip()
    return secrets


ALLOWED_DOMAINS = ["save-slack-gsheet.iam.gserviceaccount.com", "gmail.com"]
def check_email_domain(email_list: list):
    filtered = []
    for email in email_list:
            if re.search(fr"@({'|'.join(ALLOWED_DOMAINS)})$", email):
                filtered.append(email)
            else:
                raise AttributeError(f"Invalid email: {email}. Gmail only allowed.")
    return filtered

# Slack
SLACK_APP_TOKEN = load_secrets("slack_app_token")
SLACK_BOT_TOKEN = load_secrets("slack_bot_token")
SLACK_SIGNING_SECRET = load_secrets("slack_signing_secret")
SLACK_WORKSPACE_TEAM_ID = os.environ["SLACK_WORKSPACE_TEAM_ID"]
ERROR_CHANNEL = os.environ["ERROR_CHANNEL"]

# Google Spread Sheet
GCP_SERVICE_ACCOUNT_KEY = "/run/secrets/gcp_service_account_key"
SPREAD_SHEET_KEY = os.environ["SPREAD_SHEET_KEY"]
MASTER_SHEET_KEY = os.environ["MASTER_SHEET_KEY"]

# MySQL
MYSQL_ROOT_PASSWORD = os.environ["MYSQL_ROOT_PASSWORD"]
MYSQL_DATABASE = os.environ["MYSQL_DATABASE"]
MYSQL_USER = os.environ["MYSQL_USER"]
MYSQL_PASSWORD = os.environ["MYSQL_PASSWORD"]
MYSQL_HOST = os.environ["MYSQL_HOST"]

# Other settings
LOG_DIR = os.environ["LOG_DIR"]
CASE_FILE = os.environ["CASE_FILE"]

STAFF_BOT_INFO = load_secrets("staff_bot_info")
STAFF_BOT_IDS, STAFF_BOT_EMALS = [], []
for _id, email in STAFF_BOT_INFO.values():
    STAFF_BOT_IDS.append(_id)
    STAFF_BOT_EMALS.append(email)
STAFF_BOT_ID_GMAILS = check_email_domain(STAFF_BOT_EMALS)
