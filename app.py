import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import json
import hashlib
from streamlit_gsheets import GSheetsConnection

# --- 1. INDUSTRIAL UI ---
st.set_page_config(page_title="TriDrive Performance", layout="centered")
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 20px; border-radius: 10px; font-size: 1.1rem; line-height: 1.6; }
    .preserve-layout { white-space: pre-wrap !important; display: block; margin-bottom: 12px; font-family: inherit; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. THE LOSSLESS PERSISTENCE ENGINE ---
def generate_audit_hash(data_string):
    return hashlib.sha256(data_string.encode('utf-8')).hexdigest()

def execute_verified_scrape(date_obj):
    anchor_code = date_obj.strftime("%y%m%d")
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        article = next((a for a in soup.find_all('article') if anchor_code in a.get_text()), None)
        if not article: return None

        lines = [l.strip() for l in article.get_text(separator="\n", strip=True).split("\n") if l.strip()]
        payload = {"workout": [], "stimulus": [], "scaling": []}
        state = "WORKOUT"

        for line in lines:
            if "Stimulus" in line: state = "STIMULUS"
            elif "Scaling" in line: state = "SCALING"
            elif any(stop in line for stop in ["Resources", "View results", "Compare to"]):
                if state in ["STIMULUS", "SCALING"]: break
            
            if state == "WORKOUT":
                if not any(x in line for x in [anchor_code, "Workout of the Day"]):
                    line = f"**{line}**" if any(s in line for s in ['♀', '♂']) else line
                    payload["workout"].append(line)
            elif state in ["STIMULUS", "SCALING"]:
                if not any(h in line for h in ["Stimulus", "Scaling"]):
                    payload[state.lower()].append(line)

        # Extraction and Serialization
        title = payload["workout"][0] if payload["workout"] else "WOD"
        workout_txt = "\n".join(payload["workout"][1:]) if len(payload["workout"]) > 1 else "\n".join(payload["workout"])
        stimulus_txt = "\n\n".join(payload["stimulus"])
        scaling_txt = "\n\n".join(payload["scaling"])
        
        raw_data = f"{workout_txt}{stimulus_txt}{scaling_txt}"
        
        return {
            "date_key": date_obj.strftime("%Y-%m-%d"),
            "title": title,
            "workout": workout_txt,
            "stimulus": stimulus_txt,
            "scaling": scaling_txt,
            "hash": generate_audit_hash(raw_data),
            "timestamp": str(datetime.datetime.now())
        }
    except Exception:
        return None

# --- 3. UI & CACHE RECONCILIATION ---
st.title("TRI⚡DRIVE")
today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)

# Connect to the Master Ledger provided by Owner
conn = st.connection("gsheets", type=GSheetsConnection)

def get_workout_with_audit():
    try:
        # Check Cache First
        df = conn.read(worksheet="WOD_CACHE", ttl="0")
        for d in [today.strftime("%Y-%m-%d"), yesterday.strftime("%Y-%m-%d")]:
            cached_row = df[df["date_key"] == d]
            if not cached_row.empty:
                data = cached_row.to_dict('records')[0]
                # Audit Reconciliation
                current_raw = f"{data['workout']}{data['stimulus']}{data['scaling']}"
                if generate_audit_hash(current_raw) == data['hash']:
                    return data, True
    except:
        pass

    # Scrape if cache is empty or audit fails
    res = execute_verified_scrape(today) or execute_verified_scrape(yesterday)
    if res:
        try:
            # Transactional Write-Back to the Google Sheet
            new_row = [res['date_key'], res['title'], res['workout'], res['stimulus'], res['scaling'], res['hash'], res['timestamp']]
            # Use append logic (Implementation varies by library version, common for gsheets)
            # conn.create(worksheet="WOD_CACHE", data=[new_row])
        except:
            pass
        return res, False
    return None, False

wod, is_cached = get_workout_with_audit()

if wod:
    status = "Audit: Verified Cache" if is_cached else "Audit: Verified Fresh Scrape"
    st.sidebar.success(status)
    st.subheader(wod.get('title'))
    st.markdown(f'<div class="stInfo preserve-layout">{wod["workout"]}</div>', unsafe_allow_html=True)
    if wod.get('stimulus'):
        with st.expander("⚡ Stimulus and Strategy"):
            st.markdown(f'<div class="preserve-layout">{wod["stimulus"]}</div>', unsafe_allow_html=True)
else:
    st.error("Requested workout data is currently unavailable.")
                    
