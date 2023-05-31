import datetime
import pytz
import json
import setting
import logging

logger = logging.getLogger(__name__)


def unix_to_jst(unix_time):
    utc_datetime = datetime.datetime.utcfromtimestamp(unix_time)
    jst_datetime = utc_datetime.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Asia/Tokyo'))
    jst_str = jst_datetime.strftime('%Y-%m-%d %H:%M:%S')
    return jst_str


def str_to_bool(value):
    return value.lower() == "true"


# 投資案件のURLを取得
def load_case(_id: str) -> str:  
    try:
        with open(setting.CASE_FILE, 'r') as f:
            cases = json.load(f)
        case_url = cases.get(str(_id))
        
        return case_url

    except AttributeError as e:
        logger.debug(f"case_id: {_id}が存在しません。")
        raise AttributeError(f"case_id: {_id}が存在しません。") from e