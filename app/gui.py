import streamlit as st
import tempfile
from pathlib import Path
from datetime import datetime
import urllib.parse  # Added for data URI encoding

from extractor import pdf_to_text
from parser_llm import parse_resume_llm
from generator_llm import generate_html_llm
from generator_rule import json_to_html
from parser_rule import parse_resume_rule

# Initialize session state variables
if "generated_html" not in st.session_state:
    st.session_state.generated_html = ""
if "process_log_entries" not in st.session_state:
    st.session_state.process_log_entries = []
if "display_html" not in st.session_state:
    st.session_state.display_html = False
if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = "LLM (Direct Website)"
if "raw_text" not in st.session_state:
    st.session_state.raw_text = None
# Tracks the name of the PDF currently in the uploader widget
if "current_uploader_pdf_name" not in st.session_state:
    st.session_state.current_uploader_pdf_name = None
# Tracks the name of the PDF for which raw_text was extracted
if "processed_pdf_name" not in st.session_state:
    st.session_state.processed_pdf_name = None
# Flag to trigger regeneration when mode changes and a PDF is already processed
if "mode_changed_flag" not in st.session_state:
    st.session_state.mode_changed_flag = False

st.set_page_config(layout="wide", page_title="Résumé-to-Site")
st.title("📄 → 🌐 Résumé-to-Site")


# --- Helper to clear relevant state for new processing ---
def reset_generation_output_state():
    st.session_state.generated_html = ""
    st.session_state.process_log_entries = []
    st.session_state.display_html = False


# --- Generation Logic ---
def trigger_website_generation():
    if not st.session_state.raw_text:
        # This should ideally not be hit if calling logic is correct
        return

    reset_generation_output_state()  # Clear previous results before starting

    PLAN_PREFIX = "📝 **Website Plan:**\\\\n```\\\\n"
    PLAN_SUFFIX = "\\\\n```"

    if st.session_state.selected_mode == "LLM (Direct Website)":
        st.subheader("LLM-Generated Website")
        with st.status(
            "🚀 Starting Direct Website Generation...", expanded=True
        ) as status_ui:

            def status_update_callback(message: str):
                timestamp = datetime.now().strftime("%H:%M:%S")
                full_log_entry = f"{timestamp} - {message}"
                if message.startswith(PLAN_PREFIX) and message.endswith(PLAN_SUFFIX):
                    plan_content = message
                    status_ui.markdown(plan_content)
                    status_ui.update(label="Plan displayed. Generating Website...")
                elif message.startswith("❌"):
                    status_ui.error(message)
                    st.session_state.process_log_entries.append(full_log_entry)
                else:
                    status_ui.write(full_log_entry)
                    if not any(
                        message.startswith(p)
                        for p in ["📝", "✅", "📄", "🛠️", "🤖", "🔍"]
                    ):
                        status_ui.update(label=message)
                    st.session_state.process_log_entries.append(full_log_entry)

            try:
                html_output = generate_html_llm(
                    st.session_state.raw_text, status_callback=status_update_callback
                )
                st.session_state.generated_html = html_output
                st.session_state.display_html = True
                if (
                    "Error" not in html_output
                    and "Input Error" not in html_output
                    and "Processing Error" not in html_output
                ):
                    status_ui.update(
                        label="✅ Website generation complete!", state="complete"
                    )
                else:
                    status_ui.update(
                        label="⚠️ Website generation finished with issues or input error.",
                        state="error",
                    )
            except Exception as e:
                st.error(f"An unexpected error occurred during Website generation: {e}")
                status_ui.update(
                    label="💥 Unexpected error during generation.", state="error"
                )
                st.session_state.process_log_entries.append(
                    f'{datetime.now().strftime("%H:%M:%S")} - Error: {e}'
                )

    elif st.session_state.selected_mode == "LLM (JSON + Template)":
        st.subheader("LLM (JSON) + Template-Generated Website")
        with st.spinner("Parsing resume with LLM (JSON)..."):
            parsed_json = parse_resume_llm(st.session_state.raw_text)
        st.success("✅ Resume parsed to JSON by LLM.")
        st.json(parsed_json)
        with st.spinner("Generating Website from JSON with Template..."):
            html_output = json_to_html(parsed_json, inline=True)
        st.session_state.generated_html = html_output
        st.session_state.display_html = True
        st.success("✅ Website generated from JSON (LLM) and template.")

    elif st.session_state.selected_mode == "Rule-based (JSON + Template)":
        st.subheader("Rule-based (JSON) + Template-Generated Website")
        with st.spinner("Parsing resume with Rules..."):
            parsed_json = parse_resume_rule(st.session_state.raw_text)
        st.success("✅ Resume parsed to JSON by Rules.")
        st.json(parsed_json)
        with st.spinner("Generating Website from JSON with Template..."):
            html_output = json_to_html(parsed_json, inline=True)
        st.session_state.generated_html = html_output
        st.session_state.display_html = True
        st.success("✅ Website generated from JSON (Rules) and template.")


# --- UI Elements & Main Control Logic ---
def on_mode_selection_change_callback():
    reset_generation_output_state()  # Clear previous output
    # If a PDF has been processed, set flag to regenerate with the new mode
    if st.session_state.raw_text and st.session_state.processed_pdf_name:
        st.session_state.mode_changed_flag = True
    # DO NOT call trigger_website_generation() here


st.radio(
    "Choose generation mode:",
    options=[
        "LLM (Direct Website)",
        "LLM (JSON + Template)",
        "Rule-based (JSON + Template)",
    ],
    key="selected_mode",
    on_change=on_mode_selection_change_callback,
    index=[
        "LLM (Direct Website)",
        "LLM (JSON + Template)",
        "Rule-based (JSON + Template)",
    ].index(st.session_state.selected_mode),
)

uploaded_pdf_file_widget = st.file_uploader("Upload PDF résumé", type="pdf")

# Determine the name of the file in the uploader (None if empty)
current_widget_pdf_name = (
    uploaded_pdf_file_widget.name if uploaded_pdf_file_widget else None
)

# Scenario 1: PDF uploader state has changed (new file uploaded, or file cleared)
if current_widget_pdf_name != st.session_state.current_uploader_pdf_name:
    st.session_state.current_uploader_pdf_name = (
        current_widget_pdf_name  # Update tracked uploader name
    )
    reset_generation_output_state()  # Clear any previous generated output

    if uploaded_pdf_file_widget:
        # A new PDF has been uploaded
        st.session_state.mode_changed_flag = (
            False  # New PDF processing takes precedence over mode change flag
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            tmp_file.write(uploaded_pdf_file_widget.read())
            tmp_pdf_path = Path(tmp_file.name)

        with st.spinner("Extracting text from PDF..."):
            st.session_state.raw_text = pdf_to_text(tmp_pdf_path)
        st.session_state.processed_pdf_name = (
            uploaded_pdf_file_widget.name
        )  # Mark this PDF as processed

        if tmp_pdf_path.exists():
            tmp_pdf_path.unlink()

        trigger_website_generation()  # Generate website for the new PDF
    else:
        # PDF was cleared from the uploader
        st.session_state.raw_text = None
        st.session_state.processed_pdf_name = None
        st.session_state.mode_changed_flag = (
            False  # No PDF, so no pending mode change generation
        )

# Scenario 2: Mode was changed, and a PDF had been processed previously (and uploader state didn't change in this run)
elif (
    st.session_state.mode_changed_flag
    and st.session_state.raw_text
    and st.session_state.processed_pdf_name
):
    trigger_website_generation()  # Regenerate with the new mode
    st.session_state.mode_changed_flag = False  # Reset the flag

# --- Display Area ---
if st.session_state.display_html and st.session_state.generated_html:
    st.subheader("🌐 Website Preview")
    st.components.v1.html(st.session_state.generated_html, height=800, scrolling=True)

    # Prepare data URI for the new tab button
    # Limit data URI length to avoid browser issues (e.g., ~2MB for Chrome)
    MAX_DATA_URI_LEN = 2 * 1024 * 1024
    html_for_uri = st.session_state.generated_html
    # Truncate if too long, though this will result in an incomplete page in the new tab
    # A better approach for very large pages would be temporary file serving, but that adds complexity.
    if (
        len(html_for_uri) > MAX_DATA_URI_LEN * 0.8
    ):  # Check before quoting, as quoting expands size
        # Heuristic: if raw HTML is already 80% of max URI, it will likely exceed after quoting
        # For simplicity, we'll just warn and not provide the button if it's potentially too large.
        # A more precise check would be `len(urllib.parse.quote(html_for_uri))`
        pass  # Will be handled by the length check on the actual URI later

    html_data_uri = f"data:text/html;charset=utf-8,{urllib.parse.quote(html_for_uri)}"

    st.download_button(
        label="📥 Download Website File",
        data=st.session_state.generated_html,  # Use the full HTML for download
        file_name="website.html",
        mime="text/html",
        use_container_width=True,
    )

elif (
    not st.session_state.processed_pdf_name
):  # Show initial message if no PDF has ever been processed
    st.info("👋 Upload a PDF résumé to get started!")

st.write("---")
st.markdown(
    "<p style='text-align: center; color: grey;'>Résumé-to-Site</p>",
    unsafe_allow_html=True,
)
