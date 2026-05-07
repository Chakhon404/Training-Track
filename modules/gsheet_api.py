import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import time

# --- EXACT CONFIGURATION ---
SHEET_CONFIG = {
    "sheet_id": "1EEbWz3-C4qOljdUfLy92DNacmEP8MAY2cEKD5XvOmjU",
    "worksheets": {
        "workouts": "Workouts",
        "running": "Running",
        "biohack": "Biohack",
        "weight": "Weight"
    }
}

@st.cache_resource
def get_gspread_client():
    """
    Authenticates and returns a gspread client using Streamlit secrets.
    Cached to optimize resources and connection overhead.
    """
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    
    try:
        credentials = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=scopes
        )
        return gspread.authorize(credentials)
    except Exception as e:
        st.error(f"Cloud Authentication Failed: {e}")
        return None

def get_worksheet(worksheet_key):
    """
    Gets a specific worksheet from the Google Sheet based on normalized config key.
    Uses open_by_key for a rock-solid connection.
    """
    client = get_gspread_client()
    if not client:
        return None
    
    # Normalization: match config keys
    key = worksheet_key.strip().lower()
    
    if key not in SHEET_CONFIG["worksheets"]:
        st.error(f"Configuration Error: Key '{key}' not found in SHEET_CONFIG.")
        return None
        
    tab_name = SHEET_CONFIG["worksheets"][key]
    
    try:
        # Open by unique Sheet ID for reliability
        sheet = client.open_by_key(SHEET_CONFIG["sheet_id"])
        return sheet.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        st.error(f"Tab [{tab_name}] not found. Please check Google Sheet Tab names.")
        return None
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return None

def batch_append(worksheet_key, data_list):
    """
    Appends multiple rows to the specified worksheet with visual feedback.
    """
    if not data_list:
        st.warning("No data provided for submission.")
        return False

    # Normalization: ensure key matches config
    worksheet_key = worksheet_key.strip().lower()

    with st.status("Data Submission in Progress...", expanded=True) as status:
        st.write("Verifying database connection...")
        worksheet = get_worksheet(worksheet_key)
        
        if worksheet is None:
            status.update(label="Submission Aborted: Connection Error", state="error")
            return False
            
        try:
            st.write(f"Writing {len(data_list)} record(s) to cloud storage...")
            worksheet.append_rows(data_list, value_input_option='USER_ENTERED')
            status.update(label="Submission Successful!", state="complete")
            time.sleep(1) # Brief pause for UI feedback
            return True
        except Exception as e:
            st.write(f"Write Error: {e}")
            status.update(label="Submission Failed: API Error", state="error")
            return False
            
def fetch_all_records(worksheet_key):
    """
    Fetches all records for analytics and reporting.
    """
    worksheet = get_worksheet(worksheet_key)
    if worksheet is None:
        return []
    try:
        return worksheet.get_all_records()
    except Exception as e:
        st.error(f"Data Retrieval Error: {e}")
        return []
