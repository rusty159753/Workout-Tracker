import streamlit as st
import requests
import datetime
import re

def execute_legacy_fail_safe():
    # Target the legacy feed which is harder to block
    url = "https://www.crossfit.com/feed"
    headers = {"User-Agent": "WOD-Reader-2025"}
    
    today_id = datetime.date.today().strftime("%y%m%d")
    
    try:
        # We use a stream=True to ensure we get the raw data even if the server is slow
        response = requests.get(url, headers=headers, timeout=15)
        raw_text = response.text
        
        # 1. FIND THE WORKOUT BY DATE
        # We search for the date ID (251223) and grab everything until the end of that entry
        if today_id in raw_text:
            # Extract the section of the feed for today
            start_index = raw_text.find(today_id)
            # Find the workout description near this date
            desc_start = raw_text.find("<description><![CDATA[", start_index)
            desc_end = raw_text.find("]]></description>", desc_start)
            
            if desc_start != -1 and desc_end != -1:
                workout_content = raw_text[desc_start + 22:desc_end]
                # Clean up any leftover HTML tags
                workout_content = re.sub(r'<[^>]+>', '\n', workout_content)
                
                return {
                    "title": today_id,
                    "workout": workout_content.strip()
                }
        
        # If today isn't there, the feed is lagging—show a clear debug sample
        return {"debug": raw_text[:500] if raw_text else "SERVER RETURNED EMPTY STRING"}
        
    except Exception as e:
        return {"error": str(e)}

# --- UI ---
st.title("TRI⚡DRIVE")

with st.spinner("Accessing Legacy Data Stream..."):
    wod = execute_legacy_fail_safe()

if isinstance(wod, dict) and "workout" in wod:
    st.subheader(f"WOD: {wod['title']}")
    st.code(wod['workout'], language=None)
    st.sidebar.success("Found: Legacy Feed Continuity")
else:
    st.error("2025 Continuity Alert: Data Stream Interrupted.")
    with st.expander("Diagnostic Telemetry"):
        st.text(wod.get("debug", "Connection Blocked"))
        
