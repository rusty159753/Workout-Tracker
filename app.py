import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime

# --- 1. INDUSTRIAL UI (VERIFIED MOBILE LAYOUT) ---
st.set_page_config(page_title="TriDrive Performance", layout="centered")
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 20px; border-radius: 10px; font-size: 1.1rem; line-height: 1.6; }
    .preserve-layout { white-space: pre-wrap !important; display: block; margin-bottom: 12px; font-family: inherit; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. THE DYNAMIC ANCHOR PARSER ---
def execute_dynamic_scrape():
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    try:
        # STEP A: Generate the dynamic date code (YYMMDD)
        today_code = datetime.date.today().strftime("%y%m%d") # Today: 251223
        
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # STEP B: Identify the specific article for TODAY
        target_article = None
        for article in soup.find_all('article'):
            if today_code in article.get_text():
                target_article = article
                break
        
        if not target_article: return None

        # STEP C: Parse the verified container
        lines = [l.strip() for l in target_article.get_text(separator="\n", strip=True).split("\n") if l.strip()]
        
        data = {"title": "Today's WOD", "workout": [], "stimulus": [], "scaling": []}
        current_state = "WORKOUT"

        for line in lines:
            if "Stimulus" in line: current_state = "STIMULUS"
            elif "Scaling" in line: current_state = "SCALING"
            elif any(stop in line for stop in ["Resources", "View results", "Compare to"]):
                if current_state in ["STIMULUS", "SCALING"]: break
            
            if current_state == "WORKOUT":
                if today_code not in line and "Workout of the Day" not in line:
                    if any(s in line for s in ['♀', '♂']):
                        data["workout"].append(f"**{line}**")
                    else:
                        data["workout"].append(line)
            elif current_state == "STIMULUS" and "Stimulus" not in line:
                data["stimulus"].append(line)
            elif current_state == "SCALING" and "Scaling" not in line:
                data["scaling"].append(line)

        return {
            "title": data["workout"][0] if data["workout"] else "Isabel",
            "workout": "\n".join(data["workout"][1:] if len(data["workout"]) > 1 else data["workout"]),
            "stimulus": "\n\n".join(data["stimulus"]),
            "scaling": "\n\n".join(data["scaling"])
        }
    except:
        return None

# --- 3. UI EXECUTION ---
st.title("TRI⚡DRIVE")
current_date = datetime.date.today().strftime("%Y.%m.%d")
st.caption(f"Dynamic Anchor Build | Lock Target: {current_date}")

if 'wod_data' not in st.session_state or st.sidebar.button("Refresh Scrape"):
    st.session_state.wod_data = execute_dynamic_scrape()

wod = st.session_state.wod_data

if wod:
    st.subheader(wod['title'])
    st.markdown(f'<div class="stInfo preserve-layout">{wod["workout"]}</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    if wod['stimulus']:
        with st.expander("⚡ Stimulus and Strategy"):
            st.markdown(f'<div class="preserve-layout">{wod["stimulus"]}</div>', unsafe_allow_html=True)
            
    if wod['scaling']:
        with st.expander("⚖️ Scaling Options"):
            st.markdown(f'<div class="preserve-layout">{wod["scaling"]}</div>', unsafe_allow_html=True)
else:
    st.error(f"Could not find a workout matching {datetime.date.today().strftime('%y%m%d')}. Please verify Seattle VPN.")

# --- END OF FILE: app.py ---
