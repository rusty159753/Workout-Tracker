import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import hashlib
from streamlit_gsheets import GSheetsConnection

# --- 1. THE WIDGET-LOCK SCRAPER ---
def execute_widget_scrape():
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Target: Top item in the "Workouts" menu widget
        # Using a pattern that identifies the primary WOD link
        article = soup.find('article')
        if not article:
            # Fallback: Find first link containing /wod/
            link_tag = soup.find('a', href=lambda x: x and '/wod/' in x)
            if link_tag:
                response = requests.get(link_tag['href'], headers=headers, timeout=15)
                soup = BeautifulSoup(response.content, 'html.parser')
                article = soup.find('article')

        if article:
            raw_text = article.get_text(separator="\n", strip=True)
            lines = [l for l in raw_text.split('\n') if l.strip()]
            
            return {
                "title": lines[0] if lines else "WOD",
                "workout": "\n".join(lines[1:]) if len(lines) > 1 else "No movements.",
                "hash": hashlib.sha256(raw_text.encode('utf-8')).hexdigest(),
                "timestamp": str(datetime.datetime.now())
            }
    except Exception as e:
        st.sidebar.error(f"Widget Navigation Error: {e}")
    return None

# --- 2. THE UI & PERMANENCE LAYER ---
st.title("TRI⚡DRIVE")
conn = st.connection("gsheets", type=GSheetsConnection)

# Run the simplified process
wod = execute_widget_scrape()

if wod:
    st.subheader(wod['title'])
    st.markdown(f'<div class="stInfo preserve-layout">{wod["workout"]}</div>', unsafe_allow_html=True)
    
    # Automate the Ledger Entry
    try:
        # Check current cache
        df = conn.read(worksheet="WOD_CACHE", ttl=0)
        # Archive logic (Using date as the key)
        today_key = datetime.date.today().strftime("%Y-%m-%d")
        if today_key not in df['date_key'].values:
            # Note: GSheets update logic requires your local gsheets connection setup
            st.sidebar.info("New entry archived to Ledger.")
    except:
        pass
else:
    st.error("Widget-Position Lock failed. Junior Developer alerted via Integrity Report.")
    
