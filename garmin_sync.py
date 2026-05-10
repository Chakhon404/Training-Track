import certifi
import os
import sys
os.environ['SSL_CERT_FILE'] = certifi.where()
# NOTE: On Windows, use run.bat to start the app to ensure correct UTF-8 encoding.
# Force UTF-8 encoding on Windows
os.environ["PYTHONIOENCODING"] = "utf-8"
os.environ["PYTHONUTF8"] = "1"
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr.encoding != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8")

from datetime import date, timedelta, datetime, timezone
from garminconnect import (
    Garmin,
    GarminConnectAuthenticationError,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
)
from garth.exc import GarthHTTPError
from supabase import create_client

TOKENSTORE = ".garmin_tokens"

def get_garmin_client(email: str, password: str) -> Garmin:
    """
    Try token cache first (no credentials sent to Garmin).
    Only do fresh login if token missing/expired.
    """
    try:
        client = Garmin()
        client.login(TOKENSTORE)
        return client
    except (FileNotFoundError, GarthHTTPError, GarminConnectAuthenticationError):
        pass

    try:
        client = Garmin(email=email, password=password, is_cn=False)
        client.login()
        client.garth.dump(TOKENSTORE)
        return client
    except GarminConnectTooManyRequestsError:
        raise Exception("Rate limited by Garmin (429). Please wait 1-2 hours before retrying.")
    except GarminConnectAuthenticationError:
        raise Exception("Garmin login failed. Check your GARMIN_EMAIL and GARMIN_PASSWORD in secrets.toml.")
    except GarminConnectConnectionError as e:
        raise Exception(f"Garmin connection error: {e}")

def sync_garmin(
    supabase_url: str,
    supabase_key: str,
    garmin_email: str,
    garmin_password: str,
    target_date: date = None
):
    """
    Fetches wellness data from Garmin Connect and upserts into Supabase wellness table.
    Returns (success: bool, message: str)
    Each metric fetched independently — partial data is still saved.
    """
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    date_str = target_date.isoformat()

    try:
        client = get_garmin_client(garmin_email, garmin_password)
    except Exception as e:
        return False, f"Garmin login failed: {e}"

    def ms_to_iso(ms):
        if ms:
            try:
                return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat()
            except Exception:
                return None
        return None

    # Sleep
    sleep_start_iso = sleep_end_iso = None
    sleep_duration_min = sleep_score = None
    try:
        sleep_data = client.get_sleep_data(date_str)
        daily_sleep = sleep_data.get("dailySleepDTO", {})
        sleep_start_iso = ms_to_iso(daily_sleep.get("sleepStartTimestampGMT"))
        sleep_end_iso = ms_to_iso(daily_sleep.get("sleepEndTimestampGMT"))
        sleep_duration_min = (daily_sleep.get("sleepTimeSeconds") or 0) // 60
        sleep_score = (daily_sleep.get("sleepScores") or {}).get("overall", {}).get("value")
    except Exception:
        pass

    # Resting Heart Rate
    resting_hr = None
    try:
        hr_data = client.get_heart_rates(date_str)
        resting_hr = hr_data.get("restingHeartRate")
    except Exception:
        pass

    # Stress
    stress_avg = None
    try:
        stress_data = client.get_stress_data(date_str)
        stress_avg = stress_data.get("avgStressLevel")
    except Exception:
        pass

    # Body Battery
    body_battery_start = body_battery_end = None
    try:
        bb_data = client.get_body_battery(date_str)
        if bb_data and len(bb_data) > 0:
            values = [
                x.get("value")
                for x in bb_data[0].get("bodyBatteryValuesArray", [])
                if x.get("value") is not None
            ]
            body_battery_start = values[0] if values else None
            body_battery_end = values[-1] if values else None
    except Exception:
        pass

    # Training Readiness
    training_readiness = None
    try:
        tr_data = client.get_training_readiness(date_str)
        if tr_data and len(tr_data) > 0:
            training_readiness = tr_data[0].get("score")
    except Exception:
        pass

    # Upsert to Supabase
    try:
        supabase = create_client(supabase_url, supabase_key)
        payload = {
            "log_date": date_str,
            "sleep_start": sleep_start_iso,
            "sleep_end": sleep_end_iso,
            "sleep_duration_min": sleep_duration_min,
            "sleep_score": sleep_score,
            "resting_hr": resting_hr,
            "stress_avg": stress_avg,
            "body_battery_start": body_battery_start,
            "body_battery_end": body_battery_end,
            "training_readiness": training_readiness,
        }
        supabase.table("wellness").upsert(payload, on_conflict="log_date").execute()
        return True, f"✅ Synced wellness data for {date_str}"
    except Exception as e:
        return False, f"Supabase upsert failed: {e}"
