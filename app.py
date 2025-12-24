import streamlit as st
import datetime
import pytz
import json
import re
import unicodedata
import hashlib
from bs4 import BeautifulSoup

# --- 1. CONFIG MUST BE FIRST ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")

# --- DEBUG: Hard Reset Button ---
with st.sidebar:
    st.header("🔧 Diagnostics")
    if st.button("⚠️ Hard Reset App", type="primary"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

# --- 2. ENVIRONMENT CHECK ---
try:
    import cloudscraper
    import gspread
    from google.oauth2.service_account import Credentials
    READY_TO_SYNC = True
    st.sidebar.success("Dependencies: OK")
except ImportError:
    READY_TO_SYNC = False
    st.sidebar.error("Dependencies: Missing")

# --- 3. SESSION STATE ---
if 'view_mode' not in st.session_state:
    st.session_state['view_mode'] = 'VIEWER'
if 'current_wod' not in st.session_state:
    st.session_state['current_wod'] = {}

# --- 4. THE JANITOR ---
def sanitize_text(text):
    if not text: return ""
    text = BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# --- 5. THE MAPPER ---
def parse_workout_data(wod_data):
    if isinstance(wod_data, str):
        full_blob = sanitize_text(wod_data)
        title = "Workout of the Day"
    else:
        raw_main = wod_data.get('main_text', '')
        raw_stim = wod_data.get('stimulus', '')
        full_blob = sanitize_text(raw_main + " " + raw_stim)
        title = wod_data.get('title', 'Workout of the Day')

    headers = {
        "Stimulus": re.compile(r"(Stimulus\s+and\s+Strategy|Stimulus):", re.IGNORECASE),
        "Scaling": re.compile(r"(Scaling|Scaling Options):", re.IGNORECASE),
        "Intermediate": re.compile(r"Intermediate\s+option:", re.IGNORECASE),
        "Beginner": re.compile(r"Beginner\s+option:", re.IGNORECASE),
        "Cues": re.compile(r"(Coaching\s+cues|Coaching\s+Tips):", re.IGNORECASE)
    }

    indices = []
    for key, pattern in headers.items():
        match = pattern.search(full_blob)
        if match:
            indices.append({"key": key, "start": match.start(), "end": match.end()})
    
    indices.sort(key=lambda x: x['start'])
    parsed = {"workout": "", "history": None, "strategy": "", "scaling": "", "intermediate": "", "beginner": "", "cues": ""}

    workout_end = indices[0]['start'] if indices else len(full_blob)
    workout_text = full_blob[:workout_end].strip()
    
    post_match = re.search(r"(Post\s+time\s+to\s+comments|Post\s+rounds\s+to\s+comments|Post\s+to\s+comments)", workout_text, re.IGNORECASE)
    if post_match:
        parsed['workout'] = workout_text[:post_match.start()].strip()
    else:
        parsed['workout'] = workout_text

    for i, item in enumerate(indices):
        key, start = item['key'], item['end']
        end = indices[i+1]['start'] if (i + 1 < len(indices)) else len(full_blob)
        content = full_blob[start:end].strip()
        if key == "Stimulus": parsed['strategy'] = content
        elif key == "Scaling": parsed['scaling'] = content
        elif key == "Intermediate": parsed['intermediate'] = content
        elif key == "Beginner": parsed['beginner'] = content
        elif key == "Cues": parsed['cues'] = content

    parsed['title'] = title
    parsed['hash'] = hashlib.md5(full_blob.encode()).hexdigest()
    return parsed

# --- 6. ENGINES ---
def fetch_wod_content():
    local_tz = pytz.timezone("US/Mountain")
    today_id = datetime.datetime.now(local_tz).strftime("%y%m%d")
    
    # DEBUG: Force new scraper instance
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

    try:
        url = f"https://www.crossfit.com/{today_id}"
        # DEBUG: Short timeout to prevent infinite hanging
        response = scraper.get(url, timeout=10)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # ATTEMPT 1: JSON
            next_data = soup.find('script', id='__NEXT_DATA__')
            if next_data:
                try:
                    json_payload = json.loads(next_data.string)
                    wod_data = json_payload.get('props', {}).get('pageProps', {}).get('wod', {})
                    if wod_data:
                        parsed = parse_workout_data(wod_data)
                        parsed['id'] = today_id
                        return parsed
                except:
                    pass

            # ATTEMPT 2: HTML
            article = soup.find('article') or soup.find('div', {'class': re.compile(r'content|wod')}) or soup.find('main')
            if article:
                raw_text = article.get_text(separator=" ", strip=True)
                parsed = parse_workout_data(raw_text)
                parsed['id'] = today_id
                parsed['title'] = f"WOD {today_id}"
                return parsed

            page_title = soup.title.string.strip() if soup.title else "No Title"
            return {"error": f"Parsers failed. Page Title: '{page_title}'"}

        return {"error": f"Status {response.status_code}"}
        
    except Exception as e:
        return {"error": f"Error: {str(e)}"}

# --- 7. UI LAYER ---
st.title("TRI⚡DRIVE")
st.write("---") # Visual separator to prove rendering started

if not READY_TO_SYNC:
    st.error("Missing Dependencies")
else:
    # --- VIEW MODE ---
    if st.session_state['view_mode'] == 'VIEWER':
        
        cached_data = st.session_state.get('current_wod', {})
        
        # LOGIC: Only fetch if empty or error
        if not cached_data or "error" in cached_data:
            st.info("📡 Connecting to Headquarters...") # Visual cue
            wod = fetch_wod_content()
            
            if "error" not in wod:
                st.session_state['current_wod'] = wod
                st.rerun() # Force refresh to clear the "Connecting" message
            else:
                st.error(f"⚠️ {wod['error']}")
                if st.button("🔄 Retry Connection"):
                    st.session_state['current_wod'] = {}
                    st.rerun()
        else:
            # RENDER SUCCESS STATE
            wod = cached_data
            if "workout" in wod:
                st.subheader(wod['title'])
                st.info(wod['workout'])
                
                if st.button("🚀 IMPORT TO WORKBENCH", use_container_width=True):
                    st.session_state['view_mode'] = 'WORKBENCH'
                    st.rerun()

                st.divider()
                
                if wod.get('strategy'):
                    with st.expander("Stimulus & Strategy"):
                        st.write(wod['strategy'])
                
                if any([wod.get('scaling'), wod.get('intermediate')]):
                    with st.expander("Scaling Options"):
                        st.write(f"**Rx Scaling:** {wod.get('scaling', 'N/A')}")
                        st.write(f"**Intermediate:** {wod.get('intermediate', 'N/A')}")
            else:
                st.error("Data Corrupted. Please hit Hard Reset.")

    # --- WORKBENCH MODE ---
    elif st.session_state['view_mode'] == 'WORKBENCH':
        st.caption("🛠️ WORKBENCH ACTIVE")
        wod = st.session_state.get('current_wod', {})
        
        if not wod:
            st.error("No WOD loaded.")
            if st.button("Back"):
                st.session_state['view_mode'] = 'VIEWER'
                st.rerun()
        else:
            st.success(f"Imported: {wod.get('title', 'Unknown')}")
            st.markdown(f"**Rx Workout:** {wod.get('workout', 'No Data')}")
            st.warning("⚠️ Phase 3 Construction Zone")
            
            if st.button("⬅️ Back to Viewer"):
                st.session_state['view_mode'] = 'VIEWER'
                st.rerun()
