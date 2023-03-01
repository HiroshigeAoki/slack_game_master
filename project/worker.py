import os
import json
import re
import pandas as pd
import datetime
import pytz
from slack_sdk.errors import SlackApiError
from slack_sdk import WebClient
from celery import Celery
import gspread
from gspread_formatting.dataframe import format_with_dataframe, BasicFormatter
from gspread_dataframe import set_with_dataframe
from gspread_formatting import Color, DataValidationRule, BooleanCondition, set_data_validation_for_cell_range, CellFormat
from gspread.exceptions import GSpreadException, APIError
from oauth2client.service_account import ServiceAccountCredentials

options = 
[
    {
        "type": "button",
        "text": {
            "type": "plain_text",
            "text": "詐欺師",
        },
        "value": "liar",
        },
    {
        "type": "button",
        "text": {
            "type": "plain_text",
            "text": "詐欺師じゃない",
        },
        "value": "honest",
    },
]

select_role_block = {
    "blocks": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Please select your role:",
            },
            "accessory": {
                "type": "static_select",
                "options": options,
                "action_id": "select_role",
            },
        },
    ],
}


celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")

slack_client = WebClient(token=os.environ["SLACK_API_TOKEN"])

scope = ['https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file']

creds = ServiceAccountCredentials.from_json_keyfile_name(os.environ["PATH_TO_JSON_KEYFILE"], scope)
google_client = gspread.authorize(creds)


ALLOWED_DOMAINS = ["save-slack-gsheet.iam.gserviceaccount.com", "gmail.com"]
def check_email_domain(email_list: list):
    filtered = []
    for email in email_list:
            if re.search(fr"@({'|'.join(ALLOWED_DOMAINS)})$", email):
                filtered.append(email)
            else:
                raise AttributeError(f"Invalid email: {email}. Gmail only allowed.")
    return filtered


with open('./staff_bot_id_email.json', 'r') as f:
    STAFF_BOT_ID_EMAIL = json.load(f)
    STAFF_BOT_IDS, STAFF_BOT_EMALS = [], []
    for _id, email in STAFF_BOT_ID_EMAIL.values():
        STAFF_BOT_IDS.append(_id)
        STAFF_BOT_EMALS.append(email)
    STAFF_BOT_ID_GMAIL = check_email_domain(STAFF_BOT_EMALS)


def unix_to_jst(unix_time):
    utc_datetime = datetime.datetime.utcfromtimestamp(unix_time)
    jst_tz = pytz.timezone('Asia/Tokyo')
    jst_datetime = utc_datetime.replace(tzinfo=pytz.utc).astimezone(jst_tz)
    jst_str = jst_datetime.strftime('%Y-%m-%d %H:%M:%S')
    return jst_str


def send_to_slack(channel_id, message):
    slack_client.chat_postMessage(channel=channel_id, text=message)


def save_to_gsheet(worksheet_name, df, channel_id, customer_email, sales_email):
    try:
        # 編集権限を付与
        spreadsheet = google_client.open_by_key(os.environ['SPREAD_SHEET_KEY'])
        for email in [customer_email, sales_email]:
            spreadsheet.share(
                email_address=email,
                perm_type="user",
                role="writer",
                with_link=False,
                notify=False
            )
        
        # 既に同じ名前のworksheetが存在すれば、それを上書きする。
        worksheet_list = spreadsheet.worksheets()
        worksheet = None
        for ws in worksheet_list:
            if ws.title == worksheet_name:
                worksheet = ws
                break
        if worksheet is None:
            worksheet = spreadsheet.add_worksheet(title=worksheet_name, rows=10, cols=4)
        worksheet.clear()
        set_with_dataframe(worksheet, df)

        # ヘッダーのフォーマッティング
        header_formatter = BasicFormatter(
            header_background_color=Color(128, 128, 128),
            freeze_headers=True,
        )
        format_with_dataframe(worksheet, df, header_formatter)
        
        # lieカラムのTrue, Falseをチェックボックに
        validation_rule = DataValidationRule(
            BooleanCondition('BOOLEAN', ['TRUE', 'FALSE']),
            showCustomUi=True
        )
        lie_col_range = f'E2:E{len(df.index) + 1}'
        suspicious_col_range = f'F2:F{len(df.index) + 1}'
        set_data_validation_for_cell_range(worksheet, lie_col_range, validation_rule)
        set_data_validation_for_cell_range(worksheet, suspicious_col_range, validation_rule)
        
        # TODO: 背景色をsalesとcustomerで変更
        # for index, value in enumerate(df['role']):
        #     if value == 'sales':
        #         background_color = {'red': 1.0, 'green': 0.0, 'blue': 0.0}
        #     elif value == 'customer':
        #         background_color = {'red': 0.0, 'green': 1.0, 'blue': 0.0}
        #     row_format = worksheet.range(f'A{index+2}:F{index+2}').format
        #     row_format.update(background_color)
        #     worksheet.range(f'A{index+2}:F{index+2}').format = row_format
        
        # TODO: セルの横幅を変える。
        
        # 編集制限
        other_cols_range = f"A1:D{len(df.index) + 1}"
        header_range = "A1:F1"
        
        worksheet.add_protected_range(
            lie_col_range,
            editor_users_emails=STAFF_BOT_ID_GMAIL + [sales_email],
        )
        worksheet.add_protected_range(
            suspicious_col_range,
            editor_users_emails=STAFF_BOT_ID_GMAIL + [customer_email]
        )
        worksheet.add_protected_range(
            other_cols_range,
            editor_users_emails=STAFF_BOT_EMALS
        )
        worksheet.add_protected_range(
            header_range,
            editor_users_emails=STAFF_BOT_EMALS
        )
        
        # ミスを防ぐため、フィルターを掛けて、営業役の発話だけを見れるようにする。
        # worksheet.set_basic_filter(filters={'columnName': 'role', 'criteria': {'values': ['sales']}})
        
        return worksheet.url

    except APIError as e:
        message = f"API Error: {e}"
        send_to_slack(channel_id=channel_id, message=message)
    
    except GSpreadException as e:
        message = f"Error saving messages: {e}"
        send_to_slack(channel_id=channel_id, message=message)


@celery.task(name="save_messages_task", time_limit=300)
def save_messages_task(channel_id, customer_id, judge):
    """
        客役が/lie or /trustでジャッジしたときに呼ばれ、Slackのメッセージ全て読みこんで、
        Googleスプレットシートに'{チャンネル名}_{lie or trust}'のワークシートを追加して保存。
        営業役の人にアノテーションをしてもらうため、

    Args:
        channel_id (str): チャンネルID
        customer_id (str): 勧誘を受ける側(客)のID
        judge (Judge): 客が勧誘役が詐欺師かどうか判断したもの. lie or trust.
    
    Return:
        url(str): 営業役の人に発話が嘘かどうか、アノテーションをしてもらうため、スプレットシートのURL(フィルターで営業役の人のメッセージだけ表示)を送る。

    """
    try:
        messages = dict(
            ts=[],
            user=[],
            role=[],
            message=[],
            lie=[],
            suspicious=[]
        )
        cursor = None
        
        response = slack_client.conversations_members(channel=channel_id)
        
        # 営業役のIDを取得
        members = set(response['members'])
        sales_id_set = members - set(STAFF_BOT_IDS + [customer_id])
        assert len(sales_id_set) == 1, f"スタッフ:{len(STAFF_BOT_IDS)}人、被験者:2人以外に、{len(sales_id_set) - 1}人余分に入っています。"
        sales_id = sales_id_set.pop()
        
        # TODO: 営業役の人に嘘つきかどうか正解を打ち込んでもらう。
        answer = ""
        
        # メールを取得して、@gmail.comか確認。
        emails = []
        for _id in [customer_id, sales_id]:
            response = slack_client.users_info(user=_id)
            emails.append(response['user']['profile']['email'])
        check_email_domain(emails)
        customer_email, sales_email = emails
        
        while True:
            response = slack_client.conversations_history(
                channel=channel_id,
                exclude_archived=True,
                types="message",
                limit=1000,
                cursor=cursor
            )
            
            for message in response["messages"]:
                if "subtype" not in message and message["user"] in [customer_id, sales_id]:
                    messages["ts"].append(float(message['ts']))
                    messages["user"].append(message["user"])
                    messages["role"].append("customer" if message["user"] == customer_id else "sales")
                    messages["message"].append(message["text"])
                    messages["lie"].append(False)
                    messages["suspicious"].append(False)

            if response['has_more']:
                cursor = response['response_metadata']['next_cursor']
            else:
                break
        
        channel_info = slack_client.conversations_info(channel=channel_id)
        channel_name = channel_info["channel"]["name"]
        worksheet_name = f"{channel_name}_pred:{judge}_ans:{answer}"
        df = pd.DataFrame.from_dict(messages).sort_values(by="ts").reset_index(drop=True)
        df['ts'] = df['ts'].apply(unix_to_jst)
        
        worksheet_url = save_to_gsheet(worksheet_name, df, channel_id, customer_email, sales_email)
        
        # TODO: 騙さない場合はアノテーションいらない？
        message = f"<@{sales_id}> アノテーションを行ってください。 {worksheet_url}"
        send_to_slack(channel_id=channel_id, message=message)

        return True

    except SlackApiError as e:
        send_to_slack(channel=channel_id, message=e.response['error'])

    except AssertionError as e:
        send_to_slack(channel_id=channel_id, message=str(e))
        
    except AttributeError as e:
        send_to_slack(channel_id=channel_id, message=str(e))