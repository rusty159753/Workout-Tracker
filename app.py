import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re
import datetime
import pytz

# --- CORE LOGIC: THE LINGUISTIC SLICER ---
def parse_workout_data(wod_data):
    """
    Slices the raw JSON content into clean, categorized buckets
    based on the Owner's "Grammar of CrossFit" logic.
    """
    # 1. RAW INPUTS
    title = wod_data.get('title', 'Workout of the Day')
    raw_main = wod_data.get('main_text', '')
    raw_stimulus = wod_data.get('stimulus', '') # Often contains strategy + scaling

    # 2. PARSE THE MAIN WORKOUT (The "Gold Standard")
    # We stop reading at "Post time to comments" to remove the admin noise.
    # We also extract the "Compare to" date for the History section.
    
    # Default to raw if splitter not found
    clean_workout = raw_main 
    history_ref = None
    
    # Splitter Logic
    split_match = re.search(r"(Post\s+time\s+to\s+comments|Post\s+rounds\s+to\s+comments|Post\s+score\s+to\s+comments)", raw_main, re.IGNORECASE)
    if split_match:
        clean_workout = raw_main[:split_match.start()].strip()
        
        # Look for History in the junk pile (text after the split)
        junk_text = raw_main[split_match.end():]
        history_match = re.search(r"Compare\s+to\s+(\d{6})", junk_text)
        if history_match:
            history_ref = history_match.group(1)

    # 3. PARSE THE STRATEGY & SCALING (The "Education")
    # The 'stimulus' field usually contains Strategy -> Scaling -> Options.
    # We will slice this string into specific sections.
    
    strategy_text = raw_stimulus
    scaling_text = None
    intermediate_text = None
    beginner_text = None

    # Slice: Find where "Scaling" starts
    scaling_match = re.search(r"(Scaling|Scaling Options):", raw_stimulus, re.IGNORECASE)
    if scaling_match:
        # Strategy is everything BEFORE "Scaling"
        strategy_text = raw_stimulus[:scaling_match.start()].strip()
        # Scaling is everything AFTER
        full_scaling_block = raw_stimulus[scaling_match.start():]
        
        # Now, look for Intermediate/Beginner inside the Scaling block
        inter_match = re.search(r"Intermediate\s+option:", full_scaling_block, re.IGNORECASE)
        begin_match = re.search(r"Beginner\s+option:", full_scaling_block, re.IGNORECASE)
        
        # If we find specific options, we slice them out
        if inter_match:
            scaling_text = full_scaling_block[:inter_match.start()].strip()
            # Check if Beginner follows Intermediate
            if begin_match and begin_match.start() > inter_match.start():
                intermediate_text = full_scaling_block[inter_match.start():begin_match.start()].strip()
                beginner_text = full_scaling_block[begin_match.start():].strip()
            else:
                intermediate_text = full_scaling_block[inter_match.start():].strip()
        elif begin_match:
            # Beginner only
            scaling_text = full_scaling_block[:begin_match.start()].strip()
            beginner_text = full_scaling_block[begin_match.start():].strip()
        else:
            # Just generic scaling
            scaling_text = full_scaling_block

    return {
        "title": title,
        "workout": clean_workout,
        "history": history_ref,
        "strategy": strategy_text,
        "scaling": scaling_text,
        "intermediate": intermediate_text,
        "beginner": beginner_text
    }

# --- EXECUTION ENGINE: MIRROR SYNC ---
def execute_parsed_sync():
    # 1. TIMEZONE & HEADERS (Standard Hardened Setup)
    local_tz = pytz.timezone("US/Mountain")
    today_id = datetime.datetime.now(local_tz).strftime("%y%m%d")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }

    try:
        # 2. DISCOVERY: Try Direct ID first, then Homepage Fallback
        target_url = f"https://www.crossfit.com/{today_id}"
        response = requests.get(target_url, headers=headers, timeout=15)
        
        if response.status_code != 200:
            # Fallback to homepage scanning
            home_res = requests.get("https://www.crossfit.com", headers=headers, timeout=10)
            match = re.search(r'(\d{6})', home_res.text)
            if match:
                today_id = match.group(1)
                target_url = f"https://www.crossfit.com/{today_id}"
                response = requests.get(target_url, headers=headers, timeout=15)

        # 3. EXTRACTION: JSON BRAIN
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            next_data = soup.find('script', id='__NEXT_DATA__')
            
            if next_data:
                data = json.loads(next_data.string)
                wod_data = data.get('props', {}).get('pageProps', {}).get('wod', {})
                
                if wod_data:
                    # PASS DATA TO THE NEW PARSER
                    parsed_content = parse_workout_data(wod_data)
                    parsed_content['url'] = target_url
                    parsed_content['id'] = today_id
                    return parsed_content

            # Fallback for "Total Harvest" if JSON structure fails
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

with st.spinner("Syncing & Parsing Live Feed..."):
    wod = execute_parsed_sync()

if wod and "workout" in wod:
    # 1. THE WORK (Clean, Simple, No Bold)
    st.subheader(wod['title'])
    
    # Symbol Cleaning
    clean_workout = wod['workout'].replace('♂', '(M)').replace('♀', '(F)')
    st.info(clean_workout)
    
    # History Reference (Small, unobtrusive)
    if wod.get('history'):
        st.caption(f"📅 Compare to: {wod['history']}")

    st.divider()

    # 2. THE STRATEGY (Expandable)
    if wod.get('strategy'):
        with st.expander("Stimulus & Strategy", expanded=False):
            st.write(wod['strategy'])

    # 3. THE LEVELS (Tabs for clarity)
    # Only show tabs if we actually have content to put in them
    tabs = []
    tab_names = []
    
    if wod.get('scaling'): tab_names.append("Rx Scaling")
    if wod.get('intermediate'): tab_names.append("Intermediate")
    if wod.get('beginner'): tab_names.append("Beginner")
    
    if tab_names:
        cols = st.tabs(tab_names)
        for idx, name in enumerate(tab_names):
            content_key = name.lower().split()[0] # 'rx', 'intermediate', 'beginner'
            # Map back to our dictionary keys
            if name == "Rx Scaling": content_key = "scaling"
            
            # Display content in simple text
            cols[idx].write(wod[content_key].replace('♂', '(M)').replace('♀', '(F)'))

    # Footer
    st.sidebar.success(f"Synced: /{wod.get('id')}")
    st.sidebar.markdown(f"[View on CrossFit.com]({wod.get('url')})")

else:
    st.error(f"System Failure: {wod.get('error')}")
