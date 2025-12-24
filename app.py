import streamlit as st
import requests
from bs4 import BeautifulSoup
import json
import re
import datetime
import pytz

def execute_final_hardened_sync():
    # 1. TIMEZONE ALIGNMENT: Lock to Boise time to prevent '251224' future-leak
    local_tz = pytz.timezone("US/Mountain")
    now = datetime.datetime.now(local_tz)
    today_id = now.strftime("%y%m%d")
    
    # Headers to bypass 'Shell' and 'Cookie' barriers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5"
    }

    try:
        # 2. TARGETED DISCOVERY: We try the 'Today' ID directly first (Agnostic & Fast)
        target_url = f"https://www.crossfit.com/{today_id}"
        response = requests.get(target_url, headers=headers, timeout=15)
        
        # If the direct ID isn't live, we fall back to Homepage Discovery
        if response.status_code != 200:
            home_res = requests.get("https://www.crossfit.com", headers=headers, timeout=10)
            # Find the FIRST 6-digit ID on the homepage to see what is currently live
            match = re.search(r'(\d{6})', home_res.text)
            if match:
                today_id = match.group(1)
                target_url = f"https://www.crossfit.com/{today_id}"
                response = requests.get(target_url, headers=headers, timeout=15)

        if response.status_code == 200:
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 3. EXTRACTION: THE JSON BRAIN (NEXT.JS DATA SHELL)
            next_data = soup.find('script', id='__NEXT_DATA__')
            if next_data:
                data = json.loads(next_data.string)
                # Precision Path: pageProps -> wod
                wod_data = data.get('props', {}).get('pageProps', {}).get('wod', {})
                
                if wod_data:
                    title = wod_data.get('title', 'Workout of the Day')
                    main_text = wod_data.get('main_text', '')
                    stimulus = wod_data.get('stimulus', '')
                    
                    return {
                        "title": title,
                        "content": f"{main_text}\n\n**Stimulus & Strategy:**\n{stimulus}" if stimulus else main_text,
                        "url": target_url,
                        "id": today_id
                    }

            # 4. FINAL FAILSAFE: GREEDY BODY HARVEST
            # If JSON is missing, we pull the physical 'Article' or 'Main' tag
            article = soup.find('article') or soup.find('main')
            if article:
                return {
                    "title": f"WOD {today_id}",
                    "content": article.get_text(separator="\n", strip=True),
                    "url": target_url,
                    "id": today_id
                }

        return {"error": f"Site unreachable (Status {response.status_code})"}
        
    except Exception as e:
        return {"error": f"Critical Audit Failure: {str(e)}"}

# --- UI LAYER ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")
st.title("TRI⚡DRIVE")

# Execute the audited logic
with st.spinner("Locking on to live WOD..."):
    wod = execute_final_hardened_sync()

if wod and "content" in wod:
    st.subheader(wod['title'])
    
    # Clean the Rx symbols for the Pixel display
    final_text = wod['content'].replace('♂', '(M)').replace('♀', '(F)')
    st.info(final_text)
    
    st.sidebar.success(f"Status: Live-Sync /{wod.get('id')}")
    st.sidebar.markdown(f"[Verify on CrossFit.com]({wod['url']})")
else:
    st.error(f"Logic Failure: {wod.get('error')}")
                    
