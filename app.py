import streamlit as st
import requests
from bs4 import BeautifulSoup
import pandas as pd
import datetime
import re
from streamlit_gsheets import GSheetsConnection

# --- Page Config ---
st.set_page_config(page_title="TriDrive Performance", page_icon="🚴‍♂️", layout="centered")

# --- Custom Styling ---
st.markdown("""
    <style>
    .main { background-color: #0e1117; color: #fafafa; }
    .stButton>button { width: 100%; border-radius: 10px; height: 3.5em; background-color: #ff4b4b; color: white; font-weight: bold; }
    .stTextInput>div>div>input { background-color: #262730; color: white; }
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; padding: 20px; border-radius: 10px; font-size: 1.1rem; }
    </style>
    """, unsafe_allow_html=True)

if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- Precise Post Scraper ---
def scrape_crossfit_wod():
    # Targeted WOD-specific URL
    url = "https://www.crossfit.com/wod"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Eliminate global navigation to prevent menu-item scraping
        for junk in soup.find_all(['nav', 'header', 'footer', 'noscript']):
            junk.decompose()

        # 1. FIND THE DATE (The Absolute Anchor)
        # CrossFit uses a specific h3 or h4 for the YYMMDD code
        today_code = datetime.date.today().strftime("%y%m%d")
        
        # 2. EXTRACT THE POST CONTENT
        # The WOD post is almost always contained within an <article> or a specific div
        article = soup.find('article')
        if not article:
            return {"title": "Error", "workout": "Daily post container not found.", "scaling": "", "score_type": "Other"}

        # Get all textual elements in order
        elements = article.find_all(['h1', 'h2', 'h3', 'h4', 'p', 'ul', 'li'])
        
        wod_content = []
        scaling_content = []
        capture_state = "寻找DATE" # Seeking Date
        title = "Today's WOD"

        for elem in elements:
            text = elem.get_text(strip=True)
            if not text: continue

            # A. Detect Date Code (Start of Post)
            if today_code in text:
                capture_state = "WOD"
                continue
            
            # B. Identify Title (First line after Date/Workout of the Day)
            if capture_state == "WOD" and title == "Today's WOD" and "Workout of the Day" not in text:
                title = text
                continue

            # C. Detect Scaling Header
            if "Scaling" in text:
                capture_state = "SCALING"
                continue
            
            # D. Detect End of Post (Comments/Results)
            if any(stop in text for stop in ["Post time", "View results"]):
                capture_state = "END"
                break

            # E. Distribute Content
            if capture_state == "WOD":
                # If we hit Stimulus, we can choose to keep it or label it
                if "Stimulus" in text or "Strategy" in text:
                    wod_content.append(f"\n**{text}**")
                else:
                    wod_content.append(text)
            elif capture_state == "SCALING":
                scaling_content.append(text)

        return {
            "title": title if len(title) < 25 else "Benchmark",
            "workout": "\n\n".join(wod_content),
            "scaling": "\n\n".join(scaling_content) if scaling_content else "Scale for Isabel stimulus (under 15 min).",
            "score_type": "AMRAP" if "AMRAP" in str(wod_content).upper() else "For Time"
        }

    except Exception as e:
        return {"title": "Scraper Offline", "workout": f"Technical Issue: {e}", "scaling": "", "score_type": "Other"}

# --- Data Ledger Management ---
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

# --- App Structure ---
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
    # This text area is populated with the SCALING section we scraped
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
        st.info("Awaiting initial data entry.")
