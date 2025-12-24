import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- Page Config & "Pixel-Perfect" UI ---
st.set_page_config(page_title="TriDrive Performance", page_icon="⚡", layout="centered")
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stButton>button { width: 100%; border-radius: 12px; height: 3.5em; background-color: #ff4b4b; color: white; font-weight: bold; border: none; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 25px; border-radius: 10px; font-size: 1.15rem; line-height: 1.7; }
    .streamlit-expanderHeader { background-color: #262730 !important; border-radius: 8px; font-weight: bold; padding: 12px; border: 1px solid #3e3e4e; }
    /* The "Efficacy" Fix: Forces the app to respect the website's literal line hierarchy */
    .preserve-layout { white-space: pre-wrap !important; word-wrap: break-word; display: block; margin-bottom: 12px; font-family: inherit; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- Industrial-Grade Structural Scraper ---
def scrape_crossfit_wod():
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.encoding = 'utf-8' # Critical for ♀ and ♂ symbols
        soup = BeautifulSoup(response.content, 'html.parser')
        today_code = datetime.date.today().strftime("%y%m%d")
        
        # 1. Targeted Container Discovery
        # Instead of guessing the tag, we find the container holding the date anchor
        article = soup.find(string=lambda t: today_code in t if t else False)
        if article:
            # Move up to the main post container
            article = article.find_parent('article') or article.find_parent('div', class_='content')
        
        if not article:
            return {"title": "Rest Day", "workout": "Workout details not found. Please log manually.", "stim": "", "scal": "", "cue": ""}

        # 2. Block-Level Line Extraction
        # We use a unique separator to ensure nested <span> elements don't bunch up
        lines = [l.strip() for l in article.get_text(separator="\n", strip=True).split("\n") if l.strip()]

        # 3. Precise Sectioning Logic
        sections = {"WOD": [], "STIM": [], "SCAL": [], "CUE": []}
        mode = "WAITING"
        title = "Today's WOD"

        for i, line in enumerate(lines):
            # Anchor 1: Start
            if today_code in line:
                mode = "WOD"
                if i + 1 < len(lines): title = lines[i+1]
                continue
            
            # Anchor 2: Stimulus
            if "Stimulus" in line:
                mode = "STIM"
                continue
            
            # Anchor 3: Scaling (Hard Match to prevent shunting)
            if "Scaling" in line and len(line) < 15:
                mode = "SCAL"
                continue

            # Anchor 4: Cues
            if "Coaching cues" in line:
                mode = "CUE"
                continue
            
            # Stop condition
            if "Post time to comments" in line:
                mode = "WOD_END"
                continue
            if any(stop in line for stop in ["Compare to", "View results"]):
                break

            # Data Capture
            if mode == "WOD":
                if line != title and "Workout of the Day" not in line:
                    # Bold the weights to mirror the website's emphasis
                    if any(c in line for c in ['♀', '♂']):
                        sections["WOD"].append(f"**{line}**")
                    else:
                        sections["WOD"].append(line)
            elif mode in sections:
                # Clean section headers out of the content
                if not any(h in line for h in ["Stimulus", "Scaling", "Coaching cues"]):
                    sections[mode].append(line)

        return {
            "title": title,
            "workout": "\n".join(sections["WOD"]),
            "stimulus": "\n".join(sections["STIM"]),
            "scaling": "\n".join(sections["SCAL"]),
            "cues": "\n".join(sections["CUE"])
        }

    except Exception:
        return {"title": "Connection Error", "workout": "Could not connect to CrossFit.com.", "stimulus": "", "scaling": "", "cues": ""}

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

# --- App Interface ---
st.title("TRI⚡DRIVE")
st.caption("43M | 150-160 lbs | Sciatica-Resilient Hub")

if st.session_state.wod_data is None:
    st.session_state.wod_data = scrape_crossfit_wod()

wod = st.session_state.wod_data
tab1, tab2, tab3 = st.tabs(["🔥 The Daily Drive", "📊 Metrics", "📈 Apex Analytics"])

with tab1:
    st.subheader(wod['title'])
    # Using 'preserve-layout' to force the website's exact line break structure
    st.markdown(f'<div class="stInfo preserve-layout">{wod["workout"]}</div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Each section is logically separated into its own expander
    if wod['stimulus']:
        with st.expander("⚡ Stimulus & Strategy"):
            st.markdown(f'<div class="preserve-layout">{wod["stimulus"]}</div>', unsafe_allow_html=True)

    if wod['scaling']:
        with st.expander("⚖️ Scaling Options"):
            st.markdown(f'<div class="preserve-layout">{wod["scaling"]}</div>', unsafe_allow_html=True)

    if wod['cues']:
        with st.expander("🧠 Coaching Cues"):
            st.markdown(f'<div class="preserve-layout">{wod["cues"]}</div>', unsafe_allow_html=True)

with tab2:
    st.subheader("Performance Log")
    c1, c2 = st.columns(2)
    with c1:
        s_score = st.slider("Sciatica Sensitivity", 1, 10, 2)
        bw = st.slider("Body Weight", 145, 170, 158)
    with col2:
        res = st.text_input("Score", placeholder="e.g. 12:45")
        log_notes = st.text_area("Notes", placeholder="L5-S1 status...")
    
    if st.button("Save to TriDrive Ledger"):
        entry = {"Date": datetime.date.today().strftime("%Y-%m-%d"), "WOD_Name": wod['title'], "Result": res, "Weight": bw, "Sciatica_Score": s_score, "Notes": log_notes}
        if save_entry(entry):
            st.success("WOD Entry Logged!")
            st.balloons()

with tab3:
    try:
        history = conn.read(ttl=0)
        if not history.empty:
            history['Date'] = pd.to_datetime(history['Date'])
            st.line_chart(history.set_index('Date')[['Sciatica_Score', 'Weight']])
    except: st.info("Logged sessions will generate visual performance charts.")
                        
