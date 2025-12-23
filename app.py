import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- Page Config & Styling ---
st.set_page_config(page_title="TriDrive Performance", page_icon="🚴‍♂️", layout="centered")
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; background-color: #ff4b4b; color: white; font-weight: bold; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 20px; border-radius: 10px; font-size: 1.1rem; line-height: 1.6; }
    .streamlit-expanderHeader { background-color: #262730 !important; border-radius: 5px; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- Step-by-Step Modular Scraper ---
def scrape_crossfit_wod():
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        today_code = datetime.date.today().strftime("%y%m%d")
        
        article = soup.find('article')
        if not article:
            return {"title": "Error", "workout": "Content not reachable.", "stimulus": "", "scaling": "", "cues": ""}

        # Convert entire article into a list of clean text lines
        raw_text = article.get_text(separator="|||", strip=True)
        lines = [line.strip() for line in raw_text.split("|||") if line.strip()]

        # Helper function to grab text between two markers
        def get_section(start_key, end_keys, include_start=False):
            capture = []
            found_start = False
            for line in lines:
                if not found_start and start_key in line:
                    found_start = True
                    if include_start: capture.append(line)
                    continue
                if found_start:
                    if any(end in line for end in end_keys):
                        break
                    capture.append(line)
            return "\n\n".join(capture)

        # STEP 1: Find Title (Line immediately after Date)
        title = "Today's WOD"
        for i, line in enumerate(lines):
            if today_code in line and i+1 < len(lines):
                title = lines[i+1]
                break

        # STEP 2: Scrape Workout (Date -> Stimulus)
        workout = get_section(today_code, ["Stimulus", "Scaling", "Post time"])
        # Clean up title from workout body if it was captured
        workout = workout.replace(title, "").strip()

        # STEP 3: Scrape Stimulus (Stimulus -> Scaling)
        stimulus = get_section("Stimulus", ["Scaling", "Coaching cues", "Post time"])

        # STEP 4: Scrape Scaling (Scaling -> Coaching cues)
        scaling = get_section("Scaling", ["Coaching cues", "Post time"])

        # STEP 5: Scrape Cues (Coaching cues -> Post time)
        cues = get_section("Coaching cues", ["Post time", "View results"])

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
    
    with st.expander("⚡ Stimulus & Strategy"):
        st.write(wod['stimulus'] if wod['stimulus'] else "Refer to CrossFit site.")

    with st.expander("⚖️ Scaling Options"):
        st.write(wod['scaling'] if wod['scaling'] else "Scale to maintain speed.")

    with st.expander("🧠 Coaching Cues"):
        st.write(wod['cues'] if wod['cues'] else "Keep bar close, heels down.")

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
        
