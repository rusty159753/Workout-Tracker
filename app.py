import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re
import datetime
import pytz

# --- CORE LOGIC: THE DEEP LINGUISTIC SLICER ---
def parse_workout_data(wod_data):
    """
    Slices the raw JSON content into interactive buckets.
    Handles the case where HQ stuffs everything into 'main_text'.
    """
    # 1. RAW INPUTS
    title = wod_data.get('title', 'Workout of the Day')
    # Combine main and stimulus just in case, to ensure we catch everything
    raw_blob = wod_data.get('main_text', '') + " " + wod_data.get('stimulus', '')

    # 2. DEFINE MARKERS (The "Grammar of CrossFit")
    # We look for these headers to chop the string into blocks
    markers = {
        "stimulus": re.compile(r"(Stimulus\s+and\s+Strategy|Stimulus):", re.IGNORECASE),
        "scaling": re.compile(r"(Scaling|Scaling Options):", re.IGNORECASE),
        "cues": re.compile(r"(Coaching\s+cues|Coaching\s+Tips):", re.IGNORECASE),
        "resources": re.compile(r"(Resources):", re.IGNORECASE)
    }

    # 3. SLICE & DICE
    # We iterate through the blob and extract sections based on the markers.
    
    # A. Extract Resources (to strip them from the end)
    resources_text = None
    res_match = markers['resources'].search(raw_blob)
    if res_match:
        resources_text = raw_blob[res_match.end():].strip()
        raw_blob = raw_blob[:res_match.start()].strip() # Remove resources from the blob

    # B. Extract Coaching Cues
    cues_text = None
    cues_match = markers['cues'].search(raw_blob)
    if cues_match:
        cues_text = raw_blob[cues_match.end():].strip()
        raw_blob = raw_blob[:cues_match.start()].strip() # Remove cues from the blob

    # C. Extract Scaling
    scaling_text = None
    intermediate_text = None
    beginner_text = None
    scale_match = markers['scaling'].search(raw_blob)
    if scale_match:
        full_scaling_block = raw_blob[scale_match.end():].strip()
        raw_blob = raw_blob[:scale_match.start()].strip() # Remove scaling from the blob

        # Parse Levels inside Scaling
        inter_match = re.search(r"Intermediate\s+option:", full_scaling_block, re.IGNORECASE)
        begin_match = re.search(r"Beginner\s+option:", full_scaling_block, re.IGNORECASE)

        if inter_match:
            scaling_text = full_scaling_block[:inter_match.start()].strip()
            if begin_match and begin_match.start() > inter_match.start():
                intermediate_text = full_scaling_block[inter_match.start():begin_match.start()].strip()
                beginner_text = full_scaling_block[begin_match.start():].strip()
            else:
                intermediate_text = full_scaling_block[inter_match.start():].strip()
        elif begin_match:
            scaling_text = full_scaling_block[:begin_match.start()].strip()
            beginner_text = full_scaling_block[begin_match.start():].strip()
        else:
            scaling_text = full_scaling_block

    # D. Extract Stimulus
    strategy_text = None
    stim_match = markers['stimulus'].search(raw_blob)
    if stim_match:
        strategy_text = raw_blob[stim_match.end():].strip()
        raw_blob = raw_blob[:stim_match.start()].strip() # Remove stimulus from blob

    # E. The Remainder is the WORKOUT
    # We clean up the "Post to comments" junk at the end of the workout text
    clean_workout = raw_blob
    history_ref = None
    split_match = re.search(r"(Post\s+time\s+to\s+comments|Post\s+rounds\s+to\s+comments|Post\s+score\s+to\s+comments|Post\s+to\s+comments)", raw_blob, re.IGNORECASE)
    if split_match:
        clean_workout = raw_blob[:split_match.start()].strip()
        junk_text = raw_blob[split_match.end():]
        # Look for History in the junk
        history_match = re.search(r"Compare\s+to\s+(\d{6})", junk_text)
        if history_match:
            history_ref = history_match.group(1)

    return {
        "title": title,
        "workout": clean_workout,
        "history": history_ref,
        "strategy": strategy_text,
        "scaling": scaling_text,
        "intermediate": intermediate_text,
        "beginner": beginner_text,
        "cues": cues_text,
        "resources": resources_text
    }

# --- EXECUTION ENGINE: MIRROR SYNC ---
def execute_parsed_sync():
    local_tz = pytz.timezone("US/Mountain")
    today_id = datetime.datetime.now(local_tz).strftime("%y%m%d")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        # Discovery: Try Direct ID first
        target_url = f"https://www.crossfit.com/{today_id}"
        response = requests.get(target_url, headers=headers, timeout=15)
        response.encoding = 'utf-8' # *** CRITICAL ENCODING FIX ***

        if response.status_code != 200:
            # Fallback Discovery
            home_res = requests.get("https://www.crossfit.com", headers=headers, timeout=10)
            home_res.encoding = 'utf-8'
            
            match = re.search(r'(\d{6})', home_res.text)
            if match:
                today_id = match.group(1)
                target_url = f"https://www.crossfit.com/{today_id}"
                response = requests.get(target_url, headers=headers, timeout=15)
                response.encoding = 'utf-8'

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            next_data = soup.find('script', id='__NEXT_DATA__')
            
            if next_data:
                data = json.loads(next_data.string)
                wod_data = data.get('props', {}).get('pageProps', {}).get('wod', {})
                
                if wod_data:
                    parsed_content = parse_workout_data(wod_data)
                    parsed_content['url'] = target_url
                    parsed_content['id'] = today_id
                    return parsed_content

            # HTML Fallback
            article = soup.find('article') or soup.find('main')
            if article:
                return {
                    "title": f"WOD {today_id}",
                    "workout": article.get_text(separator="\n", strip=True),
                    "url": target_url,
                    "id": today_id
                }

        return {"error": f"Site unreachable (Status {response.status_code})"}
        
    except Exception as e:
        return {"error": f"Parsing Failure: {str(e)}"}

# --- UI LAYER ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡", layout="centered")
st.title("TRI⚡DRIVE")

with st.spinner("Syncing Live Feed..."):
    wod = execute_parsed_sync()

if wod and "workout" in wod:
    # 1. THE HERO (Always Visible)
    st.subheader(wod['title'])
    clean_workout = wod['workout'].replace('♂', '(M)').replace('♀', '(F)')
    st.info(clean_workout)
    
    if wod.get('history'):
        st.caption(f"📅 Compare to: {wod['history']}")

    # 2. STIMULUS (Hidden by Default)
    if wod.get('strategy'):
        with st.expander("Stimulus & Strategy", expanded=False):
            st.write(wod['strategy'].replace('♂', '(M)').replace('♀', '(F)'))

    # 3. SCALING (Hidden by Default -> Tabs)
    # Check if we have any scaling content
    has_scaling = any([wod.get('scaling'), wod.get('intermediate'), wod.get('beginner')])
    
    if has_scaling:
        with st.expander("Scaling & Modifications", expanded=False):
            # Dynamic Tabs
            tabs = []
            tab_names = []
            if wod.get('scaling'): tab_names.append("Rx Scaling")
            if wod.get('intermediate'): tab_names.append("Intermediate")
            if wod.get('beginner'): tab_names.append("Beginner")
            
            if tab_names:
                cols = st.tabs(tab_names)
                for idx, name in enumerate(tab_names):
                    content_key = name.lower().split()[0]
                    if name == "Rx Scaling": content_key = "scaling"
                    cols[idx].write(wod[content_key].replace('♂', '(M)').replace('♀', '(F)'))

    # 4. COACHING CUES (Hidden by Default)
    if wod.get('cues'):
        with st.expander("Coaching Cues", expanded=False):
            st.write(wod['cues'])

    # Footer
    st.divider()
    st.sidebar.success(f"Synced: /{wod.get('id')}")
    st.sidebar.markdown(f"[View on CrossFit.com]({wod.get('url')})")

else:
    st.error(f"System Failure: {wod.get('error')}")
    
