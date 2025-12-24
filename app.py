# --- 4. UTILITY: The Formatter (Upgraded Janitor) ---
def sanitize_text(text):
    if not text: return ""
    
    # 1. Clean weird quote characters
    replacements = {"â": "'", "’": "'", "‘": "'", "“": '"', "”": '"', "–": "-", "—": "-", "…": "..."}
    for bad, good in replacements.items():
        text = text.replace(bad, good)
        
    soup = BeautifulSoup(text, "html.parser")
    
    # 2. Convert HTML structure to Markdown Visuals
    # Replace line breaks with newlines
    for br in soup.find_all("br"): 
        br.replace_with("\n")
    
    # Replace list items with bullet points and newlines
    for li in soup.find_all("li"): 
        li.insert_before("\n• ")
        li.insert_after("\n")
        
    # Replace paragraphs and headers with double newlines
    for block in soup.find_all(['p', 'div', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol']):
        block.insert_before("\n\n")
        block.insert_after("\n\n")

    # 3. Extract text with NEWLINE separator (Critical Fix)
    text = soup.get_text(separator="\n", strip=True)
    
    # 4. Regex Cleanup
    text = unicodedata.normalize("NFKD", text)
    
    # Force "Resources:" to its own line
    text = text.replace("Resources:", "\n\n**Resources:**\n")
    
    # Fix mashed lists (e.g., "1. Run 2. Swim" -> "1. Run\n2. Swim")
    # This looks for a number followed by a dot or space, preceded by a lowercase letter
    text = re.sub(r'([a-z])\s+(\d+[\.\s])', r'\1\n\2', text)
    
    # Collapse massive gaps
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()
tegy'):
            with st.expander("Stimulus & Strategy"):
                st.markdown(wod['strategy'].replace("\n", "  \n"))
        if any([wod.get('scaling'), wod.get('intermediate'), wod.get('beginner')]):
            with st.expander("Scaling Options"):
                t1, t2, t3 = st.tabs(["Rx", "Intermediate", "Beginner"])
                with t1: st.markdown(str(wod.get('scaling', '')).replace("\n", "  \n"))
                with t2: st.markdown(str(wod.get('intermediate', '')).replace("\n", "  \n"))
                with t3: st.markdown(str(wod.get('beginner', '')).replace("\n", "  \n"))

# 3. WORKBENCH (Active Athlete Mode)
elif st.session_state['app_mode'] == 'WORKBENCH':
    st.caption("🏋️ ACTIVE SESSION")
    wod = st.session_state.get('current_wod', {})
    
    # Header
    title_safe = wod.get('title', 'Unknown WOD')
    st.success("Target: " + title_safe)
    
    # THE KINETIC PARSER
    raw_workout = str(wod.get('workout', ''))
    lines = raw_workout.split('\n')
    
    st.markdown("### 📋 Checklist")
    
    # Dynamic Checkbox Generation
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        
        # Heuristics
        is_header = False
        if line.endswith(":") or "rounds" in line.lower() or "amrap" in line.lower():
            is_header = True
            
        is_movement = False
        if line.startswith("•") or line[0].isdigit():
            is_movement = True
            
        # Rendering
        if is_header and not is_movement:
            st.markdown("**" + line + "**")
        elif is_movement:
            key_id = "chk_" + str(idx)
            clean_text = line.replace("• ", "").strip()
            st.checkbox(clean_text, key=key_id)
        else:
            st.markdown(line)
            
    st.divider()
    
    # LOGGING & EXIT
    st.markdown("#### 🏁 Post Score")
    
    # INPUT FIELD (Added per Requirements Phase 5)
    result_input = st.text_input("Final Time / Load / Score", key="res_input")
    
    c1, c2 = st.columns(2)
    with c1:
        if st.button("❌ Exit (No Save)"):
            st.session_state['app_mode'] = 'HOME'
            st.rerun()
            
    with c2:
        if st.button("💾 Log to Whiteboard", type="primary"):
            if not result_input:
                st.error("Enter a score to log.")
            else:
                st.toast("Syncing to Cloud...")
                
                # Execute Data Push
                success = push_score_to_sheet(title_safe, result_input)
                
                if success:
                    st.success("Score Posted!")
                    # Clear Progress Flag
                    st.session_state['wod_in_progress'] = False
                    # Delay slightly or just rerun
                    st.session_state['app_mode'] = 'HOME'
                    st.rerun()
                else:
                    st.error("Sync Failed. Check Connection.")

# === END OF SYSTEM FILE ===
   # We take the raw workout text and attempt to structure it
            raw_workout = wod.get('workout', '')
            
            # Safety Check: Ensure string
            if not isinstance(raw_workout, str):
                raw_workout = str(raw_workout)

            # Split by newlines (The Janitor already ensured clean \n separators)
            lines = raw_workout.split('\n')
            
            # PARSING LOOP
            # We track an index 'idx' to create unique keys for every checkbox
            st.markdown("### 📋 Mission Checklist")
            
            for idx, line in enumerate(lines):
                line = line.strip()
                
                # Skip empty noise
                if not line:
                    continue
                    
                # HEURISTIC 1: Detect Headers/Schemes
                # If a line ends in a colon (:) or implies a round structure, it is a header.
                is_header = False
                if line.endswith(":") or "rounds" in line.lower() or "amrap" in line.lower():
                    is_header = True
                
                # HEURISTIC 2: Detect Movements
                # If it starts with a number (reps) or a bullet point, it is likely a movement.
                # The Janitor injected "• " for list items, so we look for that.
                is_movement = False
                if line.startswith("•") or line[0].isdigit():
                    is_movement = True
                
                # RENDER LOGIC
                if is_header and not is_movement:
                    # Render as bold instruction using concatenation
                    st.markdown("**" + line + "**")
                
                elif is_movement:
                    # Render as Checkbox
                    # Key generation uses strict unique ID to prevent state collision
                    # NO F-STRINGS: "chk_" + str(idx)
                    checkbox_key = "chk_" + str(idx)
                    
                    # Clean the bullet for display if present
                    display_text = line.replace("• ", "").strip()
                    
                    st.checkbox(display_text, key=checkbox_key)
                    
                else:
                    # Fallback: Render as standard text note
                    st.markdown(line)

            st.divider()
            
            # 4. NAVIGATION
            col1, col2 = st.columns(2)
            with col1:
                if st.button("⬅️ Abort & Return"):
                    st.session_state['view_mode'] = 'VIEWER'
                    st.rerun()
            with col2:
                # Placeholder for Phase 4
                st.button("💾 Save to Log (Locked)", disabled=True)

# === END OF SYSTEM FILE ===
