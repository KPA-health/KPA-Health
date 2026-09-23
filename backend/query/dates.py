from datetime import datetime, timedelta
import zoneinfo
from backend.settings import settings

def get_reference_date(ref_date_str: str = None) -> datetime:
    tz = zoneinfo.ZoneInfo(settings.timezone)
    if ref_date_str:
        return datetime.fromisoformat(ref_date_str).replace(tzinfo=tz)
    return datetime.now(tz)

def resolve_dates(start_str: str = None, end_str: str = None, ref_date_str: str = None):
    # Returns [start, end)
    tz = zoneinfo.ZoneInfo(settings.timezone)
    start = datetime.fromisoformat(start_str).replace(tzinfo=tz) if start_str else None
    end = datetime.fromisoformat(end_str).replace(tzinfo=tz) if end_str else None
    return start, end
