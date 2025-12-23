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
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 20px; border-radius: 10px; font-size: 1.1rem; line-height: 1.6; }
    .streamlit-expanderHeader { background-color: #262730 !important; border-radius: 8px; font-weight: bold; padding: 10px; }
    .stInfo p { margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- Advanced Structural Scraper ---
def scrape_crossfit_wod():
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        today_code = datetime.date.today().strftime("%y%m%d")
        
        article = soup.find('article')
        if not article:
            return {"title": "Rest Day", "workout": "No workout found.", "stimulus": "", "scaling": "", "cues": ""}

        # Extracting with single newline to preserve original list flow
        raw_text = article.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]

        def get_section_robust(start_trigger, stop_triggers):
            section_lines = []
            found_start = False
            for line in lines:
                if not found_start:
                    # Target date or exact header match
                    if (start_trigger.lower() in line.lower() and len(line) < 30) or (start_trigger == today_code and today_code in line):
                        found_start = True
                        continue
                else:
                    # Stop if we hit a future header
                    if any(stop.lower() in line.lower() and len(line) < 30 for stop in stop_triggers):
                        break
                    
                    # Formatting weights for visibility
                    if any(char in line for char in ['♀', '♂', 'lb', 'kg']):
                        section_lines.append(f"**{line}**")
                    else:
                        section_lines.append(line)
            return "\n\n".join(section_lines)

        # 1. Title Capture
        title = "Today's WOD"
        for i, line in enumerate(lines):
            if today_code in line and i+1 < len(lines):
                title = lines[i+1]
                break

        # 2. Sequential Extraction
        workout = get_section_robust(today_code, ["Stimulus", "Scaling", "Coaching cues", "Post time"])
        workout = workout.replace(title, "").strip() # Clean redundancy

        stimulus = get_section_robust("Stimulus", ["Scaling", "Coaching cues", "Post time"])
        scaling = get_section_robust("Scaling", ["Coaching cues", "Post time"])
        cues = get_section_robust("Coaching cues", ["Post time", "View results"])

        return {
            "title": title,
            "workout": workout if workout else "Isabel: 30 Snatches for time (135/95 lbs)",
            "stimulus": stimulus,
            "scaling": scaling,
            "cues": cues
        }

    except Exception as e:
        return {"title": "Manual Entry Mode", "workout": f"Technical Issue: {e}", "stimulus": "", "scaling": "", "cues": ""}

# --- Data Persistence ---
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
    st.info(wod['workout'])
    st.markdown("---")
    
    if wod['stimulus']:
        with st.expander("⚡ Stimulus & Strategy"):
            st.markdown(wod['stimulus'])

    if wod['scaling']:
        with st.expander("⚖️ Scaling Options"):
            st.markdown(wod['scaling'])

    if wod['cues']:
        with st.expander("🧠 Coaching Cues"):
            st.markdown(wod['cues'])

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
        
