import streamlit as st
import datetime
import pytz
import json
import re
import unicodedata
from bs4 import BeautifulSoup

# --- ENVIRONMENT CHECK ---
try:
    import cloudscraper
    HAS_SCRAPER = True
except ImportError:
    HAS_SCRAPER = False

# --- STEP 1: THE JANITOR (Sanitization) ---
def sanitize_text(text):
    """
    Scrub the text to remove 'Ghost Spaces' and encoding artifacts.
    """
    if not text:
        return ""
    # Normalize unicode to handle special characters
    text = unicodedata.normalize("NFKD", text)
    # Replace non-breaking spaces with standard spaces
    text = text.replace('\xa0', ' ')
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# --- STEP 2: THE MAPPER (Positional Parsing) ---
def parse_workout_data(wod_data):
    """
    Slices the sanitized text into logical sections based on header positions.
    """
    raw_main = wod_data.get('main_text', '')
    raw_stim = wod_data.get('stimulus', '')
    
    # Sanitize the full blob immediately
    full_blob = sanitize_text(raw_main + " " + raw_stim)

    # Define the headers we are hunting for
    headers = {
        "Stimulus": re.compile(r"(Stimulus\s+and\s+Strategy|Stimulus):", re.IGNORECASE),
        "Scaling": re.compile(r"(Scaling|Scaling Options):", re.IGNORECASE),
        "Intermediate": re.compile(r"Intermediate\s+option:", re.IGNORECASE),
        "Beginner": re.compile(r"Beginner\s+option:", re.IGNORECASE),
        "Cues": re.compile(r"(Coaching\s+cues|Coaching\s+Tips):", re.IGNORECASE),
        "Resources": re.compile(r"(Resources):", re.IGNORECASE)
    }

    # Find the GPS coordinates (start/end) of every header found
    indices = []
    for key, pattern in headers.items():
        match = pattern.search(full_blob)
        if match:
            indices.append({"key": key, "start": match.start(), "end": match.end()})
    
    # Sort markers by their position in the text (Top to Bottom)
    indices.sort(key=lambda x: x['start'])

    parsed = {
        "workout": "", "history": None, "strategy": None,
        "scaling": None, "intermediate": None, "beginner": None,
        "cues": None, "resources": None
    }

    # SLICE A: The Workout (Start -> First Header)
    workout_end = indices[0]['start'] if indices else len(full_blob)
    workout_text = full_blob[:workout_end].strip()
    
    # Clean up "Post to comments" junk
    post_match = re.search(r"(Post\s+time\s+to\s+comments|Post\s+rounds\s+to\s+comments|Post\s+score\s+to\s+comments|Post\s+to\s+comments)", workout_text, re.IGNORECASE)
    if post_match:
        junk_tail = workout_text[post_match.end():]
        hist_match = re.search(r"Compare\s+to\s+(\d{6})", junk_tail)
        if hist_match:
            parsed['history'] = hist_match.group(1)
        parsed['workout'] = workout_text[:post_match.start()].strip()
    else:
        parsed['workout'] = workout_text

    # SLICE B: The Sections (Header -> Next Header)
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

# --- STEP 3: THE CLOUDSCRAPER ENGINE (Preserved) ---
def execute_cloud_sync():
    local_tz = pytz.timezone("US/Mountain")
    today_id = datetime.datetime.now(local_tz).strftime("%y%m%d")
    
    # Initialize the scraper (mimics a real Chrome browser)
    scraper = cloudscraper.create_scraper(browser={'browser': 'chrome', 'platform': 'windows', 'mobile': False})

    try:
        target_url = f"https://www.crossfit.com/{today_id}"
        
        # Use scraper.get instead of requests.get
        response = scraper.get(target_url, timeout=15)
        response.encoding = 'utf-8'

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            next_data = soup.find('script', id='__NEXT_DATA__')
            
            if next_data:
                data = json.loads(next_data.string)
                wod_data = data.get('props', {}).get('pageProps', {}).get('wod', {})
                if wod_data:
                    # Pass data to the Mapper
                    parsed = parse_workout_data(wod_data)
                    parsed['id'] = today_id
                    parsed['url'] = target_url
                    return parsed

            # HTML Fallback (Last resort)
            article = soup.find('article') or soup.find('main')
            if article:
                raw = sanitize_text(article.get_text(separator="\n", strip=True))
                return {"workout": raw, "title": f"WOD {today_id}", "url": target_url, "id": today_id}

        return {"error": f"Cloudflare Blocked Access (Status {response.status_code})"}
    except Exception as e:
        return {"error": f"Scraper Failure: {str(e)}"}

# --- STEP 4: THE UI LAYER (Interactive Dashboard) ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡", layout="centered")
st.title("TRI⚡DRIVE")

if not HAS_SCRAPER:
    st.error("⚠️ Dependency Missing")
    st.markdown("Please verify `cloudscraper` is in your requirements.txt file.")
else:
    with st.spinner("Syncing Live Feed..."):
        wod = execute_cloud_sync()

    if wod and "workout" in wod:
        # 1. HERO (Always Visible)
        st.subheader(wod['title'])
        st.info(wod['workout'].replace('♂', '(M)').replace('♀', '(F)'))
        
        if wod.get('history'):
            st.caption(f"📅 Compare to: {wod['history']}")

        st.divider()

        # 2. STRATEGY (Hidden)
        if wod.get('strategy'):
            with st.expander("Stimulus & Strategy", expanded=False):
                st.write(wod['strategy'].replace('♂', '(M)').replace('♀', '(F)'))

        # 3. SCALING & TABS (Hidden)
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

        # Footer
        st.sidebar.success(f"Synced: /{wod.get('id')}")
        st.sidebar.markdown(f"[Source]({wod.get('url')})")
    else:
        st.error(f"Error: {wod.get('error')}")
