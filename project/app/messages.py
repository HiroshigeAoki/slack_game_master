from app.utils import load_case

INCENTIVE="ハーゲンダッツ"
GENERAL_CNANNEL_ID = "C04LWLAE5SM"
#TODO: 営業案件をいくつか定義して、スプレッドシートで使う営業案件を決めるようにする。


def start_message_block(customer_id, sales_id):
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"プレイヤーの皆さん、こんにちは！これから「（仮）投資ゲーム」が始まります！\n"
                    "このゲームは、客役が、架空の営業案件を宣伝する営業役との対話を通じて、営業役が詐欺師かどうかをジャッジするゲームです。\n"
                    "今回は、SNSなどでテキストでやり取りしているケースを想定してます。\n\n"
                    "ゲームの流れと、報酬については以下の通りです。"
                )
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*ゲームの流れ*\n"
                    "1. 役職の割当\n"
                    f"\t• 客役: <@{customer_id}>、営業役: <@{sales_id}>\n"
                    f"2. <@{sales_id}>に、営業案件と詐欺師かどうかを通知\n"
                    f"\t• このメッセージの後に<@{sales_id}>に見えるようにして送ります。\n"
                    "3. 対話開始\n"
                    "\t• 怪しい発話・嘘の発話の記録もお願いします \n"
                    "\t• 記録するもの： \n"
                    "\t\t• 客役: 営業役の発話で怪しいと思った発話。\n"
                    "\t\t• 営業役: 自身の嘘の発話。\n"
                    "\t• 記録方法: <https://slack.zendesk.com/hc/article_attachments/1500012103001/save_files.png|ブックマークマークを押して、その発話をSave Itemに追加。>\n"
                    "4. 対話終了後、客役(<@{customer_id}>)は営業役が詐欺師かどうかを対話を通じて判断\n"
                    "\t• 詐欺師だと思ったら `/lie` コマンドを入力。"
                    "\t• 詐欺師ではないと思ったら `/trust` コマンドを入力。\n"
                    "\t• 判断の根拠の入力もお願いします。\n"
                    "5. Googleスプレッドシートにアノテーション\n"
                    "\t• 客役：記録しておいた営業役の怪しい発話の `suspicious` カラムにチェック。\n"
                    "\t• 営業役：記録しておいた自身が嘘をついた発話の `lie` カラムにチェック。\n"
                    "\t• 入力が完了したらそれぞれ、 `アノテーション完了` ボタンを押してください。\n"
                    "6. 両者のアノテーション完了後、結果を発表。\n"
                )
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*報酬*\n"
                    f"• このゲームの報酬は、{INCENTIVE}です。\n"
                    f"• アノテーション終了後に結果を発表します。\n"
                    
                    f"獲得条件:\n"
                    f"• 客役：客役は正しく詐欺師かそうでないかを正しく見抜けた時。\n"
                    f"• 営業役：客役に信じてもらえた時。"
                )
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*注意事項*\n"
                    f"• なにかご質問があれば、このチャンネルではなく、<#{GENERAL_CNANNEL_ID}>チャンネルでスタッフまでお声掛けください。 \n\n"
                    f"それでは、ゲームを始めます！{INCENTIVE}獲得を目指して、楽しんでプレイしてください！"
                )
            },
        },
    ]


def start_message_to_sales_block(case_id, is_liar):
    LIAR_MESSAGE = "あなたは `詐欺師` です。今回の投資先として紹介するサービスは実際には開発をしていません。相手に案件が怪しまれないように、あたかも自分たちが開発しているかのように話し、投資を受けられるよう信頼を得てください。"
    HONEST_MESSAGE = "あなたは詐欺師ではありません。相手に怪しまれないように、うまく話を進め、投資を受けられるよう信頼を得てください。"
    case_url = load_case(case_id)    
    
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*投資案件と詐欺師かどうか* \n"
                    f"{LIAR_MESSAGE if is_liar else HONEST_MESSAGE} \n"
                )
            },
            "accessory":{
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": ":page_facing_up: 投資案件",
                    "emoji": True
                },
                "url": case_url
            }
        },
    ]



def judge_receipt_message(user_id):
    return f"<@{user_id}> ジャッジを受け付けました。ありがとうございます。\n スプレッドシートを作成しますので少々お待ち下さい。"


def ask_annotation_block(customer_id, sales_id, worksheet_url):
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "スプレッドシートにアノテーションをお願いします。 \n"\
                    "*アノテーション先*\n"
                    f"• <@{customer_id}>: `suspicious` カラム\n"
                    f"• <@{sales_id}>: `lie` カラム\n\n"\
                    "両者のアノテーションが完了したら、ゲーム結果をお伝えします。"\
                )
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "スプレッドシートを開く",
                    "emoji": True
                },
                "url": worksheet_url,
                "action_id": "open_spreadsheet"
            }
        },
    ]


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
    return f"<@{body['user_id']}> `{body['command']}` を受け付けました。少々お待ち下さい。"


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