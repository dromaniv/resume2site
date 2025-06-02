import streamlit as st
import tempfile
from pathlib import Path
from datetime import datetime
import urllib.parse  # Added for data URI encoding
import webbrowser
import time

from extractor import pdf_to_text
from parser_llm import parse_resume_llm
from generator_llm import generate_html_llm, apply_user_changes_llm
from generator_rule import json_to_html
from parser_rule import parse_resume_rule
from temp_server import serve_html_temporarily, cleanup_temp_server

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
if "website_plan" not in st.session_state:
    st.session_state.website_plan = ""
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "temp_server_url" not in st.session_state:
    st.session_state.temp_server_url = None
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

# Simple title with default Streamlit styling
st.title("📄 → 🌐 Résumé-to-Site")
st.markdown("Transform your PDF résumé into a stunning personal website")

# Comprehensive dark theme CSS - NO WHITE BACKGROUNDS ANYWHERE
st.markdown("""
<style>
/* Root app styling - dark theme */
.stApp {
    background-color: #1e1e1e !important;
    color: #ffffff !important;
}

/* Main content container */
.main .block-container {
    background-color: #1e1e1e !important;
    color: #ffffff !important;
}

/* All buttons - dark theme with gradients */
div.stButton > button {
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.5rem 1rem !important;
    font-weight: 500 !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
    width: 100% !important;
}

div.stButton > button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 4px 8px rgba(0,0,0,0.4) !important;
}

/* Primary buttons */
div.stButton > button[kind="primary"] {
    background: linear-gradient(90deg, #ff6b6b 0%, #ee5a24 100%) !important;
}

/* Secondary buttons */
div.stButton > button[kind="secondary"] {
    background: linear-gradient(90deg, #555 0%, #333 100%) !important;
}

/* Download buttons */
div.stDownloadButton > button {
    background: linear-gradient(90deg, #10ac84 0%, #1dd1a1 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.5rem 1rem !important;
    font-weight: 500 !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
    width: 100% !important;
}

/* Link buttons */
div.stLinkButton > a {
    background: linear-gradient(90deg, #3742fa 0%, #2f3542 100%) !important;
    color: white !important;
    text-decoration: none !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 0.5rem 1rem !important;
    font-weight: 500 !important;
    transition: all 0.3s ease !important;
    box-shadow: 0 2px 4px rgba(0,0,0,0.3) !important;
    display: inline-block !important;
    width: 100% !important;
    text-align: center !important;
}

/* File uploader */
div.stFileUploader {
    background: #2d2d2d !important;
    border: 2px dashed #555 !important;
    border-radius: 8px !important;
    color: white !important;
}

div.stFileUploader label {
    color: white !important;
}

/* Radio buttons */
div.stRadio > div {
    background: #2d2d2d !important;
    border-radius: 8px !important;
    padding: 1rem !important;
    border: 1px solid #444 !important;
}

div.stRadio label {
    color: white !important;
}

/* Text inputs */
div.stTextInput > div > div > input {
    background: #2d2d2d !important;
    border: 1px solid #444 !important;
    border-radius: 8px !important;
    color: white !important;
}

div.stTextInput label {
    color: white !important;
}

/* Chat messages */
div[data-testid="chat-message-user"] {
    background: #1a365d !important;
    border-radius: 8px !important;
    padding: 1rem !important;
    margin: 0.5rem 0 !important;
    border-left: 4px solid #3182ce !important;
}

div[data-testid="chat-message-assistant"] {
    background: #2d1b69 !important;
    border-radius: 8px !important;
    padding: 1rem !important;
    margin: 0.5rem 0 !important;
    border-left: 4px solid #805ad5 !important;
}

/* Chat input */
div.stChatInput {
    background: #2d2d2d !important;
    border-radius: 8px !important;
}

div.stChatInput input {
    background: #2d2d2d !important;
    border: 1px solid #444 !important;
    color: white !important;
}

/* Metrics */
div[data-testid="metric-container"] {
    background: #2d2d2d !important;
    border: 1px solid #444 !important;
    padding: 1rem !important;
    border-radius: 8px !important;
    color: white !important;
}

/* Status containers */
div[data-testid="stStatus"] {
    background: #2d2d2d !important;
    border: 1px solid #444 !important;
    border-radius: 8px !important;
}

/* Tabs */
div[data-testid="stTabs"] {
    background: #2d2d2d !important;
    border-radius: 8px !important;
}

/* Remove any white backgrounds from containers */
div[data-testid="stVerticalBlock"],
div[data-testid="stHorizontalBlock"],
div[data-testid="column"],
div.row-widget {
    background: transparent !important;
}

/* Sidebar dark theme */
.css-1d391kg {
    background: #2d2d2d !important;
}

/* Success/error/warning/info boxes */
div.stSuccess {
    background: #1b4332 !important;
    border: 1px solid #40916c !important;
    color: #d8f3dc !important;
}

div.stError {
    background: #660708 !important;
    border: 1px solid #dc2626 !important;
    color: #fecaca !important;
}

div.stWarning {
    background: #451a03 !important;
    border: 1px solid #d97706 !important;
    color: #fed7aa !important;
}

div.stInfo {
    background: #1e3a8a !important;
    border: 1px solid #3b82f6 !important;
    color: #dbeafe !important;
}

/* Dividers */
hr {
    margin: 2rem 0 !important;
    border: none !important;
    height: 2px !important;
    background: linear-gradient(90deg, #667eea 0%, #764ba2 100%) !important;
    border-radius: 1px !important;
}

/* Hide streamlit branding */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Dark welcome section */
.welcome-section {
    text-align: center;
    padding: 3rem;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    border-radius: 12px;
    color: white;
    margin: 2rem 0;
}

.welcome-feature-box {
    background: rgba(255,255,255,0.1);
    padding: 1.5rem;
    border-radius: 8px;
    margin: 1rem auto;
    max-width: 600px;
}

/* Dark footer */
.dark-footer {
    text-align: center;
    padding: 2rem;
    color: #999;
    background: #2d2d2d;
    border-radius: 8px;
    margin-top: 2rem;
    border: 1px solid #444;
}
</style>
""", unsafe_allow_html=True)

# --- Helper to clear relevant state for new processing ---
def reset_generation_output_state():
    st.session_state.generated_html = ""
    st.session_state.process_log_entries = []
    st.session_state.display_html = False
    st.session_state.website_plan = ""
    st.session_state.chat_messages = []
    st.session_state.temp_server_url = None
    cleanup_temp_server()  # Clean up any running temp server


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
                    # Extract and store the plan content for use in chat
                    plan_text = message[len(PLAN_PREFIX):-len(PLAN_SUFFIX)]
                    st.session_state.website_plan = plan_text
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
    # Normal layout
    st.subheader("🌐 Your Website")
    
    # Action buttons in columns (removed fullscreen button)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Improved new tab functionality
        if not st.session_state.temp_server_url:
            if st.button("🌐 New Tab", help="Open website in new browser tab", use_container_width=True):
                try:
                    # Start temporary server and get URL
                    url = serve_html_temporarily(st.session_state.generated_html)
                    st.session_state.temp_server_url = url
                    st.success("✅ Server started!")
                    st.rerun()
                except Exception as e:
                    st.error(f"❌ Failed to create local server: {str(e)}")
        else:
            # Show link button when server is ready
            st.link_button("🚀 Open Website", st.session_state.temp_server_url, use_container_width=True)
    
    with col2:
        st.download_button(
            label="📥 Download",
            data=st.session_state.generated_html,
            file_name="website.html",
            mime="text/html",
            help="Download the website as an HTML file",
            use_container_width=True
        )
    
    with col3:
        if st.session_state.temp_server_url:
            # Better URL display with copy functionality
            st.text_input("🔗 URL:", value=st.session_state.temp_server_url, key="url_display", help="Copy this URL to share")
        else:
            st.empty()  # Placeholder when no URL is available
    
    st.divider()
    
    # Main content layout
    col_main, col_info = st.columns([3, 1])
    
    with col_main:
        # Website preview
        st.components.v1.html(st.session_state.generated_html, height=600, scrolling=True)
    
    with col_info:
        # Enhanced website stats
        st.markdown("**📊 Website Statistics**")
        
        html_size_kb = len(st.session_state.generated_html) / 1024
        word_count = len(st.session_state.generated_html.split())
        changes_count = len([m for m in st.session_state.chat_messages if m['role'] == 'user'])
        
        # Create a nice container for stats
        with st.container():
            st.metric("💾 Size", f"{html_size_kb:.1f} KB")
            st.metric("🔢 Elements", f"{word_count:,}")
            mode_display = st.session_state.selected_mode.replace("LLM (Direct Website)", "Direct").replace("LLM (JSON + Template)", "LLM+Template").replace("Rule-based (JSON + Template)", "Rule-based")
            st.metric("⚙️ Mode", mode_display)
            
            if changes_count > 0:
                st.metric("✨ Changes", changes_count)
            
            # Server status
            if st.session_state.temp_server_url:
                st.success("🟢 Live Server Active")
            else:
                st.info("⚪ Server Inactive")
    
    st.divider()
    
    # --- SIMPLIFIED SINGLE CHAT INTERFACE ---
    st.subheader("💬 Customize Your Website")
    st.markdown("Describe what changes you'd like to make to your website:")
    
    # Enhanced quick actions
    st.markdown("**🚀 Quick Actions:**")
    
    col1, col2, col3, col4 = st.columns(4)
    
    quick_action_triggered = False
    quick_action_text = ""
    
    with col1:
        if st.button("🎨 Modern Colors", use_container_width=True, key="quick_colors", help="Apply a professional color scheme"):
            quick_action_text = "Change the color scheme to a modern professional palette with blues, grays, and white. Use gradients and ensure good contrast for readability."
            quick_action_triggered = True
    
    with col2:
        if st.button("📱 Mobile Ready", use_container_width=True, key="quick_mobile", help="Make mobile responsive"):
            quick_action_text = "Improve mobile responsiveness by making the layout stack vertically on small screens, adjusting font sizes, and ensuring touch-friendly buttons."
            quick_action_triggered = True
    
    with col3:
        if st.button("✨ Add Effects", use_container_width=True, key="quick_effects", help="Add animations and interactions"):
            quick_action_text = "Add smooth animations, hover effects on buttons and links, animated progress bars for skills, and subtle transitions throughout the site."
            quick_action_triggered = True
    
    with col4:
        if st.button("🔤 Better Fonts", use_container_width=True, key="quick_fonts", help="Improve typography"):
            quick_action_text = "Improve typography by using modern Google Fonts like Inter or Roboto, creating better text hierarchy, and adding proper spacing between elements."
            quick_action_triggered = True
    
    st.divider()
    
    # Simple chat history using default Streamlit chat elements
    if st.session_state.chat_messages:
        st.markdown("**💭 Chat History:**")
        
        for message in st.session_state.chat_messages:
            if message["role"] == "user":
                with st.chat_message("user"):
                    st.write(message["content"])
            else:
                with st.chat_message("assistant"):
                    st.write(message["content"])
        
        # Clear chat button
        if st.button("🗑️ Clear Chat", type="secondary"):
            st.session_state.chat_messages = []
            st.rerun()
    
    # Chat input using default Streamlit chat_input
    user_input = None
    if quick_action_triggered:
        user_input = quick_action_text
    else:
        user_input = st.chat_input("Describe what you'd like to change...")
    
    if user_input:
        # Validate input
        if len(user_input.strip()) < 3:
            st.warning("Please provide a more detailed description.")
            st.stop()
        
        # Add user message to chat history
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
        
        # Show user message
        with st.chat_message("user"):
            st.write(user_input)
        
        # Process the change request with simple status
        with st.status("Processing your request...", expanded=True) as status:
            
            def status_callback(message: str):
                status.write(message)
            
            try:
                # Apply the user's requested changes
                modified_html = apply_user_changes_llm(
                    current_html=st.session_state.generated_html,
                    user_request=user_input,
                    resume_text=st.session_state.raw_text or "",
                    website_plan=st.session_state.website_plan,
                    status_callback=status_callback
                )
                
                # Check if successful
                if modified_html and len(modified_html) > 100:
                    st.session_state.generated_html = modified_html
                    assistant_response = "✅ Changes applied successfully! Check the preview above."
                    status.update(label="✅ Complete!", state="complete")
                else:
                    assistant_response = "⚠️ Partial success. Please try rephrasing your request."
                    status.update(label="⚠️ Partial", state="error")
                
            except Exception as e:
                assistant_response = f"❌ Error: {str(e)}. Please try a different request."
                status.update(label="❌ Error", state="error")
            
            # Add assistant response
            st.session_state.chat_messages.append({"role": "assistant", "content": assistant_response})
            
            # Show assistant response
            with st.chat_message("assistant"):
                st.write(assistant_response)
        
        # Rerun to refresh
        st.rerun()

elif not st.session_state.processed_pdf_name:
    # Dark themed welcome message
    st.markdown("""
    <div class="welcome-section">
        <h2 style="margin-bottom: 1rem;">🚀 Welcome to Résumé-to-Site!</h2>
        <p style="font-size: 1.2rem; margin-bottom: 2rem;">Transform your PDF résumé into a stunning personal website in minutes</p>
        <div class="welcome-feature-box">
            <h3 style="margin-bottom: 1rem;">✨ What you'll get:</h3>
            <ul style="text-align: left; list-style: none; padding: 0;">
                <li style="margin: 0.5rem 0;">🎨 Beautiful, professional design</li>
                <li style="margin: 0.5rem 0;">📱 Mobile-responsive layout</li>
                <li style="margin: 0.5rem 0;">💬 AI-powered customization chat</li>
                <li style="margin: 0.5rem 0;">⚡ Instant preview and download</li>
                <li style="margin: 0.5rem 0;">🌐 Shareable live URL</li>
            </ul>
        </div>
        <p style="font-size: 1rem; opacity: 0.9;">👆 Upload your PDF résumé above to get started!</p>
    </div>
    """, unsafe_allow_html=True)

# Cleanup temp server on app exit
import atexit
atexit.register(cleanup_temp_server)

st.markdown("---")
st.markdown("""
<div class="dark-footer">
    <p style="margin: 0; font-size: 0.9rem;">
        <strong>📄 → 🌐 Résumé-to-Site</strong> | Powered by AI | 
        <a href="#" style="color: #667eea; text-decoration: none;">Documentation</a> | 
        <a href="#" style="color: #667eea; text-decoration: none;">Support</a>
    </p>
    <p style="margin: 0.5rem 0 0 0; font-size: 0.8rem; opacity: 0.7;">
        © 2024 | Transform your career, one website at a time ✨
    </p>
</div>
""", unsafe_allow_html=True)
