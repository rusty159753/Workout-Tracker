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
    Cleans the text to handle encoding errors and invisible spaces.
    This runs BEFORE we try to parse the workout.
    """
    if not text:
        return ""
    
    # 1. Fix weird characters (â□□ -> ')
    text = unicodedata.normalize("NFKD", text)
    
    # 2. Fix the "Invisible Wall" (Non-Breaking Spaces)
    text = text.replace('\xa0', ' ')
    
    # 3. Clean up whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

# --- STEP 2: THE MAPPER (Positional Parsing) ---
def parse_workout_data(wod_data):
    """
    Maps out the text by finding the position of every header,
    then slicing the text based on those positions.
    """
    # Combine main text and stimulus to ensure we capture everything
    raw_main = wod_data.get('main_text', '')
    raw_stim = wod_data.get('stimulus', '')
    
    # SANITIZE FIRST: Scrub the blob
    full_blob = sanitize_text(raw_main + " " + raw_stim)

    # Define the headers we are looking for
    headers = {
        "Stimulus": re.compile(r"(Stimulus\s+and\s+Strategy|Stimulus):", re.IGNORECASE),
        "Scaling": re.compile(r"(Scaling|Scaling Options):", re.IGNORECASE),
        "Intermediate": re.compile(r"Intermediate\s+option:", re.IGNORECASE),
        "Beginner": re.compile(r"Beginner\s+option:", re.IGNORECASE),
        "Cues": re.compile(r"(Coaching\s+cues|Coaching\s+Tips):", re.IGNORECASE),
        "Resources": re.compile(r"(Resources):", re.IGNORECASE)
    }

    # Find where each section starts and ends
    indices = []
    for key, pattern in headers.items():
        match = pattern.search(full_blob)
        if match:
            indices.append({
                "key": key,
                "start": match.start(),
                "end": match.end()
            })
    
    # Sort by position in the text
    indices.sort(key=lambda x: x['start'])

    # Prepare the container
    parsed = {
        "workout": "", "history": None, "strategy": None,
        "scaling": None, "intermediate": None, "beginner": None,
        "cues": None, "resources": None
    }

    # 1. EXTRACT WORKOUT (Start -> First Header)
    workout_end = indices[0]['start'] if indices else len(full_blob)
    workout_text = full_blob[:workout_end].strip()
    
    # Clean up "Post to comments" junk
    post_match = re.search(r"(Post\s+time\s+to\s+comments|Post\s+rounds\s+to\s+comments|Post\s+score\s+to\s+comments|Post\s+to\s+comments)", workout_text, re.IGNORECASE)
    if post_match:
        # Check for history comparison
        junk_tail = workout_text[post_match.end():]
        hist_match = re.search(r"Compare\s+to\s+(\d{6})", junk_tail)
        if hist_match:
            parsed['history'] = hist_match.group(1)
        parsed['workout'] = workout_text[:post_match.start()].strip()
    else:
        parsed['workout'] = workout_text

    # 2. EXTRACT SECTIONS
    for i, item in enumerate(indices):
        key = item['key']
        start = item['end']
        # End at the next section start, or end of text
        end = indices[i+1]['start'] if (i + 1 < len(indices)) else len(full_blob)
        content = full_blob[start:end].strip()
        
        # Map to keys
        if key == "Stimulus": parsed['strategy'] = content
        elif key == "Scaling": parsed['scaling'] = content
        elif key == "Intermediate": parsed['intermediate'] = content
        elif key == "Beginner": parsed['beginner'] = content
        elif key == "Cues": parsed['cues'] = content
        elif key == "Resources": parsed['resources'] = content

    parsed['title'] = wod_data.get('title', 'Workout of the Day')
    return parsed

# --- STEP 3: DISCOVERY & EXTRACTION (Restored) ---
def execute_full_sync():
    local_tz = pytz.timezone("US/Mountain")
    today_id = datetime.datetime.now(local_tz).strftime("%y%m%d")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        # A. Try Direct ID First
        target_url = f"https://www.crossfit.com/{today_id}"
        response = requests.get(target_url, headers=headers, timeout=15)
        response.encoding = 'utf-8' # Force Encoding

        # B. Fallback to Homepage Discovery if Direct ID fails OR yields empty JSON
        # (This prevents the Status 200 error when the ID exists but has no WOD data)
        valid_data_found = False
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            next_data = soup.find('script', id='__NEXT_DATA__')
            if next_data:
                data = json.loads(next_data.string)
                # Verify deeper structure exists
                if data.get('props', {}).get('pageProps', {}).get('wod'):
                    valid_data_found = True

        if not valid_data_found:
            # Revert to Homepage Search
            home_res = requests.get("https://www.crossfit.com", headers=headers, timeout=10)
            home_res.encoding = 'utf-8'
            match = re.search(r'(\d{6})', home_res.text)
            if match:
                today_id = match.group(1)
                target_url = f"https://www.crossfit.com/{today_id}"
                response = requests.get(target_url, headers=headers, timeout=15)
                response.encoding = 'utf-8'

        # C. Process the Final Valid Response
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            next_data = soup.find('script', id='__NEXT_DATA__')
            
            if next_data:
                data = json.loads(next_data.string)
                wod_data = data.get('props', {}).get('pageProps', {}).get('wod', {})
                
                if wod_data:
                    # Pass raw data to the Parser (which Sanitizes -> Maps)
                    parsed_content = parse_workout_data(wod_data)
                    parsed_content['url'] = target_url
                    parsed_content['id'] = today_id
                    return parsed_content

            # HTML Fallback (Last Resort)
            article = soup.find('article') or soup.find('main')
            if article:
                raw = sanitize_text(article.get_text(separator="\n", strip=True))
                return {"workout": raw, "title": f"WOD {today_id}", "url": target_url, "id": today_id}

        return {"error": f"Site unreachable (Status {response.status_code})"}
        
    except Exception as e:
        return {"error": f"Logic Failure: {str(e)}"}

# --- UI LAYER ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡", layout="centered")
st.title("TRI⚡DRIVE")

with st.spinner("Syncing Live Feed..."):
    wod = execute_full_sync()

if wod and "workout" in wod:
    # 1. HERO (Always Visible)
    st.subheader(wod['title'])
    
    # Display the sanitized, split workout text
    clean_workout = wod['workout'].replace('♂', '(M)').replace('♀', '(F)')
    st.info(clean_workout)
    
    if wod.get('history'):
        st.caption(f"📅 Compare to: {wod['history']}")

    # 2. STRATEGY (Hidden)
    if wod.get('strategy'):
        with st.expander("Stimulus & Strategy", expanded=False):
            st.write(wod['strategy'].replace('♂', '(M)').replace('♀', '(F)'))

    # 3. SCALING (Hidden + Tabs)
    # Check if any scaling content exists
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

    # 4. CUES (Hidden)
    if wod.get('cues'):
        with st.expander("Coaching Cues", expanded=False):
            st.write(wod['cues'])

    st.divider()
    st.sidebar.success(f"Synced: /{wod.get('id')}")
    st.sidebar.markdown(f"[Source]({wod.get('url')})")

else:
    st.error(f"Error: {wod.get('error')}")
