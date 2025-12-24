import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import hashlib
from streamlit_gsheets import GSheetsConnection

# --- 1. UI SETUP ---
st.title("TRI⚡DRIVE")
st.sidebar.header("System Diagnostics")

# --- 2. INTEGRITY TOOL ---
def generate_audit_hash(data_string):
    return hashlib.sha256(data_string.encode('utf-8')).hexdigest()

# --- 3. REPAIRING THE SCRAPER ---
def debug_scrape(date_obj):
    anchor = date_obj.strftime("%y%m%d")
    url = "https://www.crossfit.com/wod"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code != 200:
            st.sidebar.error(f"Site Error: {response.status_code}")
            return None
        
        soup = BeautifulSoup(response.content, 'html.parser')
        article = next((a for a in soup.find_all('article') if anchor in a.get_text()), None)
        
        if not article:
            st.sidebar.warning(f"Anchor {anchor} not found on page.")
            return None
            
        # If found, return the structured data
        text = article.get_text(separator="\n").strip()
        return {"title": "Isabel", "workout": text, "hash": generate_audit_hash(text)}
    except Exception as e:
        st.sidebar.error(f"Scraper Exception: {e}")
        return None

# --- 4. THE CONNECTION TEST ---
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # Test if we can even talk to the Sheet
    df = conn.read(worksheet="WOD_CACHE", ttl=0)
    st.sidebar.success("Connection to Ledger: OK")
except Exception as e:
    st.sidebar.error(f"Ledger Error: {e}")

# Attempt to find data
today = datetime.date.today()
yesterday = today - datetime.timedelta(days=1)

wod = debug_scrape(today) or debug_scrape(yesterday)

if wod:
    st.subheader(wod['title'])
    st.info(wod['workout'])
else:
    st.error("Requested workout data is currently unavailable. Check sidebar diagnostics.")
    
