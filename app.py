import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import re

def execute_googlebot_targeted_scrape():
    # 1. PREDICTIVE URL CONSTRUCTION
    now = datetime.date.today()
    # CrossFit URL format: /wod/YYYY/MM/DD
    target_url = now.strftime("https://www.crossfit.com/wod/%Y/%m/%d")
    
    # 2. GOOGLEBOT SPOOFING (High-Priority Bypass)
    headers = {
        "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
    }
    
    try:
        # Go straight to the workout page for today
        response = requests.get(target_url, headers=headers, timeout=15)
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 3. ROBUST CONTENT EXTRACTION
            # We look for the workout text in the article or main content div
            article = soup.find('article') or soup.find('div', class_=re.compile(r'content|post|entry|wod', re.I))
            
            if article:
                # Extract text and clean up whitespace
                full_text = article.get_text(separator="\n", strip=True)
                # Verify we aren't looking at a "Rest Day" or error page
                return {
                    "title": now.strftime("%y%m%d"),
                    "workout": full_text,
                    "url": target_url
                }
        
        # Fallback: If today isn't out yet, try yesterday
        yesterday_url = (now - datetime.timedelta(days=1)).strftime("https://www.crossfit.com/wod/%Y/%m/%d")
        res_yest = requests.get(yesterday_url, headers=headers, timeout=15)
        if res_yest.status_code == 200:
            soup_y = BeautifulSoup(res_yest.content, 'html.parser')
            article_y = soup_y.find('article') or soup_y.find('div', class_=re.compile(r'content|post|entry|wod', re.I))
            if article_y:
                return {
                    "title": (now - datetime.timedelta(days=1)).strftime("%y%m%d"),
                    "workout": article_y.get_text(separator="\n", strip=True),
                    "url": yesterday_url
                }

        return {"debug": f"Status: {response.status_code} | Target: {target_url}"}
        
    except Exception as e:
        return {"error": str(e)}

# --- UI LAYER ---
st.title("TRI⚡DRIVE")

wod = execute_googlebot_targeted_scrape()

if isinstance(wod, dict) and "workout" in wod:
    st.subheader(f"WOD: {wod['title']}")
    st.code(wod['workout'], language=None)
    st.sidebar.success("Direct-Target Success")
    st.sidebar.markdown(f"[View on Source Site]({wod['url']})")
else:
    st.error("Target Workout Page not yet accessible via Googlebot bypass.")
    if "debug" in wod:
        with st.expander("Diagnostic Telemetry"):
            st.text(wod["debug"])
            
