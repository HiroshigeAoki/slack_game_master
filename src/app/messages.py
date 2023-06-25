import json
import logging
import setting
from src.app.gsheet import GSheetClientWrapper

logger = logging.getLogger("slack_game_master")
logger.setLevel(logging.DEBUG)

gsheet_client = GSheetClientWrapper()

GENERAL_CHANNEL_ID = "C04LWLAE5SM"
INCENTIVE = "ハーゲンダッツ"


def start_message_block(customer_id, sales_id):
    outline_section = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                f"これから「詐欺ゲーム」が始まります！\n"
                "このゲームは、客役が、投資案件を宣伝する営業役との対話を通じて、\n"
                "営業役が詐欺師かどうかをジャッジするゲームです。\n"
                "このゲームでは、SNSなどでテキストでやり取りしているケースを想定してます。\n\n"
                f"今回<@{customer_id}>は客役、<@{sales_id}>は営業役です。\n"
                "ゲームの進め方については、ダイレクトメッセージにて別途お送りします。\n"
            )
        }
    }
    
    note = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                "*注意事項*\n"
                f"• なにかご質問があれば、このチャンネルではなく、<@{setting.STAFF_ID}>にダイレクトメッセージを送ってください。\n\n"
            )
        }
    }

    start_message_block = [outline_section, note]
    
    return start_message_block


def role_instruction_block(channel_id, case_id, role, is_liar):
    
    case_record = gsheet_client.get_case_data(case_id=case_id)
    role_instruction_message = (
        f"<#{channel_id}>\n"
        "*ゲームの進め方*\n"
    )
    if role == "customer":
        role_instruction_message += (
            f"{case_record.get('customer_scenario')}\n"
            f"`客役` のゲーム進め方は、<{setting.CUSTOMER_INSTRUCTION}|*このGoogleドキュメント*>をご確認ください。\n"
        )
    elif role == "sales":
        if is_liar:
            role_instruction_message += (
                "今回あなたは詐欺師です。\n"
                f"{case_record.get('liar_scenario')}\n"
                f"`営業役(詐欺師)` のゲーム進め方は、<{setting.SALES_LIAR_INSTRUCTION}|*このGoogleドキュメント*>をご確認ください。\n"
            )
        else:
            role_instruction_message += (
                "今回あなたは詐欺師ではありません。\n"
                f"{case_record.get('honest_scenario')}\n"
                f"`営業役(詐欺師ではない)` のゲーム進め方は、<{setting.SALES_HONEST_INSTRUCTION}|*このGoogleドキュメント*>をご確認ください。\n"
            )
    
    role_instruction_section = {
        "type": "section", 
        "text": {
            "type": "mrkdwn",
            "text": role_instruction_message
        },
    }
    
    case_description_section = {
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": (
                "*営業案件*\n"
                f"<{case_record.get('description_url')}|*この営業案件*>をご確認ください(相手にはこの内容は共有されていません。)\n"
            )
        },
    }
    
    return [role_instruction_section, case_description_section]


def judge_receipt_message(user_id):
    return f"<@{user_id}> ジャッジを受け付けました。ありがとうございます。\n スプレッドシートを作成しますのでしばらくお待ち下さい。"


def ask_annotation_block(worksheet_url, role="customer"):
    col_name = "suspicious" if role == "customer" else "lie"
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "スプレッドシートにアノテーションをお願いします。 \n"\
                    f"*アノテーション先*: `{col_name}` カラム\n"
                    "両者のアノテーションが完了したら、ゲーム結果をお伝えします。"\
                )
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":googlespreadsheet: スプレッドシートを開く",
                    "emoji": True
                },
                "url": worksheet_url,
                "action_id": "open_spreadsheet"
            }
        },
    ]


def ask_reason_block(channel_id, judge):
    judge_text = "詐欺師" if judge == "lie" else "詐欺師ではない"
    return {
        "title": {
            "type": "plain_text",
            "text": "判定の根拠を教えて下さい"
        },
        "submit": {
            "type": "plain_text",
            "text": "Submit"
        },
        "type": "modal",
        "callback_id": "message_submission",
        "private_metadata": json.dumps({
            "judge": judge,
            "channel_id": f"{channel_id}" 
        }),
        "blocks": [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Selected:* {judge_text}"  # Show the selected judge value
                }
            },
            {
                "type": "input",
                "block_id": "message_input_block",
                "label": {
                    "type": "plain_text",
                    "text": "判定の根拠"
                },
                "element": {
                    "type": "plain_text_input",
                    "action_id": "message",
                    "min_length": 10,
                    "placeholder": {
                        "type": "plain_text",
                        "text": "10単語以上入力してください"
                    }
                }
            }
        ]
    }


def on_open_spreadsheet_block(user_id):
    return [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": (

                            f"""
                            <@{user_id}>アノテーション完了後、 `アノテーション完了` ボタンを押してください。 \
                            """
                        )
                    },
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {
                                "type": "plain_text",
                                "text": "アノテーション完了",
                                "emoji": True
                            },
                            "action_id": "annotation_done",
                            "style": "primary",
                        }
                    ]
                }
    ]


def thank_you_for_annotation_message(user_id):
    return f"<@{user_id}>アノテーション完了です。お疲れさまでした。"


def command_confirmation_message(body):
    return f"<@{body['user_id']}> `{body['command']}` を受け付けました。しばらくお待ち下さい。"


def final_result_announcement_block(customer_id, sales_id, is_liar, judge):
    if is_liar:
        if judge=='lie':
            RESULT_MESSAGE = f"<@{customer_id}>が{INCENTIVE}を獲得しました。\n<@{sales_id}>を正しく詐欺師と判断しました。おめでとうございます！"
        elif judge=='trust':
            RESULT_MESSAGE = f"<@{sales_id}>が{INCENTIVE}を獲得しました。 \n<@{customer_id}>をうまく欺くことに成功しました。おめでとうございます！"
    else:
        if judge=='lie':
            RESULT_MESSAGE = f"今回{INCENTIVE}は両者ともお預けです。 \n<@{sales_id}>は詐欺師と怪しまれ、<@{customer_id}>は詐欺師ではないのに詐欺師と判定しました。残念。"
        elif judge=='trust':
            RESULT_MESSAGE = f"<@{customer_id}>と<@{sales_id}>が{INCENTIVE}を獲得しました。\n<@{customer_id}>は正しく詐欺師ではないこと判断し、<@{sales_id}>は相手に信じてもらうことができました。おめでとうございます！"
    
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*結果発表!*\n"
                    f"{RESULT_MESSAGE}"
                )
            }
        }
    ]