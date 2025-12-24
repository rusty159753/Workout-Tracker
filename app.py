import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime

# --- 1. INDUSTRIAL UI (STRICT SCOPE) ---
st.set_page_config(page_title="TriDrive Performance", layout="centered")
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 20px; border-radius: 10px; font-size: 1.1rem; line-height: 1.6; }
    .preserve-layout { white-space: pre-wrap !important; display: block; margin-bottom: 12px; font-family: inherit; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. LOCAL-TIME AWARE SCRAPER ---
def execute_localized_scrape(local_date_str):
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        
        target_article = None
        # Search for the article matching the user's LOCAL date (YYMMDD)
        for article in soup.find_all('article'):
            if local_date_str in article.get_text():
                target_article = article
                break
        
        if not target_article: return None

        lines = [l.strip() for l in target_article.get_text(separator="\n", strip=True).split("\n") if l.strip()]
        data = {"title": "WOD", "workout": [], "stimulus": [], "scaling": []}
        current_state = "WORKOUT"

        for line in lines:
            if "Stimulus" in line: current_state = "STIMULUS"
            elif "Scaling" in line: current_state = "SCALING"
            elif any(stop in line for stop in ["Resources", "View results", "Compare to"]):
                if current_state in ["STIMULUS", "SCALING"]: break
            
            if current_state == "WORKOUT":
                if not any(x in line for x in [local_date_str, "Workout of the Day"]):
                    if any(s in line for s in ['♀', '♂']):
                        data["workout"].append(f"**{line}**")
                    else:
                        data["workout"].append(line)
            elif current_state == "STIMULUS" and "Stimulus" not in line:
                data["stimulus"].append(line)
            elif current_state == "SCALING" and "Scaling" not in line:
                data["scaling"].append(line)

        return {
            "title": data["workout"][0] if data["workout"] else "WOD",
            "workout": "\n".join(data["workout"][1:] if len(data["workout"]) > 1 else data["workout"]),
            "stimulus": "\n\n".join(data["stimulus"]),
            "scaling": "\n\n".join(data["scaling"])
        }
    except:
        return None

# --- 3. UI EXECUTION ---
st.title("TRI⚡DRIVE")

# Get User's Local Date for the Anchor (Defaults to Python Date if JS fails)
local_date_code = datetime.date.today().strftime("%y%m%d")
st.caption(f"Current Lock: {local_date_code}")

if 'wod_data' not in st.session_state or st.sidebar.button("Refresh"):
    st.session_state.wod_data = execute_localized_scrape(local_date_code)

wod = st.session_state.wod_data

if wod:
    st.subheader(wod['title'])
    st.markdown(f'<div class="stInfo preserve-layout">{wod["workout"]}</div>', unsafe_allow_html=True)
    if wod['stimulus']:
        with st.expander("⚡ Stimulus and Strategy"):
            st.markdown(f'<div class="preserve-layout">{wod["stimulus"]}</div>', unsafe_allow_html=True)
else:
    st.error("Requested workout data is currently unavailable.")

# --- END OF FILE: app.py ---
