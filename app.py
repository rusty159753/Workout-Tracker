import streamlit as st
import datetime
import pytz
import json
import re
import unicodedata
import hashlib
from bs4 import BeautifulSoup

# --- ENVIRONMENT CHECK ---
try:
    import cloudscraper
    import gspread
    from google.oauth2.service_account import Credentials
    READY_TO_SYNC = True
except ImportError:
    READY_TO_SYNC = False

# --- SESSION STATE ---
if 'view_mode' not in st.session_state:
    st.session_state['view_mode'] = 'VIEWER'
if 'current_wod' not in st.session_state:
    st.session_state['current_wod'] = {}

# --- STEP 1: THE JANITOR (UNTOUCHED) ---
def sanitize_text(text):
    if not text: return ""
    text = BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)
    text = unicodedata.normalize("NFKD", text)
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# --- STEP 2: THE MAPPER (RESTORED HYBRID LOGIC) ---
def parse_workout_data(wod_data):
    # LOGIC RESTORED: Handle both Dictionary (JSON) and String (HTML) inputs
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

# --- STEP 3: ENGINES (RESTORED FALLBACK) ---
def fetch_wod_content():
    local_tz = pytz.timezone("US/Mountain")
    today_id = datetime.datetime.now(local_tz).strftime("%y%m%d")
    
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

    try:
        url = f"https://www.crossfit.com/{today_id}"
        response = scraper.get(url, timeout=20)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # ATTEMPT 1: JSON Data (Preferred)
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
                    pass # JSON failed, try HTML

            # ATTEMPT 2: HTML Fallback (RESTORED)
            # This is what was missing. If JSON is empty, look for the text.
            article = soup.find('article') or soup.find('div', {'class': re.compile(r'content|wod')}) or soup.find('main')
            
            if article:
                # Grab raw text and feed it to the parser
                raw_text = article.get_text(separator=" ", strip=True)
                parsed = parse_workout_data(raw_text) # Helper now accepts string
                parsed['id'] = today_id
                parsed['title'] = f"WOD {today_id}" # Fallback title
                return parsed

            # DEBUG: Only returns this if BOTH methods fail
            page_title = soup.title.string.strip() if soup.title else "No Title"
            return {"error": f"Page found ('{page_title}') but parsers failed."}

        return {"error": f"Connection Failed: Status {response.status_code}"}
        
    except Exception as e:
        return {"error": f"Crash: {str(e)}"}

# --- UI LAYER (UNTOUCHED) ---
st.set_
