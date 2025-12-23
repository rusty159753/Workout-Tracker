import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- Page Config ---
st.set_page_config(page_title="TriDrive Performance", page_icon="🚴‍♂️", layout="centered")

# --- Custom Styling ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; background-color: #ff4b4b; color: white; font-weight: bold; }
    .stTextInput>div>div>input { background-color: #262730; color: white; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 20px; border-radius: 10px; font-size: 1.1rem; line-height: 1.6; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- Precise Anchor-to-Stop Scraper ---
def scrape_crossfit_wod():
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Target the YYMMDD anchor
        today_code = datetime.date.today().strftime("%y%m%d")
        
        # 2. Extract every line of text from the article
        article = soup.find('article')
        if not article:
            return {"title": "Error", "workout": "Workout container not reachable.", "scaling": "", "score_type": "Other"}

        raw_text = article.get_text(separator="|||", strip=True)
        lines = [line.strip() for line in raw_text.split("|||") if line.strip()]
        
        wod_content = []
        scaling_content = []
        capture_mode = "WAITING" 
        title = "Today's WOD"

        for line in lines:
            # TRIGGER: Find today's date code
            if today_code in line:
                capture_mode = "WOD"
                continue
            
            # TITLE LOGIC: First non-blank line after date
            if capture_mode == "WOD" and title == "Today's WOD":
                if "Workout of the Day" not in line:
                    title = line
                continue

            # STOP PHRASE: Hard stop for the WOD section
            if "Post time to comments" in line:
                capture_mode = "SCALING_HUNT" # Move to scaling search
                continue
            
            # SCALING TRIGGER: Resume capture for scaling
            if capture_mode == "SCALING_HUNT" and "Scaling" in line:
                capture_mode = "SCALING"
                continue

            # END OF POST: Final stop
            if any(stop in line for stop in ["View results", "Comments"]):
                break

            # DATA DISTRIBUTION
            if capture_mode == "WOD":
                wod_content.append(line)
            elif capture_mode == "SCALING":
                scaling_content.append(line)

        return {
            "title": title,
            "workout": "\n\n".join(wod_content) if wod_content else "Isabel: 30 Snatches for time (135/95 lbs)",
            "scaling": "\n\n".join(scaling_content) if scaling_content else "Scaling: Reduce weight to maintain speed.",
            "score_type": "AMRAP" if any("AMRAP" in l.upper() for l in wod_content) else "For Time"
        }

    except Exception as e:
        return {"title": "Manual Entry Mode", "workout": f"Technical Issue: {e}", "scaling": "", "score_type": "Other"}

# --- Data Persistence ---
conn = st.connection("gsheets", type=GSheetsConnection)

def save_entry(data):
    try:
        existing = conn.read(ttl=0)
        new_row = pd.DataFrame([data])
        updated = pd.concat([existing, new_row], ignore_index=True) if not existing.empty else new_row
        conn.update(data=updated)
        return True
    except:
        return False

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
    st.write("### YMCA Scaling & Adaptations")
    st.text_area("YMCA Safety Notes:", value=wod['scaling'], height=300)

with tab2:
    st.subheader("Performance Log")
    col1, col2 = st.columns(2)
    with col1:
        sciatica = st.slider("Sciatica Sensitivity", 1, 10, 2)
        weight = st.slider("Body Weight", 145, 170, 158)
    with col2:
        res = st.text_input("Score", placeholder="e.g. 12:45")
        notes = st.text_area("Gym Notes", placeholder="Back felt...")
    
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
            st.dataframe(history.tail(5), use_container_width=True)
    except:
        st.info("Log a workout to see trends.")
        
