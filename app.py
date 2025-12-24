import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import hashlib
from streamlit_gsheets import GSheetsConnection

# --- 1. RESILIENT AGNOSTIC SCRAPER ---
def execute_resilient_scrape():
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Grab the FIRST article on the page (The most recent WOD)
        article = soup.find('article')
        
        if article:
            # Capture content for the audit hash
            raw_content = article.get_text(separator="\n", strip=True)
            lines = [line for line in raw_content.split('\n') if line.strip()]
            
            # Extract date from the link to use as the database key
            link = article.find('a', href=True)
            date_match = link['href'] if link else "unknown-date"
            
            return {
                "title": lines[0] if lines else "Workout of the Day",
                "workout": "\n".join(lines[1:]) if len(lines) > 1 else "No movements found.",
                "hash": hashlib.sha256(raw_content.encode('utf-8')).hexdigest(),
                "date_key": date_match # Captures the actual date from the URL
            }
    except Exception as e:
        st.sidebar.error(f"Scrape Error: {e}")
    return None

# --- 2. EXECUTION ---
st.title("TRI⚡DRIVE")
conn = st.connection("gsheets", type=GSheetsConnection)

# Run the Resilient Scraper
wod = execute_resilient_scrape()

if wod:
    st.subheader(wod['title'])
    st.markdown(f'<div class="stInfo preserve-layout">{wod["workout"]}</div>', unsafe_allow_html=True)
    st.sidebar.success(f"Source: {wod['date_key']}")
    st.sidebar.info(f"Integrity: {wod['hash'][:8]}")
else:
    st.error("Connection successful, but no workout articles were found on the page.")
            
