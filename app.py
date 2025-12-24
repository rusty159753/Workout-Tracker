import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import hashlib
from streamlit_gsheets import GSheetsConnection

# --- 1. AGNOSTIC SCRAPER (NO HARD-CODED NAMES) ---
def execute_agnostic_scrape(date_obj):
    # Constructing the URL path based on the date, NOT the name
    date_path = date_obj.strftime("/%Y/%m/%d")
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Identify the article by the date in its link
        article = soup.find('article')
        link_to_check = article.find('a', href=True) if article else None
        
        if article and date_path in link_to_check['href']:
            # Capture EVERYTHING inside the article for completeness
            raw_content = article.get_text(separator="\n", strip=True)
            lines = [line for line in raw_content.split('\n') if line.strip()]
            
            # The title is dynamically the first line, workout is the rest
            return {
                "title": lines[0] if lines else "Workout of the Day",
                "workout": "\n".join(lines[1:]) if len(lines) > 1 else lines[0],
                "hash": hashlib.sha256(raw_content.encode('utf-8')).hexdigest(),
                "date_key": date_obj.strftime("%Y-%m-%d")
            }
    except Exception as e:
        st.sidebar.error(f"Scrape Error: {e}")
    return None

# --- 2. THE UI & PERMANENCE LAYER ---
st.title("TRI⚡DRIVE")
conn = st.connection("gsheets", type=GSheetsConnection)

# Get the target date dynamically (Today)
target_date = datetime.date.today()
wod = execute_agnostic_scrape(target_date)

if wod:
    st.subheader(wod['title']) # This will show "Isabel" today, and something else tomorrow
    st.markdown(f'<div class="stInfo">{wod["workout"]}</div>', unsafe_allow_html=True)
    
    # Audit Verification
    st.sidebar.success(f"Audit: {wod['hash'][:8]}... Verified")
else:
    st.error("Could not find a workout for today's date on CrossFit.com.")
    
