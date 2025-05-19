import streamlit as st
import tempfile
from pathlib import Path
from datetime import datetime

from extractor import pdf_to_text
from parser_llm import parse_resume_llm
from generator_llm import generate_html_llm
from generator_rule import json_to_html
from parser_rule import parse_resume_rule

# Initialize session state variables if they don't exist
if 'generated_html' not in st.session_state:
    st.session_state.generated_html = ""
if 'process_log_entries' not in st.session_state: # Renamed for clarity
    st.session_state.process_log_entries = []
if 'display_html' not in st.session_state:
    st.session_state.display_html = False
if 'selected_mode' not in st.session_state: 
    st.session_state.selected_mode = "LLM (Direct HTML)"


st.set_page_config(layout="wide", page_title="Résumé-to-Site")
st.title("📄 → 🌐 Résumé-to-Site")

# Radio button for mode selection
def on_mode_change():
    st.session_state.generated_html = ""
    st.session_state.process_log_entries = []
    st.session_state.display_html = False

st.radio(
    "Choose generation mode:",
    options=["LLM (Direct HTML)", "LLM (JSON + Template)", "Rule-based (JSON + Template)"],
    key='selected_mode',
    on_change=on_mode_change,
    index=["LLM (Direct HTML)", "LLM (JSON + Template)", "Rule-based (JSON + Template)"].index(st.session_state.selected_mode)
)

pdf_file = st.file_uploader("Upload PDF résumé", type="pdf")

if pdf_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_file.read())
        pdf_path = Path(tmp.name)

    with st.spinner("Extracting text from PDF..."):
        raw_text = pdf_to_text(pdf_path)
    st.session_state.raw_text = raw_text

    if st.button("✨ Generate Website ✨", type="primary", use_container_width=True):
        st.session_state.generated_html = ""
        st.session_state.process_log_entries = [] 
        st.session_state.display_html = False
        
        PLAN_PREFIX = "📝 **Website Plan:**\\n```\\n"
        PLAN_SUFFIX = "\\n```"

        if st.session_state.selected_mode == "LLM (Direct HTML)":
            st.subheader("LLM-Generated HTML Website")
            
            with st.status("🚀 Starting Direct HTML Generation...", expanded=True) as status_ui:
                
                def status_update_callback(message: str):
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    full_log_entry = f"{timestamp} - {message}"

                    if message.startswith(PLAN_PREFIX) and message.endswith(PLAN_SUFFIX):
                        plan_content = message 
                        status_ui.markdown(plan_content) 
                        status_ui.update(label="Plan displayed. Generating HTML...")
                    elif message.startswith("❌"):
                        status_ui.error(message) 
                        st.session_state.process_log_entries.append(full_log_entry)
                    else:
                        status_ui.write(full_log_entry) 
                        if not any(message.startswith(p) for p in ["📝", "✅", "📄", "🛠️", "🤖", "🔍"]):
                             status_ui.update(label=message)
                        st.session_state.process_log_entries.append(full_log_entry)

                try:
                    html_output = generate_html_llm(st.session_state.raw_text, status_callback=status_update_callback)
                    st.session_state.generated_html = html_output
                    st.session_state.display_html = True
                    if "Error" not in html_output and "Input Error" not in html_output and "Processing Error" not in html_output:
                        status_ui.update(label="✅ HTML generation complete!", state="complete")
                    else:
                        status_ui.update(label="⚠️ HTML generation finished with issues or input error.", state="error")
                except Exception as e:
                    st.error(f"An unexpected error occurred during HTML generation: {e}")
                    status_ui.update(label="💥 Unexpected error during generation.", state="error")
                    st.session_state.process_log_entries.append(f'{datetime.now().strftime("%H:%M:%S")} - Error: {e}')

        elif st.session_state.selected_mode == "LLM (JSON + Template)":
            st.subheader("LLM (JSON) + Template-Generated Website")
            with st.spinner("Parsing resume with LLM (JSON)..."):
                parsed_json = parse_resume_llm(st.session_state.raw_text)
            st.success("✅ Resume parsed to JSON by LLM.")
            st.json(parsed_json) 
            with st.spinner("Generating HTML from JSON with Template..."):
                html_output = json_to_html(parsed_json, inline=True)
            st.session_state.generated_html = html_output
            st.session_state.display_html = True
            st.success("✅ HTML generated from JSON (LLM) and template.")

        elif st.session_state.selected_mode == "Rule-based (JSON + Template)":
            st.subheader("Rule-based (JSON) + Template-Generated Website")
            with st.spinner("Parsing resume with Rules..."):
                parsed_json = parse_resume_rule(st.session_state.raw_text)
            st.success("✅ Resume parsed to JSON by Rules.")
            st.json(parsed_json) 
            with st.spinner("Generating HTML from JSON with Template..."):
                html_output = json_to_html(parsed_json, inline=True)
            st.session_state.generated_html = html_output
            st.session_state.display_html = True
            st.success("✅ HTML generated from JSON (Rules) and template.")
        
        if pdf_path.exists():
            pdf_path.unlink()

if st.session_state.display_html and st.session_state.generated_html:
    st.subheader("🌐 Website Preview")
    st.components.v1.html(st.session_state.generated_html, height=600, scrolling=True)
    
    final_html_for_download = st.session_state.generated_html
    if st.session_state.selected_mode != "LLM (Direct HTML)":
        if "raw_text" in st.session_state: 
            if st.session_state.selected_mode == "LLM (JSON + Template)":
                parsed_json_dl = parse_resume_llm(st.session_state.raw_text) 
                final_html_for_download = json_to_html(parsed_json_dl, inline=False)
            elif st.session_state.selected_mode == "Rule-based (JSON + Template)":
                parsed_json_dl = parse_resume_rule(st.session_state.raw_text) 
                final_html_for_download = json_to_html(parsed_json_dl, inline=False)
    
    st.download_button(
        label="📥 Download HTML File",
        data=final_html_for_download,
        file_name="index.html",
        mime="text/html",
        use_container_width=True
    )
elif not pdf_file:
    st.info("👋 Upload a PDF résumé to get started!")

st.write("---")
st.markdown("<p style='text-align: center; color: grey;'>Résumé-to-Site</p>", unsafe_allow_html=True)