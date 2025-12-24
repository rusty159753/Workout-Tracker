import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re
import datetime
import pytz
import unicodedata

# --- STEP 1: THE JANITOR (Sanitization) ---
def sanitize_text(text):
    """
    Scrub the text to remove 'Ghost Spaces' and encoding artifacts.
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = text.replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# --- STEP 2: THE MAPPER (Positional Parsing) ---
def parse_workout_data(wod_data):
    """
    Maps the workout text by position, ensuring robust extraction
    even if sections move around.
    """
    raw_main = wod_data.get('main_text', '')
    raw_stim = wod_data.get('stimulus', '')
    full_blob = sanitize_text(raw_main + " " + raw_stim)

    # Regex Headers
    headers = {
        "Stimulus": re.compile(r"(Stimulus\s+and\s+Strategy|Stimulus):", re.IGNORECASE),
        "Scaling": re.compile(r"(Scaling|Scaling Options):", re.IGNORECASE),
        "Intermediate": re.compile(r"Intermediate\s+option:", re.IGNORECASE),
        "Beginner": re.compile(r"Beginner\s+option:", re.IGNORECASE),
        "Cues": re.compile(r"(Coaching\s+cues|Coaching\s+Tips):", re.IGNORECASE),
        "Resources": re.compile(r"(Resources):", re.IGNORECASE)
    }

    indices = []
    for key, pattern in headers.items():
        match = pattern.search(full_blob)
        if match:
            indices.append({"key": key, "start": match.start(), "end": match.end()})
    
    indices.sort(key=lambda x: x['start'])

    parsed = {
        "workout": "", "history": None, "strategy": None,
        "scaling": None, "intermediate": None, "beginner": None,
        "cues": None, "resources": None
    }

    # Extract Workout Section
    workout_end = indices[0]['start'] if indices else len(full_blob)
    workout_text = full_blob[:workout_end].strip()
    
    # Remove "Post to comments" junk
    post_match = re.search(r"(Post\s+time\s+to\s+comments|Post\s+rounds\s+to\s+comments|Post\s+score\s+to\s+comments|Post\s+to\s+comments)", workout_text, re.IGNORECASE)
    if post_match:
        junk_tail = workout_text[post_match.end():]
        hist_match = re.search(r"Compare\s+to\s+(\d{6})", junk_tail)
        if hist_match:
            parsed['history'] = hist_match.group(1)
        parsed['workout'] = workout_text[:post_match.start()].strip()
    else:
        parsed['workout'] = workout_text

    # Extract Other Sections
    for i, item in enumerate(indices):
        key = item['key']
        start = item['end']
        end = indices[i+1]['start'] if (i + 1 < len(indices)) else len(full_blob)
        content = full_blob[start:end].strip()
        
        if key == "Stimulus": parsed['strategy'] = content
        elif key == "Scaling": parsed['scaling'] = content
        elif key == "Intermediate": parsed['intermediate'] = content
        elif key == "Beginner": parsed['beginner'] = content
        elif key == "Cues": parsed['cues'] = content
        elif key == "Resources": parsed['resources'] = content

    parsed['title'] = wod_data.get('title', 'Workout of the Day')
    return parsed

# --- STEP 3: THE HUMAN SESSION ENGINE ---
def execute_human_session():
    local_tz = pytz.timezone("US/Mountain")
    today_id = datetime.datetime.now(local_tz).strftime("%y%m%d")
    
    # 1. INITIALIZE SESSION (The "Browser Tab")
    # This object persists cookies across requests
    session = requests.Session()
    
    # 2. SET HUMAN HEADERS (The "Fingerprint")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.google.com/",
        "Upgrade-Insecure-Requests": "1",
        "Connection": "keep-alive"
    }
    session.headers.update(headers)

    try:
        # 3. THE HANDSHAKE (Visit Homepage First)
        # This gets the cookies/tokens from Cloudflare
        home_res = session.get("https://www.crossfit.com", timeout=10)
        
        # Discovery: Find the latest ID from the homepage
        match = re.search(r'(\d{6})', home_res.text)
        if match:
            target_id = match.group(1)
        else:
            target_id = today_id
            
        # 4. THE REQUEST (With Cookies)
        target_url = f"https://www.crossfit.com/{target_id}"
        response = session.get(target_url, timeout=15)
        response.encoding = 'utf-8' # Force Encoding

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            next_data = soup.find('script', id='__NEXT_DATA__')
            
            # 5. DATA EXTRACTION
            if next_data:
                data = json.loads(next_data.string)
                wod_data = data.get('props', {}).get('pageProps', {}).get('wod', {})
                
                if wod_data:
                    parsed_content = parse_workout_data(wod_data)
                    parsed_content['url'] = target_url
                    parsed_content['id'] = target_id
                    return parsed_content

            # Fallback for HTML-only pages (still using session)
            article = soup.find('article') or soup.find('main')
            if article:
                raw = sanitize_text(article.get_text(separator="\n", strip=True))
                return {"workout": raw, "title": f"WOD {target_id}", "url": target_url, "id": target_id}

            # DEBUG: If 200 OK but no data, capture the page title
            try:
                page_title = soup.title.string.strip()
            except:
                page_title = "Unknown"
            
            return {"error": f"Soft Block / Challenge Page Detected. Title: '{page_title}'"}

        return {"error": f"Site unreachable (Status {response.status_code})"}
        
    except Exception as e:
        return {"error": f"Connection Failure: {str(e)}"}

# --- UI LAYER ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡", layout="centered")
st.title("TRI⚡DRIVE")

with st.spinner("Syncing..."):
    wod = execute_human_session()

if wod and "workout" in wod:
    st.subheader(wod['title'])
    
    # Display Workout (Always Visible)
    st.info(wod['workout'].replace('♂', '(M)').replace('♀', '(F)'))
    
    if wod.get('history'):
        st.caption(f"📅 Compare to: {wod['history']}")

    # Strategy (Hidden)
    if wod.get('strategy'):
        with st.expander("Stimulus & Strategy", expanded=False):
            st.write(wod['strategy'].replace('♂', '(M)').replace('♀', '(F)'))

    # Scaling (Hidden + Tabs)
    has_scaling = any([wod.get('scaling'), wod.get('intermediate'), wod.get('beginner')])
    if has_scaling:
        with st.expander("Scaling & Modifications", expanded=False):
            tabs = []
            if wod.get('scaling'): tabs.append("Rx Scaling")
            if wod.get('intermediate'): tabs.append("Intermediate")
            if wod.get('beginner'): tabs.append("Beginner")
            if tabs:
                cols = st.tabs(tabs)
                for idx, name in enumerate(tabs):
                    key = name.lower().split()[0]
                    if name == "Rx Scaling": key = "scaling"
                    cols[idx].write(wod[key].replace('♂', '(M)').replace('♀', '(F)'))

    # Cues (Hidden)
    if wod.get('cues'):
        with st.expander("Coaching Cues", expanded=False):
            st.write(wod['cues'])

    st.divider()
    st.sidebar.success(f"Synced: /{wod.get('id')}")
    st.sidebar.markdown(f"[Source]({wod.get('url')})")

else:
    st.error(f"Error: {wod.get('error')}")
