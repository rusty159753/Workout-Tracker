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
    .stInfo { background-color: #1e1e26; border-left: 5px solid #ff4b4b; }
    </style>
    """, unsafe_allow_html=True)

# --- Session State Initialization ---
if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- Advanced Targeted Scraper ---
def scrape_crossfit_wod():
    url = "https://www.crossfit.com/workout/"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/04.1"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. Targeted Hunt: CrossFit hides the WOD in an 'article' or a 'content' div
        article = soup.find('article') or soup.find('div', class_='content')
        
        if not article:
            return {"title": "Error", "workout": "Workout container not found.", "scaling": "", "score_type": "Other"}

        # 2. Extract Title (e.g., 'Isabel')
        # We look for the first header that isn't a site-wide nav link
        title_text = "Today's WOD"
        possible_titles = article.find_all(['h1', 'h2', 'h3'])
        for t in possible_titles:
            text = t.get_text().strip()
            # If it's short and doesn't look like a date or nav, it's the title
            if text and len(text) < 30 and not any(x in text.lower() for x in ['crossfit', 'gym', 'courses']):
                title_text = text
                break
        
        # 3. Targeted Body Extraction
        # We specifically extract paragraphs and lists to avoid the <div> soup
        content_elements = article.find_all(['p', 'ul', 'li', 'h4'])
        
        # JUNK FILTER: Phrases that CrossFit uses for marketing, not the workout
        junk = ["find a gym", "open a crossfit", "getting started", "what is crossfit", 
                "cure", "level 1", "subscribe", "courses", "view more", "military"]
        
        cleaned_body = []
        scaling_section = []
        is_scaling = False
        
        for elem in content_elements:
            text = elem.get_text().strip()
            if not text or any(j in text.lower() for j in junk):
                continue
            
            # Switch to scaling section if keyword found
            if "scaling" in text.lower() or "beginner" in text.lower() or "intermediate" in text.lower():
                is_scaling = True
            
            if is_scaling:
                scaling_section.append(text)
            else:
                cleaned_body.append(text)

        workout_text = "\n\n".join(cleaned_body)
        scaling_text = "\n\n".join(scaling_section) if scaling_section else "Scaling: Adjust for back safety and YMCA equipment."
        
        # 4. Smart Score Detection
        score_type = "AMRAP" if any(x in workout_text.upper() for x in ["AMRAP", "REPS", "ROUNDS"]) else "For Time"
            
        return {
            "title": title_text,
            "workout": workout_text,
            "scaling": scaling_text,
            "score_type": score_type
        }
    except Exception as e:
        return {"title": "Scraper Error", "workout": f"Failed: {e}", "scaling": "", "score_type": "Other"}

# --- Data Handshake ---
conn = st.connection("gsheets", type=GSheetsConnection)

def save_entry(data):
    try:
        existing_data = conn.read(ttl=0)
        new_row = pd.DataFrame([data])
        if existing_data.empty:
            updated_df = new_row
        else:
            updated_df = pd.concat([existing_data, new_row], ignore_index=True)
        conn.update(data=updated_df)
        return True
    except Exception as e:
        st.error(f"Save failed: {e}")
        return False

# --- UI Header ---
st.title("TRI⚡DRIVE")
st.caption("43M | 150-160 lbs | Sciatica-Resilient Performance Hub")

# --- App Logic ---
if st.session_state.wod_data is None:
    with st.spinner("Scraping Daily WOD..."):
        st.session_state.wod_data = scrape_crossfit_wod()

wod = st.session_state.wod_data

tab1, tab2, tab3 = st.tabs(["🔥 The Daily Drive", "📊 Metrics", "📈 Apex Analytics"])

with tab1:
    st.subheader(wod['title'])
    st.info(wod['workout'])
    
    st.write("### YMCA Scaling & Adaptations")
    scaled_workout = st.text_area(
        "Modify movements for back safety:",
        value=wod['scaling'],
        height=300
    )

with tab2:
    st.subheader("Performance Log")
    col1, col2 = st.columns(2)
    
    with col1:
        sciatica_score = st.slider("Sciatica/Back Sensitivity (1-10)", 1, 10, 2)
        weight = st.slider("Body Weight (lbs)", 145, 170, 155)
    
    with col2:
        if wod['score_type'] == "AMRAP":
            result = st.text_input("Score (Total Reps/Rounds)", placeholder="e.g. 8 Rounds + 12")
        else:
            result = st.text_input("Score (Time)", placeholder="e.g. 14:22")
        notes = st.text_area("Internal Dialogue / Back Status", placeholder="Felt stiffness in L5-S1 during cleans...")

    if st.button("Save to TriDrive Ledger"):
        entry = {
            "Date": datetime.date.today().strftime("%Y-%m-%d"),
            "WOD_Name": wod['title'],
            "Result": result,
            "Weight": weight,
            "Sciatica_Score": sciatica_score,
            "Notes": notes
        }
        if save_entry(entry):
            st.success("Entry locked into Handshake!")
            st.balloons()

with tab3:
    st.subheader("Visualizing Resilience")
    try:
        history = conn.read(ttl=0)
        if not history.empty:
            history['Date'] = pd.to_datetime(history['Date'])
            history = history.sort_values('Date')
            st.write("### Sciatica vs. Weight Trends")
            chart_data = history.set_index('Date')[['Sciatica_Score', 'Weight']]
            st.line_chart(chart_data)
            st.write("### Recent Logs")
            st.dataframe(history.tail(5), use_container_width=True)
        else:
            st.warning("No data found in Google Sheets. Start logging to see analytics!")
    except Exception as e:
        st.info("Awaiting initial data connection for visualization.")
        
