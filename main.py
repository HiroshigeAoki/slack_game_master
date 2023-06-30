import json
import logging
from slack_sdk import WebClient
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from src.app.messages import ask_reason_block
import setting
from src.app.worker import save_messages_task, invite_players_task, start_task, on_open_spreadsheet_task, on_annotation_done_task
from src.db.game_info import GameInfoDB
from logger_config import setup_loggers
from src.app.messages import access_denied_message, no_game_info_message, game_not_started_message, wrong_user_message

game_info_db = GameInfoDB().get_instance()

app = AsyncApp(
    token=setting.SLACK_BOT_TOKEN,
    signing_secret=setting.SLACK_SIGNING_SECRET,
)
    
logger = logging.getLogger(__name__)
logger = setup_loggers(logger)


# validation
async def validate_command_usage(body, client: WebClient):
    channel_id = body.get("channel_id")
    invoked_user_id = body.get("user_id")
    command = body.get("command")
    game_info = game_info_db.get_game_info(channel_id)
    logger.debug(f"validate_command_usage, channel_id: {channel_id}, invoked_user_id: {invoked_user_id}, command: {command}, game_info: {game_info}")
    
    if command == "/invite_players" or command == "/start":
        if invoked_user_id not in setting.STAFF_BOT_IDS:
            await client.chat_postEphemeral(channel=channel_id, user=invoked_user_id, text=access_denied_message(invoked_user_id))
            return False
    
    if command == "/start":
        if game_info == None:
            await client.chat_postEphemeral(channel=channel_id, user=invoked_user_id, text=no_game_info_message(invoked_user_id))
    
    if command == "/lie" or command == "/trust":
        if game_info == None:
            await client.chat_postEphemeral(channel=channel_id, user=invoked_user_id, text=game_not_started_message(invoked_user_id))
            return False        
        elif game_info.customer_id != invoked_user_id:
            await client.chat_postEphemeral(channel=channel_id, user=invoked_user_id, text=wrong_user_message(invoked_user_id, game_info.customer_id))
            return False
        elif game_info.is_started == False:
            await client.chat_postEphemeral(channel=channel_id, user=invoked_user_id, text=game_not_started_message(invoked_user_id))
            return False
    return True



@app.command("/invite_players")
async def handle_invite_command(ack, body, client):
    try:
        await ack()
        logger.debug(f"/invite_players, body: {body}")
        if await validate_command_usage(body=body, client=client):
            invite_players_task.delay(body)
    except Exception as e:
        logger.error(f"Failed to invite players: {e}")


@app.command("/start")
async def handle_start_command(ack, body, client):
    try:
        await ack()
        logger.debug(f"/start, body: {body}")
        if await validate_command_usage(body=body, client=client):
            start_task.delay(body)
    except Exception as e:
        logger.error(f"Failed to start: {e}")


async def open_ask_reason_modal(client, trigger_id, channel_id, judge):
    modal_view = ask_reason_block(channel_id, judge)
    response = await client.views_open(trigger_id=trigger_id, view=modal_view)
    logger.debug(f"views.open response: {response}")


# 客役のjudgeを受け取り、Googleスプレットシートに保存して、ユーザーにURLを返して、入力を促す。
async def save_messages(body, judge, reason):
    logger.debug(f"/{judge}, reason: {reason}, body: {body}")
    save_messages_task(body, judge, reason)


@app.command("/lie")
async def handle_lie_command(ack, body, client):
    await ack()
    judge = "lie"
    channel_id = body.get("channel_id")
    if await validate_command_usage(body, client):    
        await open_ask_reason_modal(client, body.get("trigger_id"), channel_id=channel_id, judge=judge)


@app.command("/trust")
async def handle_trust_command(ack, body, client):
    await ack()
    judge = "trust"
    channel_id = body.get("channel_id")
    if await validate_command_usage(body, client):
        await open_ask_reason_modal(client, body.get("trigger_id"), channel_id=channel_id, judge=judge)


@app.view("message_submission")
async def handle_view_submission(ack, body, view):
    await ack()
    reason = view["state"]["values"]["message_input_block"]["message"]["value"]
    # TODO; 入力のチェックをする
    private_metadata = json.loads(view["private_metadata"]) 
    judge = private_metadata["judge"]
    channel_id = private_metadata["channel_id"]
    body["channel_id"] = channel_id
    body["user_id"] = body["user"]["id"]
    body["command"] = judge
    logger.debug(f"view_submission, body: {body}, view: {view}, reason: {reason}, judge: {judge}, channel_id: {channel_id}")

    await save_messages(body, judge, reason)


@app.action("open_spreadsheet")
async def on_open_spreadsheet(body, ack):
    await ack()
    game_info = game_info_db.get_game_info(body.get("channel").get("id"))
    logger.debug(f"on_open_spreadsheet_task, body: {body}, action_id: {body.get('actions')[0].get('action_id')}")
    invoked_user_id = body['user']['id']
    if invoked_user_id == game_info.customer_id and invoked_user_id not in setting.STAFF_BOT_IDS:
        logger.debug(f"invoke_user_id: {invoked_user_id}, sales_id: {game_info.sales_id}, is_liar: {game_info.is_liar}")
        on_open_spreadsheet_task.delay(body)
    elif invoked_user_id == game_info.sales_id and game_info.is_liar:
        logger.debug(f"invoke_user_id: {invoked_user_id}, sales_id: {game_info.sales_id}, is_liar: {game_info.is_liar}")
        on_open_spreadsheet_task.delay(body)


@app.action("annotation_done")
async def on_annotation_done(body, ack):
    await ack()
    action_id = body.get("actions")[0].get("action_id")
    logger.debug(f"on_annotation_done_task, body: {body}, action_id: {action_id}")
    
    on_annotation_done_task.delay(body)


async def main():
    handler = AsyncSocketModeHandler(app=app, app_token=setting.SLACK_APP_TOKEN)
    await handler.start_async()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
