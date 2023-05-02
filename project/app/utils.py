import re
import datetime
import pytz
import json
import logging

logger = logging.getLogger(__name__)


ALLOWED_DOMAINS = ["save-slack-gsheet.iam.gserviceaccount.com", "gmail.com"]
def check_email_domain(email_list: list):
    filtered = []
    for email in email_list:
            if re.search(fr"@({'|'.join(ALLOWED_DOMAINS)})$", email):
                filtered.append(email)
            else:
                raise AttributeError(f"Invalid email: {email}. Gmail only allowed.")
    return filtered


def unix_to_jst(unix_time):
    utc_datetime = datetime.datetime.utcfromtimestamp(unix_time)
    jst_datetime = utc_datetime.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Asia/Tokyo'))
    jst_str = jst_datetime.strftime('%Y-%m-%d %H:%M:%S')
    return jst_str


def str_to_bool(value):
    return value.lower() == "true"


def load_case(_id: str, is_liar: bool) -> str:  
    try:
        with open("./app/case.json", 'r') as f:
            cases = json.load(f)
        _type = "lie" if is_liar else "truth"
        case = cases.get(str(_id)).get(_type)
        
        case_str = ""
        for name, content in case.items():
            if isinstance(content, dict):
                case_str += f'• {name}: \n'
                for name, content in content.items():
                    case_str += f' - {name}: {content}\n'
            else:
                case_str += f'• {name}: {content}\n'
        return case_str

    except AttributeError as e:
        logger.debug(f"case_id: {_id}が存在しません。")
        raise AttributeError(f"case_id: {_id}が存在しません。") from e