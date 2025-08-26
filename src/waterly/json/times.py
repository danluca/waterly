import pytz
from datetime import datetime
from src.waterly.config import CONFIG, Settings

def _json_datetime_encoder(dt:datetime) -> dict[str, str]:
    """
    Encodes a datetime object into a dictionary format suitable for JSON serialization.
    The dictionary contains the type of the object, its ISO 8601 string representation,
    and the time zone information if available.

    :param dt: The datetime object that needs to be encoded.
    :type dt: datetime
    :return: A dictionary containing the encoded datetime data with keys "__type__", "iso", and "tz".
    :rtype: dict[str, str]
    """
    stz = None
    if isinstance(dt.tzinfo, pytz.BaseTzInfo):
        stz = dt.tzinfo.zone
    elif dt.tzinfo:
        stz = dt.tzinfo.tzname(dt)
    return {
        "__type__": "datetime",
        "iso": dt.isoformat(),
        "tz": stz,
    }

def _json_datetime_decoder(obj:dict[str, str]) -> datetime | dict[str, str]:
    """
    Decodes a JSON object into a datetime object or returns the object if it is not a
    datetime representation.

    This function checks if the object represents a datetime by looking for a specific key "__type__" with the
    value "datetime". If this key is absent or has a different value, the function simply returns the input object
    to allow further processing from within the object hook.
    Otherwise, it attempts to parse the datetime information using the provided timezone information or the configuration
    local timezone, as the most probable timezone used for the device.

    :param obj: A dictionary containing potential datetime representation.
    :type obj: dict[str, str]
    :return: A datetime object if the input is a valid datetime representation; otherwise, the original dictionary is returned.
    :rtype: datetime | dict[str, str]
    """
    if "__type__" not in obj or obj["__type__"] != "datetime":
        return obj
    # noinspection PyBroadException
    try:
        tz = pytz.timezone(obj["tz"]) if obj["tz"] else CONFIG[Settings.LOCAL_TIMEZONE]
    except Exception:
        tz = CONFIG[Settings.LOCAL_TIMEZONE]
    return tz.localize(datetime.fromisoformat(obj["iso"]).replace(tzinfo=None))