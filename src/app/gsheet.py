import setting
import logging
import pandas as pd
import os
import gspread
from gspread_dataframe import set_with_dataframe
from gspread_formatting import DataValidationRule, BooleanCondition, set_data_validation_for_cell_range, batch_updater, cellFormat
from gspread_formatting.dataframe import format_with_dataframe, BasicFormatter
from oauth2client.service_account import ServiceAccountCredentials
from src.db.game_info import GameInfoTable

from src.app.slack import SlackClientWrapper
slack_client = SlackClientWrapper()

logger = logging.getLogger("slack_game_master")
logger.setLevel(logging.DEBUG)


class GSheetClientWrapper:
    def __init__(self):
        scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(setting.GCP_SERVICE_ACCOUNT_KEY, scope)
        self.client = gspread.authorize(creds)

    def get_master_data(self, body, return_row_index=False):
        channel_name = body.get("channel_name")
        worksheet_name = "Sheet1"
        spreadsheet = self.client.open_by_key(setting.MASTER_SHEET_KEY)

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

    def get_case_data(self, case_id) -> dict or None:
        """
        Retrieve the case data for a given case ID from the spreadsheet.

        Args:
            case_id (str): The case ID to search for.

        Returns:
            dict or None: A dictionary containing the case data if a matching case ID is found,
                or None if no match is found. The dictionary structure is as follows:

                {
                    'case_id': str,
                    'description_url': str,
                    'customer_scenario': str,
                    'liar_scenario': str,
                    'honest_scenario': str
                }
        """
        sheet = self.client.open_by_key(setting.MASTER_SHEET_KEY).worksheet("case")
        logger.debug(f"sheet: {sheet}")
        records = sheet.get_all_records()
        for record in records:
            if record['case_id'] == case_id:
                return record
        raise ValueError(f"Case ID {case_id} not found in spreadsheet.")

    def save_value_to_master_sheet(self, target_row_index, target_col_index, value):
        spreadsheet = self.client.open_by_key(os.environ['MASTER_SHEET_KEY'])
        worksheet = spreadsheet.worksheet("Sheet1")
        worksheet.update_cell(target_row_index, target_col_index, value)

    def save_dialogue(self, game_info: GameInfoTable, df: pd.DataFrame):
        sheet = self.client.open_by_key(setting.SPREAD_SHEET_KEY)

        for email in setting.STAFF_BOT_EMALS + [game_info.customer_email, game_info.sales_email]:
            worksheet = sheet.worksheet(email)
            worksheet.append_row(df.loc[0].values.tolist())

        # 既に同じ名前のworksheetが存在すれば、それを上書きする。
        worksheet_list = sheet.worksheets()
        worksheet = None
        for ws in worksheet_list:
            if ws.title == game_info.channel_id:
                worksheet = ws
                break
        if worksheet is None:
            worksheet = sheet.add_worksheet(title=game_info.channel_id, rows=10, cols=4)
        worksheet.clear()
        set_with_dataframe(worksheet, df)

        # ヘッダーのフォーマッティング
        header_formatter = BasicFormatter(
            freeze_headers=True,
        )
        format_with_dataframe(worksheet, df, header_formatter)

        with batch_updater(worksheet.spreadsheet) as batch:
            message_column_formatting = cellFormat(
                horizontalAlignment="LEFT",
                wrapStrategy="WRAP"
            )
            batch.set_column_width(worksheet, 'D:D', 700)
            batch.set_column_width(worksheet, 'G:G', 500)
            batch.format_cell_range(worksheet, 'D:D', message_column_formatting)
            batch.format_cell_range(worksheet, 'G:G', message_column_formatting)

        lie_col_range = f'E2:E{len(df.index) + 1}'
        suspicious_col_range = f'F2:F{len(df.index) + 1}'
        reason_col_range = f'G2:G{len(df.index) + 1}'

        # lieカラムのTrue, Falseをチェックボックに
        validation_rule = DataValidationRule(
            BooleanCondition('BOOLEAN', ['TRUE', 'FALSE']),
            showCustomUi=True
        )
        set_data_validation_for_cell_range(worksheet, lie_col_range, validation_rule)
        set_data_validation_for_cell_range(worksheet, suspicious_col_range, validation_rule)

        # 編集制限
        # lie/suspiciousカラムに編集制限をかける

        if game_info.is_liar:  # 詐欺師の場合のみ嘘の発話をアノテーション出来る
            worksheet.add_protected_range(worksheet, lie_col_range, setting.STAFF_BOT_ID_GMAILS + [game_info.sales_email])
            worksheet.add_protected_range(worksheet, reason_col_range, setting.STAFF_BOT_ID_GMAILS + [game_info.sales_email])
        worksheet.add_protected_range(worksheet, suspicious_col_range, setting.STAFF_BOT_ID_GMAILS + [game_info.customer_email])
        worksheet.add_protected_range(worksheet, reason_col_range, setting.STAFF_BOT_ID_GMAILS + [game_info.customer_email])

        other_cols_range = f"A1:D{len(df.index) + 1}"
        header_range = "A1:F1"

        worksheet.add_protected_ranges(worksheet, other_cols_range, setting.STAFF_BOT_ID_GMAILS)
        worksheet.add_protected_ranges(worksheet, header_range, setting.STAFF_BOT_ID_GMAILS)

        return worksheet.url

    def share_spreadsheet(self, sheet: gspread.Spreadsheet, email: str):
        sheet.share(email, perm_type='user', role='writer', with_link=False, notify=False)
        logging.info(f"Shared spreadsheet with {email}")
