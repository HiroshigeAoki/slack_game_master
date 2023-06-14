import os
import json
import logging
from datetime import datetime, timezone, timedelta
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.errors import SlackApiError
from src.app.messages import ask_reason_block

import setting
from src.app.worker import save_messages_task, invite_players_task, start_task, on_open_spreadsheet_task, on_annotation_done_task

os.makedirs(setting.LOG_DIR, exist_ok=True)
logging.basicConfig(filename=f'{setting.LOG_DIR}/app.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
logging.Formatter.converter = lambda *args: datetime.now(tz=timezone(timedelta(hours=+9), 'JST')).timetuple()

logger = logging.getLogger(__name__)

app = AsyncApp(
    token=setting.SLACK_BOT_TOKEN,
    signing_secret=setting.SLACK_SIGNING_SECRET,
)


@app.command("/invite_players")
async def handle_invite_command(ack, body):
    try:
        await ack()
        logger.debug(f"/invite_players, body: {body}")
        invite_players_task.delay(body)
    except SlackApiError as e:
        raise e


@app.command("/start")
async def handle_start_command(ack, body):
    try:
        await ack()
        start_task.delay(body)
    except SlackApiError as e:
        raise e


async def open_ask_reason_modal(client, trigger_id, channel_id, judge):
    modal_view = ask_reason_block(channel_id, judge)
    response = await client.views_open(trigger_id=trigger_id, view=modal_view)
    logger.debug(f"views.open response: {response}")


# 客役のjudgeを受け取り、Googleスプレットシートに保存して、ユーザーにURLを返して、入力を促す。
async def save_messages(body, judge, reason):
    logger.debug(f"/{judge}, reason: {reason}, body: {body}")
    invoked_user_id = body.get("user_id")
    save_messages_task.delay(body, invoked_user_id, judge, reason)


@app.command("/lie")
async def handle_lie_command(ack, body, client):
    await ack()
    judge = "lie"
    channel_id = body.get("channel_id")
    await open_ask_reason_modal(client, body.get("trigger_id"), channel_id=channel_id, judge=judge)


@app.command("/trust")
async def handle_trust_command(ack, body, client):
    await ack()
    judge = "trust"
    channel_id = body.get("channel_id")
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
    action_id = body.get("actions")[0].get("action_id")
    logger.debug(f"on_open_spreadsheet_task, body: {body}, action_id: {action_id}")
    
    on_open_spreadsheet_task(body)


@app.action("annotation_done")
async def on_annotation_done(body, ack):
    await ack()
    action_id = body.get("actions")[0].get("action_id")
    logger.debug(f"on_annotation_done_task, body: {body}, action_id: {action_id}")
    
    on_annotation_done_task(body)


async def main():
    handler = AsyncSocketModeHandler(app=app, app_token=setting.SLACK_APP_TOKEN)
    await handler.start_async()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

