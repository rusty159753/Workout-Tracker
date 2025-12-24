import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- Page Config & Pro Styling ---
st.set_page_config(page_title="TriDrive Performance", page_icon="🚴‍♂️", layout="centered")
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; background-color: #ff4b4b; color: white; font-weight: bold; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 20px; border-radius: 10px; font-size: 1.1rem; line-height: 1.5; }
    .streamlit-expanderHeader { background-color: #262730 !important; border-radius: 8px; font-weight: bold; padding: 10px; }
    /* Preserves line breaks exactly as scraped */
    .preserve-breaks { white-space: pre-wrap; font-family: inherit; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- High-Fidelity Line-Preserving Scraper ---
def scrape_crossfit_wod():
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8' # Force encoding for special characters
        soup = BeautifulSoup(response.content, 'html.parser')
        today_code = datetime.date.today().strftime("%y%m%d")
        
        article = soup.find('article')
        if not article:
            return {"title": "Rest Day", "workout": "No workout found.", "stimulus": "", "scaling": "", "cues": ""}

        # Capture with natural newline separator
        raw_text = article.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

        def get_section_literal(start_trigger, stop_triggers):
            section_lines = []
            found_start = False
            for line in lines:
                if not found_start:
                    if (start_trigger.lower() in line.lower() and len(line) < 30) or (start_trigger == today_code and today_code in line):
                        found_start = True
                        continue
                else:
                    if any(stop.lower() in line.lower() and len(line) < 30 for stop in stop_triggers):
                        break
                    # Identify male/female lines to apply bolding and prevent splitting
                    if any(char in line for char in ['♀', '♂']):
                        section_lines.append(f"**{line}**")
                    else:
                        section_lines.append(line)
            return "\n".join(section_lines)

        # 1. Precise Title Extract
        title = "Today's WOD"
        for i, line in enumerate(lines):
            if today_code in line and i+1 < len(lines):
                title = lines[i+1]
                break

        # 2. Sequential literal extraction
        workout = get_section_literal(today_code, ["Stimulus", "Scaling", "Coaching cues", "Post time"])
        workout = workout.replace(title, "").strip()

        stimulus = get_section_literal("Stimulus", ["Scaling", "Coaching cues", "Post time"])
        scaling = get_section_literal("Scaling", ["Coaching cues", "Post time"])
        cues = get_section_literal("Coaching cues", ["Post time", "View results"])

        return {
            "title": title,
            "workout": workout,
            "stimulus": stimulus,
            "scaling": scaling,
            "cues": cues
        }

    except Exception as e:
        return {"title": "Manual Entry Mode", "workout": f"Technical Issue: {e}", "stimulus": "", "scaling": "", "cues": ""}

# --- Ledger Persistence ---
conn = st.connection("gsheets", type=GSheetsConnection)

def save_entry(data):
    try:
        existing = conn.read(ttl=0)
        new_row = pd.DataFrame([data])
        updated = pd.concat([existing, new_row], ignore_index=True) if not existing.empty else new_row
        conn.update(data=updated)
        return True
    except: return False

# --- UI Setup ---
st.title("TRI⚡DRIVE")
st.caption("43M | 150-160 lbs | Sciatica-Resilient Hub")

if st.session_state.wod_data is None:
    st.session_state.wod_data = scrape_crossfit_wod()

wod = st.session_state.wod_data
tab1, tab2, tab3 = st.tabs(["🔥 The Daily Drive", "📊 Metrics", "📈 Apex Analytics"])

with tab1:
    st.subheader(wod['title'])
    # Using markdown with white-space preservation for WOD
    st.markdown(f'<div class="stInfo preserve-breaks">{wod["workout"]}</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    if wod['stimulus']:
        with st.expander("⚡ Stimulus & Strategy"):
            st.markdown(f'<div class="preserve-breaks">{wod["stimulus"]}</div>', unsafe_allow_html=True)

    if wod['scaling']:
        with st.expander("⚖️ Scaling Options"):
            st.markdown(f'<div class="preserve-breaks">{wod["scaling"]}</div>', unsafe_allow_html=True)

    if wod['cues']:
        with st.expander("🧠 Coaching Cues"):
            st.markdown(f'<div class="preserve-breaks">{wod["cues"]}</div>', unsafe_allow_html=True)

with tab2:
    st.subheader("Performance Log")
    col1, col2 = st.columns(2)
    with col1:
        sciatica = st.slider("Sciatica Sensitivity", 1, 10, 2)
        weight = st.slider("Body Weight", 145, 170, 158)
    with col2:
        res = st.text_input("Score", placeholder="e.g. 12:45")
        notes = st.text_area("Gym Notes", placeholder="Back status...")
    
    if st.button("Save to TriDrive Ledger"):
        entry = {"Date": datetime.date.today().strftime("%Y-%m-%d"), "WOD_Name": wod['title'], "Result": res, "Weight": weight, "Sciatica_Score": sciatica, "Notes": notes}
        if save_entry(entry):
            st.success("WOD Logged!")
            st.balloons()

with tab3:
    try:
        history = conn.read(ttl=0)
        if not history.empty:
            history['Date'] = pd.to_datetime(history['Date'])
            st.line_chart(history.set_index('Date')[['Sciatica_Score', 'Weight']])
    except: st.info("Log a workout to view charts.")
        
