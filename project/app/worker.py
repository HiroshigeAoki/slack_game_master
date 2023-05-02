import os
import time
import logging
import traceback
import json
import pandas as pd
from slack_sdk.errors import SlackApiError
from slack_sdk import WebClient
import gspread
from gspread_formatting.dataframe import format_with_dataframe, BasicFormatter
from gspread_dataframe import set_with_dataframe
from gspread_formatting import DataValidationRule, BooleanCondition, set_data_validation_for_cell_range
from gspread.exceptions import GSpreadException, APIError
from oauth2client.service_account import ServiceAccountCredentials

from app.utils import check_email_domain, unix_to_jst, str_to_bool
from app.messages import start_message_block, start_message_to_sales_block, judge_receipt_message, ask_annotation_block, command_confirmation_message, thank_you_for_annotation_message, on_open_spreadsheet_block, final_result_announcement_block
from db.game_info import GameInfoDB, GameInfoTable

import setting

logger = logging.getLogger(__name__)

slack_client = WebClient(token=setting.SLACK_BOT_TOKEN)

scope = ['https://spreadsheets.google.com/feeds',
        'https://www.googleapis.com/auth/drive',
        'https://www.googleapis.com/auth/drive.file']

creds = ServiceAccountCredentials.from_json_keyfile_name(setting.PATH_TO_JSON_KEYFILE, scope)
google_client = gspread.authorize(creds)

game_info_db = GameInfoDB().get_instance()

MASTER_JUDGE_COL_INDEX = 5
MASTER_REASON_COL_INDEX = 6
MASTER_FINISH_COL_INDEX = 8

with open('./staff_bot_id_email.json', 'r') as f:
    STAFF_BOT_ID_EMAIL = json.load(f)
    STAFF_BOT_IDS, STAFF_BOT_EMALS = [], []
    for _id, email in STAFF_BOT_ID_EMAIL.values():
        STAFF_BOT_IDS.append(_id)
        STAFF_BOT_EMALS.append(email)
    STAFF_BOT_ID_GMAIL = check_email_domain(STAFF_BOT_EMALS)


def log_error(message, channel_id=None, body=None, post_to_cor_channel=False):
    logger.error(traceback.format_exc())
    logger.error(message)

    if channel_id and post_to_cor_channel:
        post_message(channel_id=channel_id, message=message)

    if channel_id:
        message += f"<#{channel_id}>"   
    if body:
        message += f", <@{body['user_id']}>, `{body['command']}` "
    post_message(channel_id=os.environ['ERROR_CHANNEL'], message=message)


"""Send message"""
def post_message(channel_id, message=None, blocks=None, ephermal=False, user_id=None):
    try:
        assert message or blocks, "Message or blocks must be provided"
        
        if ephermal:
            assert user_id, "User id must be provided when you send ephermal message"
            slack_client.chat_postEphemeral(channel=channel_id, user=user_id, text=message, blocks=blocks)
        else:    
            slack_client.chat_postMessage(channel=channel_id, text=message, blocks=blocks)
    
    except SlackApiError as e:
        message=f"Error posting message to <#{channel_id}>: {e}"
        log_error(message)
    
    except AssertionError as e:
        message=f"Error posting message to <#{channel_id}>: {e}"
        log_error(message)


def send_direct_message(user_id, message):
    try:
        response = slack_client.conversations_open(users=user_id)
        channel = response['channel']['id']
        
        slack_client.chat_postMessage(channel=channel, text=message)
        
    except SlackApiError as e:
        message=f"Error sending to DM to <@{user_id}>: {e}"
        log_error(message)


"""Slack"""
def get_user_id_by_email(email):
    try:
        response = slack_client.users_lookupByEmail(email=email)
        user_id = response['user']['id']
        return user_id

    except SlackApiError as e:
        if e.response["error"] == "users_not_found":
            message=f"No user found with email in this workspace: {email}"
        else:
            message=f"Error: {e}"
        log_error(message)


def get_displayed_name(user_id):
    try:
        response = slack_client.users_info(user=user_id)
        user_profile = response['user']['profile']
        display_name = user_profile.get('display_name') or user_profile.get('real_name')
        return display_name
    
    except SlackApiError as e:
        message=f"Error fetching user info(<@{user_id}>): {e}"
        log_error(message)
        

def get_worckspace_members():
    try:
        response = slack_client.users_list()
        members = response['members']
        return members

    except SlackApiError as e:
        message=f"Error fetching members in this workspace: {e}"
        log_error(message)


def get_channel_members(channel_id):
    try:
        response = slack_client.conversations_members(channel=channel_id)
        members = response['members']
        return members

    except SlackApiError as e:
        message=f"Error fetching members in <#{channel_id}>: {e}"
        log_error(message)
    

def get_channel_list():
    try:
        response = slack_client.conversations_list()
        channels = response['channels']
        return channels

    except SlackApiError as e:
        message=f"Error fetching channels in this workspace: {e}"
        log_error(message)


"""Google Spreadsheet"""
def share_spreadsheet(spreadsheet, email):
    try:
        spreadsheet.share(email, perm_type='user', role='writer', with_link=False, notify=False)
        logging.info(f"Shared spreadsheet with {email}")

    except GSpreadException as e:
        message=f"Error sharing spreadsheet with {email}: {e}"
        log_error(message)


def get_master_data(body, return_row_index=False):
    try:
        channel_name = body.get("channel_name")
        worksheet_name = "Sheet1"
        spreadsheet = google_client.open_by_key(os.environ['MASTER_SHEET_KEY'])

        worksheet = spreadsheet.worksheet(worksheet_name)
        df = pd.DataFrame(worksheet.get_all_records())
        
        assert len(df) != 0, "Masterスプレッドシートの取得に失敗しました。"
        
        matching_row = df[df['channel_name'] == channel_name]
        
        logging.debug(f"Matching row: {matching_row}")

        assert len(matching_row) != 0, f"スプレッドシートにチャンネル名{channel_name}が存在しません。"
        assert len(matching_row) == 1, f"スプレッドシートにチャンネル名{channel_name}が重複して存在しています。"
        
        # Update invited column
        target_row_index = matching_row.index[0]+ 2
        
        if return_row_index:
            return matching_row.to_dict(orient='records')[0], target_row_index
        else:
            return matching_row.to_dict(orient='records')[0]

    except GSpreadException as e:
        message=f"GSpreadException: {e}"
        log_error(message)

    except AssertionError as e:
        message=str(e)
        log_error(message, channel_id=body.get("channel_id"), body=body, post_to_cor_channel=True)


def save_value_to_master_sheet(target_row_index, target_col_index, value):
    try:
        spreadsheet = google_client.open_by_key(os.environ['MASTER_SHEET_KEY'])
        worksheet = spreadsheet.worksheet("Sheet1")
        worksheet.update_cell(target_row_index, target_col_index, value)
    
    except GSpreadException as e:
        message=f"GSpreadException: {e}"
        log_error(message)


"""`/invite_players` command"""
def invite_players_task(body):
    try:
        assert body.get("user_id") in STAFF_BOT_IDS, "スタッフ以外はこのコマンドを使用できません。"
        
        channel_id = body.get("channel_id")
        
        logger.debug(f"channel_id: {channel_id}")
        
        channel_list = get_channel_list()
        logger.debug(f"Channels in this workspace: {channel_list}")
        assert channel_id not in channel_list, f"チャンネル<#{channel_id}>が存在しません。"
        post_message(message=command_confirmation_message(body=body), channel_id=channel_id, user_id=body['user_id'], ephermal=True)
        
        master_data, master_row_index = get_master_data(body, return_row_index=True)
        customer_email = master_data.get("customer_email")
        sales_email = master_data.get("sales_email")
        customer_id = get_user_id_by_email(customer_email)
        sales_id = get_user_id_by_email(sales_email)
        case_id = master_data.get("case_id")
        
        workplace_members = get_worckspace_members()
        logger.debug(f"Members in this workspace: {workplace_members}")
        if customer_id in workplace_members:
            raise SlackApiError(f"Customer <@{customer_id}> is already in this workspace.")
        if sales_id in workplace_members:
            raise SlackApiError(f"Sales <@{sales_id}> is already in this workspace.")
        
        game_info = dict(
            channel_id=channel_id,
            channel_name=body.get("channel_name"),
            customer_email=customer_email,
            sales_email=sales_email,
            customer_id=customer_id,
            sales_id=sales_id,
            case_id = case_id,
            is_liar=str_to_bool(master_data.get("is_liar")),
            master_row_index=int(master_row_index),
            is_started=False,
        )
        
        game_info = game_info_db.save_game_info(**game_info)
        
        if isinstance(game_info, Exception):
            raise game_info
        else:
            logging.info(f"Saved game info: {game_info}")

        
        members = get_channel_members(channel_id)
        logger.debug(f"Members in <#{channel_id}>: {members}")
        if customer_id in members:
            raise SlackApiError(f"Customer(<@{customer_id}>) is already in the channel<#{channel_id}>.")
        if sales_id in members:
            raise SlackApiError(f"Sales(<@{sales_id}>) is already in the channel<#{channel_id}>.")
        
        response = slack_client.conversations_invite(channel=channel_id, users=f"{customer_id},{sales_id}")
        
        # TODO: Workpalceにまだ招待されていない場合のエラー処理
        if not response["ok"] and response["error"] == "already_in_channel":
            for error in response["errors"]:
                if error["error"] == "already_in_channel":
                    message=f"<@{error['user']}>は既にチャンネルに参加しています。"
                    raise SlackApiError(response["error"], message)
        
    except AssertionError as e:
        message=f"AssertionError: {e}"
        log_error(message=message, channel_id=channel_id, body=body, post_to_cor_channel=True)

    except SlackApiError as e:
        message=f"Error inviting user: {e}"
        log_error(message=message, channel_id=channel_id, body=body, post_to_cor_channel=True)
    
    except Exception as e:
        message=str(e)
        log_error(message=message, channel_id=channel_id, body=body)


"""`/start` command"""
def start_task(body):
    try:
        assert body.get("user_id") in STAFF_BOT_IDS, "スタッフ以外はこのコマンドを使用できません。"
        
        channel_id = body.get("channel_id")
        post_message(message=command_confirmation_message(body=body), channel_id=channel_id, user_id=body['user_id'], ephermal=True)
        
        game_info_db.set_started(channel_id)
        game_info = game_info_db.get_game_info(channel_id)
        
        if game_info is None:
            raise AssertionError(f"チャンネル{channel_id}のゲーム情報がDBに存在しません。")
        
        logger.debug(f"Game Info: {game_info}")
        
        customer_id = get_user_id_by_email(game_info.customer_email)
        sales_id = get_user_id_by_email(game_info.sales_email)
        is_liar = game_info.is_liar

        # ルール説明+案件と詐欺師かどうかを通知するメッセージを送信
        post_message(channel_id=channel_id, blocks=start_message_block(customer_id, sales_id))
        time.sleep(1)
        post_message(channel_id=channel_id, blocks=start_message_to_sales_block(case_id=game_info.case_id, is_liar=is_liar), ephermal=True, user_id=game_info.sales_id)
    
    except AssertionError as e:
        message=str(e)
        log_error(message=message, channel_id=channel_id, body=body, post_to_cor_channel=True)
    except AttributeError as e:
        log_error(message=message, body=body)
    except Exception as e:
        log_error(message=message)


"""Regarding to `/lie` or `/trust` command"""
#def add_validation_rules(spreadsheet_id, sheet_id, credentials_path):
#    # Load credentials
#    credentials = service_account.Credentials.from_service_account_file(credentials_path, scopes=['https://www.googleapis.com/auth/spreadsheets'])
#
#    # Build the Google Sheets API client
#    service = build('sheets', 'v4', credentials=credentials)
#
#    # Define the data validation rules
#    rules = [
#        {
#            "range": {
#                "sheetId": sheet_id,
#                "startRowIndex": 1,  # Exclude header row
#                "endRowIndex": 9999,
#                "startColumnIndex": 4,  # lie column (zero-based index)
#                "endColumnIndex": 5
#            },
#            "booleanRule": {
#                "condition": {
#                    "type": "CUSTOM_FORMULA",
#                    "values": [
#                        {
#                            "userEnteredValue": '=IF($C2="customer", $E2=FALSE, TRUE)'
#                        }
#                    ]
#                },
#                "format": {
#                    "backgroundColor": {
#                        "red": 1,
#                        "green": 0,
#                        "blue": 0
#                    }
#                }
#            }
#        },
#        {
#            "range": {
#                "sheetId": sheet_id,
#                "startRowIndex": 1,  # Exclude header row
#                "endRowIndex": 9999,
#                "startColumnIndex": 5,  # suspicious column (zero-based index)
#                "endColumnIndex": 6
#            },
#            "booleanRule": {
#                "condition": {
#                    "type": "CUSTOM_FORMULA",
#                    "values": [
#                        {
#                            "userEnteredValue": '=IF($C2="sales", $F2=FALSE, TRUE)'
#                        }
#                    ]
#                },
#                "format": {
#                    "backgroundColor": {
#                        "red": 1,
#                        "green": 0,
#                        "blue": 0
#                    }
#                }
#            }
#        }
#    ]
#
#    # Set the data validation rules
#    body = {
#        "requests": [
#            {
#                "setDataValidation": {
#                    "rule": rule
#                }
#            } for rule in rules
#        ]
#    }
#
#    try:
#        response = service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=body).execute()
#        print(f"Added validation rules to spreadsheet with ID '{spreadsheet_id}'")
#        return response
#    
#    except HttpError as e:
#        message=f"Error adding validation rules to spreadsheet with ID '{spreadsheet_id}': {e}"
#        log_error(message=message)


def save_result(game_info: GameInfoTable, df):
    try:
        channel_id = game_info.channel_id
        customer_email = game_info.customer_email
        sales_email = game_info.sales_email
        worksheet_name = game_info.channel_name
        
        # 編集権限を付与
        spreadsheet = google_client.open_by_key(os.environ['SPREAD_SHEET_KEY'])
        
        for email in STAFF_BOT_ID_GMAIL + [customer_email, sales_email]:
            share_spreadsheet(spreadsheet=spreadsheet, email=email)
        
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
        
        # add_validation_rules(spreadsheet_id=spreadsheet.id, sheet_id=worksheet.id)
        
        # ミスを防ぐため、フィルターを掛けて、営業役の発話だけを見れるようにする。
        # worksheet.set_basic_filter(filters={'columnName': 'role', 'criteria': {'values': ['sales']}})
        
        return worksheet.url

    except APIError as e:
        message = f"API Error: {e}"
        log_error(message=message, channel_id=channel_id)
        
    except GSpreadException as e:
        message = f"Error saving messages: {e}"
        log_error(message=message, channel_id=channel_id)


def save_messages_task(body, invoked_user_id, judge, reason):
    """
        客役が/lie or /trustでジャッジしたときに呼ばれ、Slackのメッセージ全て読みこんで、
        Googleスプレットシートに'{チャンネル名}_{lie or trust}'のワークシートを追加して保存。
        営業役の人にアノテーションをしてもらうため、

    Args:
        body: Slackのリクエストボディ
        invoked_user_id (str): コマンドを使ったユーザーのID
        judge (Judge): 客が勧誘役が詐欺師かどうか判断したもの. lie or trust.
        reason: 客が勧誘役が詐欺師だと思った理由
    
    Return:
        url(str): 営業役の人に発話が嘘かどうか、アノテーションをしてもらうため、スプレットシートのURLを送る。

    """
    
    try:
        assert invoked_user_id not in STAFF_BOT_IDS, f"スタッフは/lie|/trustコマンドを使わないでください。"
        logger.debug(f"save_messages_task invoked. body: {body}, invoked_user_id: {invoked_user_id}, judge: {judge}")
        
        channel_id = body['channel_id']
        post_message(message=command_confirmation_message(body=body), user_id=invoked_user_id, channel_id=channel_id, ephermal=True)        
        
        game_info = game_info_db.get_game_info(channel_id)
        customer_id = game_info.customer_id
        sales_id = game_info.sales_id
        
        assert game_info.is_started == True, f"まだゲームが始まっていません。 `/lie` `/trust` コマンドはゲーム開始後に使用してください 。"
        assert customer_id == invoked_user_id, f"客役の<@{customer_id}>さん以外は/lie|/trustコマンドを使わないでください。"
        
        post_message(message=judge_receipt_message(user_id=customer_id), channel_id=channel_id)
        game_info_db.set_judge(channel_id=channel_id, judge=judge)
        
        displayed_customer_name = get_displayed_name(customer_id)
        displayed_sales_name = get_displayed_name(sales_id)
        annotations = dict(ts=[], user=[], role=[], message=[], lie=[], suspicious=[])
        cursor = None
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
                    annotations["ts"].append(float(message['ts']))
                    annotations["user"].append(displayed_customer_name if message["user"] == customer_id else displayed_sales_name)
                    annotations["role"].append("customer" if message["user"] == customer_id else "sales")
                    annotations["message"].append(message["text"])
                    annotations["lie"].append(False)
                    annotations["suspicious"].append(False)

            if response['has_more']:
                cursor = response['response_metadata']['next_cursor']
            else:
                break
        
        df = pd.DataFrame.from_dict(annotations).sort_values(by="ts").reset_index(drop=True)
        df['ts'] = df['ts'].apply(unix_to_jst)
        
        worksheet_url = save_result(game_info, df)
        logger.debug(f"worksheet_url: {worksheet_url}")
        game_info_db.set_worksheet_url(channel_id=channel_id, worksheet_url=worksheet_url)
        post_message(blocks=ask_annotation_block(customer_id, sales_id, worksheet_url), channel_id=channel_id)
        save_value_to_master_sheet(target_row_index=game_info.master_row_index, target_col_index=MASTER_JUDGE_COL_INDEX, value=judge)
        save_value_to_master_sheet(target_row_index=game_info.master_row_index, target_col_index=MASTER_REASON_COL_INDEX, value=reason)

        return True

    except SlackApiError as e:
        message=e.response['error']
        log_error(message=message, channel_id=channel_id, body=body)
    
    except AssertionError as e:
        message=str(e)
        log_error(message=message, channel=channel_id, body=body, post_to_cor_channel=True)
        
    except AttributeError as e:
        log_error(message=str(e), channel_id=channel_id, body=body)
    
    except Exception as e:
        log_error(message=str(e), channel_id=channel_id, body=body)


def on_open_spreadsheet_task(body):
    try:
        channel_id = body['container']['channel_id']
        invoked_user_id = body['user']['id']
        
        if invoked_user_id in STAFF_BOT_IDS:
            return
        post_message(blocks=on_open_spreadsheet_block(user_id=invoked_user_id), channel_id=channel_id, user_id=invoked_user_id, ephermal=True)

    except Exception as e:
        log_error(message=str(e), channel_id=channel_id)
        

def on_annotation_done_task(body):
    try:
        channel_id = body['container']['channel_id']
        invoked_user_id = body['user']['id']
        assert invoked_user_id not in STAFF_BOT_IDS, "スタッフは `アノテーション完了ボタン` を押さないでください。"
        
        game_info = game_info_db.get_game_info(channel_id)
        customer_id = game_info.customer_id
        sales_id = game_info.sales_id
        
        assert game_info.judge is not None, f"客役の<@{customer_id}>がまだ `/lie` | `/trust` コマンドを入力していないため、ゲームが終わっていません。\n `/done` コマンドはゲーム終了後に使用してください 。"
        
        if invoked_user_id == customer_id:
            if game_info.customer_done:
                return
            else:
                game_info_db.set_customer_done(channel_id)
        elif invoked_user_id == sales_id:
            if game_info.sales_done:
                return
            else:
                game_info_db.set_sales_done(channel_id)
        else:
            raise AssertionError(f"ゲームに参加していないユーザーは`/done`コマンドを使わないでください。")
        
        logger.error(f"game_info: {game_info}")
        game_info = game_info_db.get_game_info(channel_id)
        
        post_message(channel_id=channel_id, message=thank_you_for_annotation_message(invoked_user_id), user_id=invoked_user_id, ephermal=True)
        # TODO: 編集権限をここで剥奪する。
        
        # 二人とも終わっていれば、結果を発表する。
        logger.debug(f"game_info: {game_info}")
        logger.debug(f"customer_done: {game_info.customer_done}, sales_done: {game_info.sales_done}")
        if game_info.customer_done and game_info.sales_done:
            judge = game_info.judge
            is_liar = game_info.is_liar
            post_message(blocks=final_result_announcement_block(customer_id, sales_id, is_liar, judge), channel_id=channel_id)
            save_value_to_master_sheet(target_row_index=game_info.master_row_index, target_col_index=MASTER_FINISH_COL_INDEX, value=True)

    except AssertionError as e:
        message=str(e)
        log_error(message=message, channel_id=channel_id, post_to_cor_channel=True)

    except AttributeError as e:
        log_error(message=str(e), channel_id=channel_id)