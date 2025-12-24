import streamlit as st
import requests
from bs4 import BeautifulSoup
import datetime
import re

def execute_dynamic_boundary_scrape():
    now = datetime.date.today()
    target_url = now.strftime("https://www.crossfit.com/wod/%Y/%m/%d")
    headers = {"User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1)"}
    
    try:
        response = requests.get(target_url, headers=headers, timeout=15)
        if response.status_code == 200:
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. STRIP NON-CONTENT BLOCKS
            for noise in soup(["nav", "footer", "header", "script", "style", "aside"]):
                noise.decompose()
            
            # 2. GET TEXT STREAM
            full_text = soup.get_text(separator="  ", strip=True)
            
            # 3. DYNAMIC DATE START (The Flexible 6-String)
            # This regex allows for any number of spaces between the YY MM DD
            # It also doesn't care if 'Tuesday' or other words come before it.
            date_signature = now.strftime("%y\s*?%m\s*?%d") 
            start_match = re.search(date_signature, full_text)
            
            if start_match:
                start_idx = start_match.start()
                
                # 4. VERB-DRIVEN CTA (The Verified End)
                # Looking for a Verb (Post/Log/Record) followed by 'comments'
                cta_pattern = r"(Post|Log|Share|Record|Submit|Check).*?comments"
                end_match = re.search(cta_pattern, full_text[start_idx:], re.IGNORECASE)
                
                if end_match:
                    # Capture up to the end of the CTA sentence
                    end_idx = start_idx + end_match.end()
                    workout_content = full_text[start_idx:end_idx].strip()
                    
                    # 5. Rx SYMBOL PROTECTION
                    # Replacing symbols ensures clean rendering on the Pixel
                    workout_content = workout_content.replace('♂', '(M)').replace('♀', '(F)')
                    
                    return {
                        "workout": workout_content,
                        "url": target_url,
                        "status": "Validated Success"
                    }
                else:
                    # Fallback: Capture a large block if the specific CTA is missing
                    return {
                        "workout": full_text[start_idx:start_idx+2000].strip(),
                        "url": target_url,
                        "status": "Fallback: CTA Missing"
                    }
                    
        return {"error": f"HTTP {response.status_code}: Site unreachable."}
    except Exception as e:
        return {"error": str(e)}

# --- UI LAYER ---
st.set_page_config(page_title="TRI DRIVE", page_icon="⚡")
st.title("TRI⚡DRIVE")

wod = execute_dynamic_boundary_scrape()

if wod and "workout" in wod:
    st.subheader(f"WOD {datetime.date.today().strftime('%y%m%d')}")
    # Display the result in a clear, formatted box
    st.info(wod['workout'])
    st.sidebar.success(f"Logic: {wod['status']}")
    st.sidebar.markdown(f"[Source Page]({wod['url']})")
else:
    st.error("Boundary Failure: Could not locate the dynamic Date Header or Action Verb.")
    
