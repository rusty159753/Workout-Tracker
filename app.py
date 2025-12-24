import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import re
from streamlit_gsheets import GSheetsConnection

# --- Layout & High-Fidelity Styling ---
st.set_page_config(page_title="TriDrive Performance", page_icon="⚡", layout="centered")
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #ff4b4b; color: white; font-weight: bold; border: none; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 25px; border-radius: 10px; font-size: 1.15rem; line-height: 1.7; }
    .streamlit-expanderHeader { background-color: #262730 !important; border-radius: 8px; font-weight: bold; padding: 12px; border: 1px solid #3e3e4e; }
    .preserve-layout { white-space: pre-wrap !important; word-wrap: break-word; display: block; margin-bottom: 12px; font-family: inherit; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- Industrial-Grade Pattern Scraper ---
def scrape_crossfit_wod():
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.encoding = 'utf-8' 
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # We grab ALL text from the body to find the workout, regardless of container structure
        all_text = soup.body.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in all_text.split('\n') if line.strip()]

        # Data placeholders to avoid KeyError
        data = {"title": "Today's WOD", "workout": "", "stimulus": "", "scaling": "", "cues": ""}
        mode = "WAITING"
        today_code = datetime.date.today().strftime("%y%m%d")

        for i, line in enumerate(lines):
            # 1. TRIGGER: Find the Date Code (251223)
            if today_code in line:
                mode = "WOD"
                if i + 1 < len(lines):
                    data["title"] = lines[i+1] if len(lines[i+1]) < 30 else "Workout of the Day"
                continue

            # 2. TRANSITIONS: Detect specific headers
            if "Stimulus" in line:
                mode = "STIMULUS"
                continue
            if "Scaling" in line:
                mode = "SCALING"
                continue
            if "Coaching cues" in line:
                mode = "CUES"
                continue
            
            # 3. STOP: Determine where to end the entire capture
            if any(stop in line for stop in ["Compare to", "View results", "Resources"]):
                mode = "END"
                break

            # 4. CAPTURE LOGIC
            if mode == "WOD" and "Post time to comments" not in line:
                # Efficacy fix: Detect female/male weights and keep them together
                if "♀" in line or "♂" in line:
                    data["workout"] += f"**{line}** "
                else:
                    data["workout"] += line + "\n"
            elif mode == "STIMULUS":
                data["stimulus"] += line + "\n\n"
            elif mode == "SCALING":
                data["scaling"] += line + "\n\n"
            elif mode == "CUES":
                data["cues"] += line + "\n\n"

        # Final cleanup for display
        data["workout"] = data["workout"].strip()
        return data

    except Exception as e:
        return {"title": "Manual Entry", "workout": f"Error: {e}", "stimulus": "", "scaling": "", "cues": ""}

# --- GSheets Connection ---
conn = st.connection("gsheets", type=GSheetsConnection)

def save_entry(data_row):
    try:
        existing = conn.read(ttl=0)
        new_df = pd.DataFrame([data_row])
        updated = pd.concat([existing, new_df], ignore_index=True) if not existing.empty else new_df
        conn.update(data=updated)
        return True
    except: return False

# --- App UI ---
st.title("TRI⚡DRIVE")
st.caption("43M | 150-160 lbs | Sciatica-Resilient Hub")

if st.session_state.wod_data is None:
    st.session_state.wod_data = scrape_crossfit_wod()

wod = st.session_state.wod_data
tab1, tab2, tab3 = st.tabs(["🔥 The Daily Drive", "📊 Metrics", "📈 Apex Analytics"])

with tab1:
    st.subheader(wod.get('title', "Today's WOD"))
    st.info(wod.get('workout', "Workout loading..."))
    
    st.markdown("---")
    
    # Expanders with safety checks for 'None' or empty values
    with st.expander("⚡ Stimulus & Strategy"):
        st.write(wod.get('stimulus', "No stimulus data found."))

    with st.expander("⚖️ Scaling Options"):
        st.write(wod.get('scaling', "No scaling data found."))

    with st.expander("🧠 Coaching Cues"):
        st.write(wod.get('cues', "No cues found."))

with tab2:
    st.subheader("Performance Log")
    c1, c2 = st.columns(2)
    with c1:
        s_score = st.slider("Sciatica Sensitivity", 1, 10, 2)
        bw = st.slider("Body Weight", 145, 170, 158)
    with c2:
        res = st.text_input("Score", placeholder="e.g. 12:45")
        log_notes = st.text_area("Notes", placeholder="Back status...")
    
    if st.button("Save to TriDrive Ledger"):
        entry = {"Date": datetime.date.today().strftime("%Y-%m-%d"), "WOD_Name": wod['title'], "Result": res, "Weight": bw, "Sciatica_Score": s_score, "Notes": log_notes}
        if save_entry(entry):
            st.success("WOD Logged!")
            st.balloons()

with tab3:
    try:
        history = conn.read(ttl=0)
        if not history.empty:
            history['Date'] = pd.to_datetime(history['Date'])
            st.line_chart(history.set_index('Date')[['Sciatica_Score', 'Weight']])
    except: st.info("Log your first session to see trends.")
        
