import os
import logging
from datetime import datetime, timezone, timedelta
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_sdk.errors import SlackApiError

import setting
from app.worker import save_messages_task, invite_players_task, start_task, on_open_spreadsheet_task, on_annotation_done_task

os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename='./logs/app.log', level=logging.DEBUG, format='%(asctime)s %(levelname)s: %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
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
        invite_players_task(body)
    except SlackApiError as e:
        raise e


@app.command("/start")
async def handle_start_command(ack, body):
    try:
        await ack()
        start_task(body)
    except SlackApiError as e:
        raise e


# 客役のjudgeを受け取り、Googleスプレットシートに保存して、ユーザーにURLを返して、入力を促す。
async def save_messages(body, judge):
    logger.debug(f"/{judge}, body: {body}")
    invoked_user_id = body.get("user_id")
    save_messages_task(body, invoked_user_id, judge)


@app.command("/lie")
async def handle_lie_command(ack, body):
    await ack()
    judge = "lie"
    await save_messages(body, judge)


@app.command("/trust")
async def handle_trust_command(ack, body):
    await ack()
    judge = "trust"
    await save_messages(body, judge)


@app.action("open_spreadsheet")
async def on_open_spreadsheet(body, ack):
    await ack()
    action_id = body.get("actions")[0].get("action_id")
    logger.debug(f"block_actions, body: {body}, action_id: {action_id}")
    
    on_open_spreadsheet_task(body)


@app.action("annotation_done")
async def on_annotation_done(body, ack):
    await ack()
    action_id = body.get("actions")[0].get("action_id")
    logger.debug(f"block_actions, body: {body}, action_id: {action_id}")
    
    on_annotation_done_task(body)


async def main():
    handler = AsyncSocketModeHandler(app=app, app_token=setting.SLACK_APP_TOKEN)
    await handler.start_async()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

