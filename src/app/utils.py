import datetime
import pytz

def unix_to_jst(unix_time):
    utc_datetime = datetime.datetime.utcfromtimestamp(unix_time)
    jst_datetime = utc_datetime.replace(tzinfo=pytz.utc).astimezone(pytz.timezone('Asia/Tokyo'))
    jst_str = jst_datetime.strftime('%Y-%m-%d %H:%M:%S')
    return jst_str


def str_to_bool(value):
    return value.lower() == "true"
