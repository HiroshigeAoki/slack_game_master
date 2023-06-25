import os
import logging
import traceback
import setting
import pandas as pd
from celery import Celery
from celery.utils.log import get_task_logger
from slack_sdk.errors import SlackApiError
from src.app.utils import unix_to_jst
from src.app.messages import (start_message_block, role_instruction_block,
                                judge_receipt_message, ask_annotation_block, 
                                command_confirmation_message, thank_you_for_annotation_message, 
                                on_open_spreadsheet_block, final_result_announcement_block)
from src.db.game_info import GameInfoDB
from src.app.slack import SlackClientWrapper
from src.app.gsheet import GSheetClientWrapper
from src.app.utils import unix_to_jst, str_to_bool
from logger_config import setup_loggers

slack_client = SlackClientWrapper()
gsheet_client = GSheetClientWrapper()

celery = Celery(__name__)
celery.conf.broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379")
celery.conf.result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379")

logger = get_task_logger(__name__)
logger = setup_loggers(logger)

game_info_db = GameInfoDB().get_instance()

MASTER_JUDGE_COL_INDEX = 5
MASTER_REASON_COL_INDEX = 6
MASTER_FINISH_COL_INDEX = 8
CELERY_TIME_LIMIT = 300

def handle_errors(func):
    def wrapper(*args, **kwargs):
        body = args[0]
        channel_id = body.get("channel_id", None)
        command = body.get("command", None)
        
        try:
            return func(*args, **kwargs)

        except Exception as e:
            message = f"Error occurred in function {func.__name__}: {e}"
            if command:
                message = f"`{command}` " + message
            if channel_id:
                message = f"<#{channel_id}>" + message
                
            logger.error(message)
            logger.error(traceback.format_exc())

    return wrapper


"""`/invite_players` command"""
@celery.task(name="invite_players_task", time_limit=CELERY_TIME_LIMIT)
@handle_errors
def invite_players_task(body):
    channel_id = body.get("channel_id")
    
    logger.debug(f"channel_id: {channel_id}")
    
    channel_id_list = slack_client.get_channel_id_list()
    logger.debug(f"Channel ids in this workspace: {channel_id_list}")
    if channel_id not in channel_id_list:
        raise ValueError(f"チャンネル<#{channel_id}>が存在しません。作成してください。\n存在するチャンネルのID: {channel_id_list}")
    slack_client.post_message(message=command_confirmation_message(body=body), channel_id=channel_id, user_id=body['user_id'], ephermal=True)
    
    master_data, master_row_index = gsheet_client.get_master_data(body, return_row_index=True)
    customer_email = master_data.get("customer_email")
    sales_email = master_data.get("sales_email")
    customer_id = slack_client.get_user_id_by_email(customer_email)
    sales_id = slack_client.get_user_id_by_email(sales_email)
    case_id = master_data.get("case_id")
    
    workplace_members = slack_client.get_worckspace_members()
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
        logger.info(f"Saved game info: {game_info}")

    members = slack_client.get_channel_members(channel_id)
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


"""`/start` command"""
@celery.task(name="start_task", time_limit=CELERY_TIME_LIMIT)
@handle_errors
def start_task(body):
    logger.debug(f"body: {body}")
    
    channel_id = body.get("channel_id")
    slack_client.post_message(message=command_confirmation_message(body=body), channel_id=channel_id, user_id=body['user_id'], ephermal=True)
    
    game_info_db.set_started(channel_id)
    game_info = game_info_db.get_game_info(channel_id)
    
    logger.debug(f"Game Info: {game_info}")
    
    slack_client.post_message(channel_id=channel_id, blocks=start_message_block(customer_id=game_info.customer_id, sales_id=game_info.sales_id))
    
    slack_client.send_direct_message(user_id=game_info.customer_id, blocks=role_instruction_block(channel_id=channel_id, case_id=game_info.case_id, is_liar=game_info.is_liar, role="customer"))
    slack_client.send_direct_message(user_id=game_info.sales_id, blocks=role_instruction_block(channel_id=channel_id, case_id=game_info.case_id, is_liar=game_info.is_liar, role="sales"))


@celery.task(name="save_messages_task", time_limit=CELERY_TIME_LIMIT)
@handle_errors
def save_messages_task(body, judge, reason):
    """
        客役が/lie or /trustでジャッジしたときに呼ばれ、Slackのメッセージ全て読みこんで、
        Googleスプレットシートに'{チャンネル名}_{lie or trust}'のワークシートを追加して保存。
        営業役の人にアノテーションをしてもらうため、

    Args:
        body: Slackのリクエストボディ
        judge (Judge): 客が勧誘役が詐欺師かどうか判断したもの. lie or trust.
        reason: 客が勧誘役が詐欺師だと思った理由
    
    Return:
        url(str): 営業役の人に発話が嘘かどうか、アノテーションをしてもらうため、スプレットシートのURLを送る。

    """
    
    logger.debug(f"save_messages_task invoked. body: {body}, judge: {judge}")
    
    channel_id = body['channel_id']
    invoked_user_id = body.get("user_id")
    slack_client.post_message(message=command_confirmation_message(body=body), user_id=invoked_user_id, channel_id=channel_id, ephermal=True)        
    
    game_info = game_info_db.get_game_info(channel_id)
    customer_id = game_info.customer_id
    sales_id = game_info.sales_id
    
    slack_client.post_message(message=judge_receipt_message(user_id=customer_id), channel_id=channel_id)
    game_info_db.set_judge(channel_id=channel_id, judge=judge)
    
    displayed_customer_name = slack_client.get_displayed_name(customer_id)
    displayed_sales_name = slack_client.get_displayed_name(sales_id)
    annotations = dict(ts=[], user=[], role=[], message=[], lie=[], suspicious=[], reason=[])
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
                annotations["reason"].append("")

        if response['has_more']:
            cursor = response['response_metadata']['next_cursor']
        else:
            break
    
    df = pd.DataFrame.from_dict(annotations).sort_values(by="ts").reset_index(drop=True)
    df['ts'] = df['ts'].apply(unix_to_jst)
    logger.debug(f"df: {df}")
    
    worksheet_url = gsheet_client.save_dialogue(game_info, df)
    logger.debug(f"worksheet_url: {worksheet_url}")
    game_info_db.set_worksheet_url(channel_id=channel_id, worksheet_url=worksheet_url)

    slack_client.post_message(blocks=ask_annotation_block(worksheet_url, role="customer"), channel_id=game_info.channel_id, ephermal=True, user_id=customer_id)
    if game_info.is_liar: # 営業訳のアノテーションは、詐欺師でない場合のみ
        slack_client.post_message(blocks=ask_annotation_block(worksheet_url, role="sales"), channel_id=game_info.channel_id, ephermal=True, user_id=sales_id)

    gsheet_client.save_value_to_master_sheet(target_row_index=game_info.master_row_index, target_col_index=MASTER_JUDGE_COL_INDEX, value=judge)
    gsheet_client.save_value_to_master_sheet(target_row_index=game_info.master_row_index, target_col_index=MASTER_REASON_COL_INDEX, value=reason)

    return True


@celery.task(name="on_open_spreadsheet_task", time_limit=CELERY_TIME_LIMIT)
@handle_errors
def on_open_spreadsheet_task(body):
    channel_id = body['container']['channel_id']
    invoked_user_id = body['user']['id']
    
    if invoked_user_id in setting.STAFF_BOT_IDS:
        return
    slack_client.post_message(blocks=on_open_spreadsheet_block(user_id=invoked_user_id), channel_id=channel_id, user_id=invoked_user_id, ephermal=True)


@celery.task(name="on_annotation_done_task", time_limit=CELERY_TIME_LIMIT)
@handle_errors
def on_annotation_done_task(body):
    channel_id = body['container']['channel_id']
    invoked_user_id = body['user']['id']
    assert invoked_user_id not in setting.STAFF_BOT_IDS, "スタッフは `アノテーション完了ボタン` を押さないでください。"
    
    game_info = game_info_db.get_game_info(channel_id)
    customer_id = game_info.customer_id
    sales_id = game_info.sales_id
    
    assert game_info.judge is not None, f"客役の<@{customer_id}>がまだ `/lie` | `/trust` コマンドを入力していないため、ゲームが終わっていません。\n `/done` コマンドはゲーム終了後に使用してください 。"
    logger.info(f"game_info: {game_info}")
    
    # 営業役が詐欺師でない場合、アノテーションを要求しない。
    if not game_info.is_liar:
        game_info_db.set_sales_done(channel_id)
    
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
    
    logger.debug(f"customer_done: {game_info.customer_done}, sales_done: {game_info.sales_done}")
    game_info = game_info_db.get_game_info(channel_id)
    
    slack_client.post_message(channel_id=channel_id, message=thank_you_for_annotation_message(invoked_user_id), user_id=invoked_user_id, ephermal=True)
    # TODO: 編集権限をここで剥奪する。
    
    # 二人とも終わっていれば、結果を発表する。
    logger.debug(f"game_info: {game_info}")
    logger.debug(f"customer_done: {game_info.customer_done}, sales_done: {game_info.sales_done}")
    if game_info.customer_done and game_info.sales_done:
        judge = game_info.judge
        is_liar = game_info.is_liar
        slack_client.post_message(blocks=final_result_announcement_block(customer_id, sales_id, is_liar, judge), channel_id=channel_id)
        gsheet_client.save_value_to_master_sheet(target_row_index=game_info.master_row_index, target_col_index=MASTER_FINISH_COL_INDEX, value=True)
