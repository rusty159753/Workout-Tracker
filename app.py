import streamlit as st
import requests
import json
import datetime
import hashlib
import re

def execute_react_state_scrape():
    # We target the main page because the telemetry shows it contains the full state
    target_url = "https://www.crossfit.com"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    today_id = datetime.date.today().strftime("%y%m%d")
    
    try:
        response = requests.get(target_url, headers=headers, timeout=20)
        raw_html = response.text
        
        # 1. EXTRACT THE PRELOADED STATE
        # We look for the JSON object in the script tag the telemetry revealed
        state_match = re.search(r'window\.__PRELOADED_STATE__\s*=\s*({.*?});', raw_html, re.DOTALL)
        
        if state_match:
            state_json = state_match.group(1)
            data = json.loads(state_json)
            
            # 2. SEARCH THE STATE FOR THE WORKOUT
            # CrossFit's React state usually stores workouts in an 'items' or 'wod' key
            # We will search the entire JSON string for our date and its associated text
            if today_id in state_json:
                # We extract the specific workout text related to today's ID
                # This regex finds the date and pulls the subsequent text until the next entry
                content_match = re.search(rf'"{today_id}".*?"content":"(.*?)"', state_json)
                if content_match:
                    workout_text = content_match.group(1).encode().decode('unicode_escape')
                    # Clean up HTML artifacts from the JSON string
                    workout_text = re.sub(r'<[^>]+>', '\n', workout_text)
                    
                    return {
                        "title": today_id,
                        "workout": workout_text,
                        "hash": hashlib.sha256(workout_text.encode()).hexdigest()
                    }
        
        return {"debug": raw_html[:1000]}
    except Exception as e:
        return {"error": str(e)}

# --- UI ---
st.title("TRI⚡DRIVE")
wod = execute_react_state_scrape()

if isinstance(wod, dict) and "workout" in wod:
    st.subheader(f"WOD: {wod['title']}")
    st.code(wod['workout'], language=None)
    st.sidebar.success("Found: React State Data")
else:
    st.error("2025 Data locked in JavaScript State. Refining extraction...")
    with st.expander("Diagnostic Telemetry"):
        st.text(wod.get("debug", "No data"))
                    
