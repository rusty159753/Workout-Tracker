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
    </style>
    """, unsafe_allow_html=True)

# --- Session State Initialization ---
if 'wod_data' not in st.session_state:
    st.session_state.wod_data = None

# --- Scraper Function ---
def scrape_crossfit_wod():
    url = "https://www.crossfit.com/workout/"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/04.1"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract WOD details
        title = soup.find('h3', class_='content-title')
        title_text = title.text.strip() if title else "Today's WOD"
        
        content = soup.find('div', class_='content')
        workout_text = content.text.strip() if content else "No workout details found. Please enter manually."
        
        scaling_sections = soup.find_all('div', class_='scaling')
        scaling_text = "\n".join([s.text.strip() for s in scaling_sections]) if scaling_sections else "Scaling: Adjust for YMCA equipment and back safety."
        
        # Smart Scoring Detection
        score_type = "For Time"
        if "AMRAP" in workout_text.upper() or "REPS" in workout_text.upper():
            score_type = "AMRAP"
            
        return {
            "title": title_text,
            "workout": workout_text,
            "scaling": scaling_text,
            "score_type": score_type
        }
    except Exception as e:
        return {"title": "Error", "workout": f"Scraping failed: {e}", "scaling": "", "score_type": "Other"}

# --- Data Handshake ---
conn = st.connection("gsheets", type=GSheetsConnection)

def save_entry(data):
    try:
        # Fetch current data to check schema
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
        height=200
    )

with tab2:
    st.subheader("Performance Log")
    col1, col2 = st.columns(2)
    
    with col1:
        # High-visibility sliders for gym floor use
        sciatica_score = st.slider("Sciatica/Back Sensitivity (1-10)", 1, 10, 2)
        weight = st.slider("Body Weight (lbs)", 145, 170, 155)
    
    with col2:
        # Dynamic input based on WOD type
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
        # Direct pull from the Google Sheet
        history = conn.read(ttl=0)
        if not history.empty:
            # Sort data by date for proper charting
            history['Date'] = pd.to_datetime(history['Date'])
            history = history.sort_values('Date')
            
            st.write("### Sciatica vs. Weight Trends")
            # Charts help identify if body weight increases trigger back pain
            chart_data = history.set_index('Date')[['Sciatica_Score', 'Weight']]
            st.line_chart(chart_data)
            
            st.write("### Recent Logs")
            st.dataframe(history.tail(5), use_container_width=True)
        else:
            st.warning("No data found in Google Sheets. Start logging to see analytics!")
    except Exception as e:
        st.info("Awaiting initial data connection for visualization.")
