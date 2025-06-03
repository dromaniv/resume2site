import streamlit as st

# MUST be the first Streamlit command
st.set_page_config(layout="wide", page_title="Résumé-to-Site")

import tempfile
from pathlib import Path
from datetime import datetime
import urllib.parse  # Added for data URI encoding
import webbrowser
import time
import atexit

from extractor import pdf_to_text
from parser_llm import parse_resume_llm
from generator_llm import generate_html_llm, apply_user_changes_llm, summarize_html_changes_llm
from generator_rule import json_to_html
from parser_rule import parse_resume_rule
from temp_server import serve_html_temporarily, cleanup_temp_server
from llm_client import get_llm_client

# Register cleanup function to run when Streamlit exits
atexit.register(cleanup_temp_server)

def get_current_model() -> str:
    """Get the currently selected model from session state"""
    provider = st.session_state.selected_provider
    model = st.session_state.selected_model
    
    # Format the model for the LLM client
    if provider == "OpenAI":
        return model
    elif provider == "Ollama":
        return model
    else:
        return model  # Fallback to direct model name

# Add session-based cleanup for Streamlit
@st.cache_resource
def get_session_cleanup():
    """Register cleanup for current Streamlit session"""
    import weakref
    
    def cleanup():
        cleanup_temp_server()
    
    # Create a weakref callback that will be called when the session ends
    class SessionCleanup:
        def __init__(self):
            self.cleanup_func = cleanup
            
        def __del__(self):
            try:
                self.cleanup_func()
            except:
                pass  # Ignore cleanup errors during session end
    
    return SessionCleanup()

# Initialize cleanup for this session
session_cleanup = get_session_cleanup()

# Add cleanup on script rerun
if "server_cleanup_registered" not in st.session_state:
    st.session_state.server_cleanup_registered = True
    # This will be cleaned up when session state is cleared

# Initialize session state variables
if "generated_html" not in st.session_state:
    st.session_state.generated_html = ""
if "process_log_entries" not in st.session_state:
    st.session_state.process_log_entries = []
if "display_html" not in st.session_state:
    st.session_state.display_html = False
if "selected_mode" not in st.session_state:
    st.session_state.selected_mode = "AI Direct Build (Custom design & layout)"
if "selected_provider" not in st.session_state:
    st.session_state.selected_provider = "OpenAI"
if "selected_model" not in st.session_state:
    st.session_state.selected_model = "gpt-4o-mini"
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
# Pending quick action text to be processed in next render cycle
if "quick_action_pending" not in st.session_state:
    st.session_state.quick_action_pending = None
# Change summary system variables
if "pending_change_summary" not in st.session_state:
    st.session_state.pending_change_summary = None
if "original_html_backup" not in st.session_state:
    st.session_state.original_html_backup = None
if "change_user_request" not in st.session_state:
    st.session_state.change_user_request = None

# Simple title with default Streamlit styling
st.title("📄 → 🌐 Résumé-to-Site")
st.markdown("Transform your PDF résumé into a stunning personal website")

# --- LLM PROVIDER AND MODEL SELECTION ---
st.markdown("### 🤖 AI Model Configuration")

# Available models for each provider
MODEL_OPTIONS = {
    "OpenAI": [
        "gpt-4o",
        "gpt-4o-mini", 
        "gpt-4-turbo",
        "gpt-3.5-turbo"
    ],
    "Ollama": [
        "deepseek-coder-v2",
        "llama3.1:8b",
        "llama3.1:70b",
        "codellama:7b",
        "codellama:13b",
        "qwen2.5-coder:7b",
        "qwen2.5-coder:14b",
        "mistral:7b",
        "phi3:3.8b"
    ]
}

col_provider, col_model = st.columns([1, 2])

with col_provider:
    provider = st.selectbox(
        "Provider",
        options=list(MODEL_OPTIONS.keys()),
        index=list(MODEL_OPTIONS.keys()).index(st.session_state.selected_provider),
        key="provider_select",
        help="Choose between OpenAI API or local Ollama models"
    )

with col_model:
    # Update available models when provider changes
    if provider != st.session_state.selected_provider:
        st.session_state.selected_provider = provider
        # Reset to first model of new provider
        st.session_state.selected_model = MODEL_OPTIONS[provider][0]
    
    model = st.selectbox(
        "Model",
        options=MODEL_OPTIONS[provider],
        index=MODEL_OPTIONS[provider].index(st.session_state.selected_model) if st.session_state.selected_model in MODEL_OPTIONS[provider] else 0,
        key="model_select",
        help=f"Select the {'OpenAI' if provider == 'OpenAI' else 'Ollama'} model to use for generation"
    )

# Update session state
st.session_state.selected_provider = provider
st.session_state.selected_model = model

# Show model info
if provider == "OpenAI":
    if model == "gpt-4o":
        st.info("🚀 **GPT-4o**: Most capable, best for complex websites with advanced features")
    elif model == "gpt-4o-mini":
        st.info("⚡ **GPT-4o Mini**: Fast and cost-effective, great for most resume websites")
    elif model == "gpt-4-turbo":
        st.info("🎯 **GPT-4 Turbo**: Excellent balance of capability and speed")
    else:
        st.info("💡 **GPT-3.5 Turbo**: Budget-friendly option for simple websites")
else:
    if "deepseek" in model.lower():
        st.info("🔥 **DeepSeek Coder**: Specialized coding model, excellent for web development")
    elif "llama" in model.lower():
        st.info("🦙 **Llama**: Open-source general purpose model")
    elif "codellama" in model.lower():
        st.info("💻 **Code Llama**: Meta's specialized coding model")
    elif "qwen" in model.lower():
        st.info("🌟 **Qwen Coder**: Alibaba's powerful coding model")
    else:
        st.info(f"🤖 **{model.title()}**: {provider} local model")

st.divider()

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
    # Clear change summary state
    st.session_state.pending_change_summary = None
    st.session_state.original_html_backup = None
    st.session_state.change_user_request = None
    cleanup_temp_server()  # Clean up any running temp server


# --- Generation Logic ---
def trigger_website_generation():
    if not st.session_state.raw_text:
        # This should ideally not be hit if calling logic is correct
        return

    reset_generation_output_state()  # Clear previous results before starting

    PLAN_PREFIX = "📝 **Website Plan:**\\\\n```\\\\n"
    PLAN_SUFFIX = "\\\\n```"

    if st.session_state.selected_mode == "AI Direct Build (Custom design & layout)":
        st.subheader("🎨 Custom AI Website Generation")
        with st.status(
            "🤖 Creating custom website with AI...", expanded=True
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
                    status_ui.update(label="✏️ Design plan created. Building your website...")
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
                    st.session_state.raw_text, 
                    status_callback=status_update_callback,
                    model=get_current_model()
                )
                st.session_state.generated_html = html_output
                st.session_state.display_html = True
                
                # Auto-start server when website is generated
                if (
                    "Error" not in html_output
                    and "Input Error" not in html_output
                    and "Processing Error" not in html_output
                ):
                    try:
                        url = serve_html_temporarily(html_output)
                        st.session_state.temp_server_url = url
                    except Exception as e:
                        st.warning(f"Could not start preview server: {e}")
                    
                    status_ui.update(
                        label="✅ Custom website created successfully!", state="complete"
                    )
                else:
                    status_ui.update(
                        label="⚠️ Website creation completed with warnings.",
                        state="error",
                    )
            except Exception as e:
                st.error(f"An unexpected error occurred during website creation: {e}")
                status_ui.update(
                    label="💥 Unexpected error during creation.", state="error"
                )
                st.session_state.process_log_entries.append(
                    f'{datetime.now().strftime("%H:%M:%S")} - Error: {e}'
                )

    elif st.session_state.selected_mode == "AI Structured (Parsed data + Template)":
        st.subheader("📊 Structured Data + Professional Template")
        
        with st.spinner("🔍 Analyzing resume structure with AI..."):
            parsed_json = parse_resume_llm(st.session_state.raw_text, model=get_current_model())
        st.success("✅ Resume data extracted and structured.")
        st.json(parsed_json)
        with st.spinner("🏗️ Building website from structured data..."):
            html_output = json_to_html(parsed_json, inline=True)
        st.session_state.generated_html = html_output
        st.session_state.display_html = True
        
        # Auto-start server when website is generated
        try:
            url = serve_html_temporarily(html_output)
            st.session_state.temp_server_url = url
        except Exception as e:
            st.warning(f"Could not start preview server: {e}")
            
        st.success("✅ Professional website built from structured data.")

    elif st.session_state.selected_mode == "Rule-based Parser (Pattern matching + Template)":
        st.subheader("⚙️ Pattern-based Parsing + Clean Template")
        with st.spinner("📋 Extracting resume sections using pattern matching..."):
            parsed_json = parse_resume_rule(st.session_state.raw_text)
        st.success("✅ Resume sections identified and extracted.")
        st.json(parsed_json)
        with st.spinner("🎯 Assembling clean, structured website..."):
            html_output = json_to_html(parsed_json, inline=True)
        st.session_state.generated_html = html_output
        st.session_state.display_html = True
        
        # Auto-start server when website is generated
        try:
            url = serve_html_temporarily(html_output)
            st.session_state.temp_server_url = url
        except Exception as e:
            st.warning(f"Could not start preview server: {e}")
            
        st.success("✅ Website assembled using pattern-based extraction.")

def get_available_sections():
    """Extract available sections dynamically from the website plan and HTML"""
    sections = []
    
    # Try to extract from website plan first (more reliable)
    if hasattr(st.session_state, 'website_plan') and st.session_state.website_plan:
        plan_text = st.session_state.website_plan
        
        # Try to parse YAML-like structure first
        import re
        
        # Look for YAML section structure: "- name: SectionName"
        yaml_sections = re.findall(r'- name:\s*([^\n]+)', plan_text, re.IGNORECASE)
        if yaml_sections:
            for section_name in yaml_sections:
                section_clean = section_name.strip().lower()
                if section_clean not in sections:
                    sections.append(section_clean)
        
        # If no YAML structure found, look for common section patterns
        if not sections:
            plan_text_lower = plan_text.lower()
            section_patterns = {
                'home': ['home', 'landing', 'hero', 'intro'],
                'about': ['about', 'summary', 'profile', 'bio'],
                'experience': ['experience', 'work', 'employment', 'career', 'jobs'],
                'education': ['education', 'academic', 'university', 'degree', 'school'],
                'skills': ['skills', 'technical', 'competencies', 'abilities'],
                'projects': ['projects', 'portfolio', 'work samples', 'demos'],
                'contact': ['contact', 'reach', 'get in touch', 'email', 'phone']
            }
            
            for section_key, keywords in section_patterns.items():
                if any(keyword in plan_text_lower for keyword in keywords):
                    sections.append(section_key)
    
    # Fallback: try to extract from HTML if available
    if not sections and hasattr(st.session_state, 'generated_html') and st.session_state.generated_html:
        import re
        html_content = st.session_state.generated_html.lower()
        
        # Look for section IDs in the HTML
        section_id_matches = re.findall(r'id=["\']([^"\']*)["\']', html_content)
        common_sections = ['home', 'about', 'experience', 'education', 'skills', 'projects', 'contact']
        
        for section_id in section_id_matches:
            for common_section in common_sections:
                if common_section in section_id:
                    if common_section not in sections:
                        sections.append(common_section)
        
        # Also look for h2/h3 section headings
        heading_matches = re.findall(r'<h[23][^>]*>([^<]+)</h[23]>', html_content)
        for heading in heading_matches:
            heading_clean = heading.strip().lower()
            for common_section in common_sections:
                if common_section in heading_clean and common_section not in sections:
                    sections.append(common_section)
    
    # If still no sections found, provide defaults
    if not sections:
        sections = ['about', 'experience', 'education', 'skills', 'projects', 'contact']
    
    # Create section options with descriptions
    section_descriptions = {
        'home': 'Enhance the landing/hero section with better presentation',
        'about': 'Expand professional summary and personal introduction',
        'experience': 'Add more details about roles and responsibilities', 
        'education': 'Expand on academic achievements and coursework',
        'skills': 'Elaborate on technical and soft skills with context',
        'projects': 'Add more depth to project descriptions and outcomes',
        'contact': 'Improve contact section presentation and accessibility'
    }
    
    # Format sections for display
    formatted_sections = []
    for section in sections:
        section_title = section.replace('_', ' ').title()
        description = section_descriptions.get(section, f'Enhance the {section} section with additional details')
        formatted_sections.append(f"{section_title} - {description}")
    
    return formatted_sections

# --- UI Elements & Main Control Logic ---
def on_mode_selection_change_callback():
    reset_generation_output_state()  # Clear previous output
    # If a PDF has been processed, set flag to regenerate with the new mode
    if st.session_state.raw_text and st.session_state.processed_pdf_name:
        st.session_state.mode_changed_flag = True
    # DO NOT call trigger_website_generation() here


st.radio(
    "Select how to build your website:",
    options=[
        "AI Direct Build (Custom design & layout)",
        "AI Structured (Parsed data + Template)",
        "Rule-based Parser (Pattern matching + Template)",
    ],
    key="selected_mode",
    on_change=on_mode_selection_change_callback,
    index=[
        "AI Direct Build (Custom design & layout)",
        "AI Structured (Parsed data + Template)",
        "Rule-based Parser (Pattern matching + Template)",
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
    st.subheader("🎯 Your Professional Website")
    
    # Action buttons in columns (removed fullscreen button)
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Direct link button since server starts automatically
        if st.session_state.temp_server_url:
            st.link_button("🌐 Open New Tab", st.session_state.temp_server_url, use_container_width=True)
        else:
            st.button("🌐 New Tab", disabled=True, help="Server starting...", use_container_width=True)
    
    with col2:
        if st.session_state.temp_server_url:
            # URL display styled to match buttons
            st.markdown(f"""
            <div style="
                background: linear-gradient(90deg, #2d2d2d 0%, #444 100%);
                color: white;
                border: 1px solid #555;
                border-radius: 8px;
                padding: 0.5rem 1rem;
                font-family: monospace;
                font-size: 0.875rem;
                text-align: center;
                word-break: break-all;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
                height: 38px;
                display: flex;
                align-items: center;
                justify-content: center;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
                transition: all 0.3s ease;
                cursor: pointer;
            " title="{st.session_state.temp_server_url}" onclick="navigator.clipboard.writeText('{st.session_state.temp_server_url}')">
                📋 {st.session_state.temp_server_url}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.empty()  # Placeholder when no URL is available

    with col3:
        st.download_button(
            label="📥 Download",
            data=st.session_state.generated_html,
            file_name="website.html",
            mime="text/html",
            help="Download the website as an HTML file",
            use_container_width=True
        )
    
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
            mode_display = st.session_state.selected_mode.replace("AI Direct Build (Custom design & layout)", "AI Custom").replace("AI Structured (Parsed data + Template)", "AI+Template").replace("Rule-based Parser (Pattern matching + Template)", "Rule-based")
            st.metric("⚙️ Mode", mode_display)
            
            if changes_count > 0:
                st.metric("✨ Changes", changes_count)
    
    st.divider()
    
    # --- WEBSITE REFINEMENT INTERFACE ---
    st.subheader("✨ Refine & Perfect Your Website")
    st.markdown("Tell the AI how to improve your website's design, content, or functionality:")
    
    # Create a clean chat interface
    with st.container():        # Enhanced quick actions at the top of chat panel
        with st.expander("⚡ One-Click Enhancements", expanded=False):
            # First row of quick actions
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                if st.button("🎨 Professional Theme", use_container_width=True, key="quick_colors", help="Apply a modern professional color scheme"):
                    st.session_state.quick_action_pending = "Change the color scheme to a modern professional palette with blues, grays, and white. Use gradients and ensure good contrast for readability."
                    st.rerun()
            
            with col2:
                if st.button("📱 Mobile Optimize", use_container_width=True, key="quick_mobile", help="Optimize for mobile devices"):
                    st.session_state.quick_action_pending = "Improve mobile responsiveness by making the layout stack vertically on small screens, adjusting font sizes, and ensuring touch-friendly buttons."
                    st.rerun()
            
            with col3:
                if st.button("✨ Add Animations", use_container_width=True, key="quick_effects", help="Add smooth animations and interactions"):
                    st.session_state.quick_action_pending = "Add smooth animations, hover effects on buttons and links, animated progress bars for skills, and subtle transitions throughout the site."
                    st.rerun()
            
            with col4:
                if st.button("🔤 Typography Upgrade", use_container_width=True, key="quick_fonts", help="Enhance fonts and text styling"):
                    st.session_state.quick_action_pending = "Improve typography by using modern Google Fonts like Inter or Roboto, creating better text hierarchy, and adding proper spacing between elements."
                    st.rerun()
            
            # Second row of quick actions
            st.markdown("<br>", unsafe_allow_html=True)
            col5, col6, col7, col8 = st.columns(4)
            
            with col5:
                if st.button("🚀 Content Enhancement", use_container_width=True, key="quick_content", help="Intelligently expand project descriptions and add professional details"):
                    st.session_state.quick_action_pending = "**IMPORTANT: This feature adds AI-generated content to showcase website capabilities - content may not be factually accurate and should be reviewed.** \n\nEnhance the existing content by expanding project descriptions with realistic technical details, adding implementation specifics, outcome metrics, and professional context. Focus on expanding the Projects and Experience sections with plausible industry-standard details while maintaining professional tone. Add specific technologies, methodologies, and quantifiable results where appropriate."
                    st.rerun()            
            
            with col6:
                if st.button("🔎 Expand Chosen Section", use_container_width=True, key="quick_expand", help="Choose and expand a specific section using only CV information"):
                    # Set flag to show section selector
                    st.session_state.show_section_selector = True
                    st.rerun()
            
            with col7:
                if st.button("🎯 SEO Enhancement", use_container_width=True, key="quick_seo", help="Add SEO meta tags and improve discoverability"):
                    st.session_state.quick_action_pending = "Improve SEO by adding proper meta descriptions, Open Graph tags, structured data markup, and optimizing heading hierarchy for better search engine visibility."
                    st.rerun()
            
            with col8:
                if st.button("🎭 Website Personality", use_container_width=True, key="quick_personality", help="Apply creative themes and personality to your website"):
                    # Set flag to show personality selector
                    st.session_state.show_personality_selector = True
                    st.rerun()
        
        # Section selector modal (appears when expand chosen section is clicked)
        if getattr(st.session_state, 'show_section_selector', False):
            st.markdown("---")
            st.markdown("**🔎 Choose Section to Expand**")
            st.markdown("*This will expand the selected section using only information from your original CV*")
            
            # Get available sections dynamically
            section_options = get_available_sections()
            
            if not section_options:
                st.warning("No sections detected in your website. Please generate a website first.")
                st.session_state.show_section_selector = False
                st.rerun()
            
            col_select, col_apply, col_cancel = st.columns([3, 1, 1])
            
            with col_select:
                selected_section = st.selectbox(
                    "Select section to expand:",
                    section_options,
                    key="section_to_expand"
                )
            
            with col_apply:
                if st.button("✅ Apply", key="apply_section_expand", type="primary"):
                    section_name = selected_section.split(" - ")[0]
                    description = selected_section.split(" - ")[1]
                    
                    st.session_state.quick_action_pending = f"Focus ONLY on the {section_name} section. {description}. Use ONLY information that was present in the original CV/resume text. Do not add any fictional or assumed information. Expand and enhance the presentation of existing details, improve formatting, and make the content more readable and professional. If the section has limited information in the original CV, work with what's available and improve its presentation rather than adding new content."                  
                    st.session_state.show_section_selector = False
                    st.rerun()
            
            with col_cancel:
                if st.button("❌ Cancel", key="cancel_section_expand"):
                    st.session_state.show_section_selector = False
                    st.rerun()
            
            st.markdown("---")
        
        # Personality selector modal (appears when website personality is clicked)
        if getattr(st.session_state, 'show_personality_selector', False):
            st.markdown("---")
            st.markdown("**🎭 Choose Website Personality**")
            st.markdown("*Transform your website with a distinctive design theme and personality*")
            
            # Define personality options
            personality_options = [
                "Creative & Bold - Transform the website with vibrant colors, creative layouts, unique typography, and artistic elements that showcase creativity and innovation.",
                "Corporate & Executive - Apply a sophisticated corporate design with premium colors, executive-level typography, professional spacing, and business-focused elements.",
                "Tech & Modern - Implement a sleek tech aesthetic with dark themes, neon accents, code-inspired fonts, and futuristic design elements.",
                "Minimalist & Clean - Create an ultra-clean minimal design with lots of white space, simple typography, subtle colors, and focus on content clarity.",
                "Warm & Approachable - Design with warm colors, friendly typography, rounded elements, and inviting design that feels personal and accessible."
            ]
            
            col_select, col_apply, col_cancel = st.columns([3, 1, 1])
            
            with col_select:
                selected_personality = st.selectbox(
                    "Select personality style:",
                    personality_options,
                    key="personality_to_apply"
                )
            
            with col_apply:
                if st.button("✅ Apply", key="apply_personality", type="primary"):
                    personality_name = selected_personality.split(" - ")[0]
                    description = selected_personality.split(" - ")[1]
                    
                    st.session_state.quick_action_pending = f"{personality_name}: {description}"
                    st.session_state.show_personality_selector = False
                    st.rerun()
            
            with col_cancel:
                if st.button("❌ Cancel", key="cancel_personality"):
                    st.session_state.show_personality_selector = False
                    st.rerun()
            
            st.markdown("---")
            
          # Chat history
        if st.session_state.chat_messages:
            st.markdown("**🔄 Refinement History:**")
            
            for message in st.session_state.chat_messages:
                if message["role"] == "user":
                    with st.chat_message("user"):
                        st.write(message["content"])
                else:
                    with st.chat_message("assistant"):
                        st.write(message["content"])
        else:
            st.markdown("**🎯 Ready to improve your website?**")
            st.markdown("Use the input below or select a quick enhancement option above!")
    
    # Change Summary Review Section
    if st.session_state.pending_change_summary:
        st.markdown("---")
        st.markdown("### 📋 Change Summary")
        st.markdown(f"**Your request:** {st.session_state.change_user_request}")
        
        # Display the LLM-generated change summary
        with st.container():
            st.markdown("**Changes made:**")
            st.markdown(st.session_state.pending_change_summary)
          # Accept/Discard buttons
        col_accept, col_discard = st.columns(2)
        
        with col_accept:
            if st.button("✅ Accept Changes", type="primary", use_container_width=True, key="accept_changes"):
                # Add success message to chat first
                st.session_state.chat_messages.append({
                    "role": "assistant", 
                    "content": "✅ Changes accepted! Your website has been updated successfully."
                })
                
                # Clear change summary data (finalize the changes)
                st.session_state.pending_change_summary = None
                st.session_state.original_html_backup = None
                st.session_state.change_user_request = None
                
                st.rerun()
        
        with col_discard:
            if st.button("❌ Discard Changes", type="secondary", use_container_width=True, key="discard_changes"):
                # Revert to original HTML
                if st.session_state.original_html_backup:
                    st.session_state.generated_html = st.session_state.original_html_backup
                    
                    # Update server with original HTML
                    try:
                        url = serve_html_temporarily(st.session_state.original_html_backup)
                        st.session_state.temp_server_url = url
                    except Exception as e:
                        st.warning(f"Could not update preview server: {e}")
                
                # Clear change summary data
                st.session_state.pending_change_summary = None
                st.session_state.original_html_backup = None
                st.session_state.change_user_request = None
                
                # Add revert message to chat
                st.session_state.chat_messages.append({
                    "role": "assistant", 
                    "content": "🔄 Changes discarded. Your website has been reverted to the previous version."
                })
                st.rerun()
        
        st.markdown("---")
    
    # Chat input area with integrated clear button
    col_input, col_clear = st.columns([5, 1])
    
    with col_input:
        # Check for pending quick action
        user_input = None
        if hasattr(st.session_state, 'quick_action_pending') and st.session_state.quick_action_pending:
            user_input = st.session_state.quick_action_pending
            st.session_state.quick_action_pending = None  # Clear it
        else:
            user_input = st.chat_input("Tell me what you'd like to improve or change...")
    
    with col_clear:
        # Clear chat button integrated with input area
        if st.button("🗑️", help="Clear refinement history", key="clear_chat_btn", type="secondary", use_container_width=True):
            st.session_state.chat_messages = []
            st.rerun()
    
    if user_input:
        # Validate input
        if len(user_input.strip()) < 3:
            st.warning("Please provide a more detailed description of what you'd like to improve.")
            st.stop()
        
        # Add user message to chat history
        st.session_state.chat_messages.append({"role": "user", "content": user_input})
          # Show user message
        with st.chat_message("user"):
            st.write(user_input)
        
        # Process the change request with simple status
        with st.status("🔄 Applying your improvements...", expanded=True) as status:
            
            def status_callback(message: str):
                status.write(message)
            
            success = False
            error_msg = None
            
            try:
                # Cache original HTML before applying changes
                original_html = st.session_state.generated_html
                
                # Apply the user's requested changes
                modified_html = apply_user_changes_llm(
                    current_html=st.session_state.generated_html,
                    user_request=user_input,
                    resume_text=st.session_state.raw_text or "",
                    website_plan=st.session_state.website_plan,
                    status_callback=status_callback,
                    model=get_current_model()
                )
                
                # Check if successful
                if modified_html and len(modified_html) > 100:
                    # Generate change summary using LLM
                    status_callback("📝 Generating change summary...")
                    change_summary = summarize_html_changes_llm(
                        old_html=original_html,
                        new_html=modified_html,
                        model=get_current_model()
                    )
                    
                    # Store change information for review
                    st.session_state.original_html_backup = original_html
                    st.session_state.pending_change_summary = change_summary
                    st.session_state.change_user_request = user_input
                    st.session_state.generated_html = modified_html
                      # Update server with new HTML content
                    try:
                        url = serve_html_temporarily(modified_html)
                        st.session_state.temp_server_url = url
                    except Exception as e:
                        st.warning(f"Could not update preview server: {e}")
                    
                    assistant_response = "✅ Changes applied! Please review the summary below and accept or discard the changes."
                    status.update(label="✅ Changes Ready for Review", state="complete")
                    success = True
                else:
                    assistant_response = "⚠️ Could not apply improvements properly. Please try rephrasing your request or be more specific."
                    status.update(label="⚠️ Failed", state="error")
                    success = False
                
            except Exception as e:
                error_msg = str(e)
                assistant_response = f"❌ Error applying improvements: {error_msg}. Please try a different approach."
                status.update(label="❌ Error", state="error")
                success = False
            
            # Only add assistant response immediately if there's no pending change summary
            # (For successful changes with summaries, response is added when user accepts/discards)
            if not st.session_state.pending_change_summary:
                # Add assistant response
                st.session_state.chat_messages.append({"role": "assistant", "content": assistant_response})
                
                # Show assistant response
                with st.chat_message("assistant"):
                    if success:
                        st.success(assistant_response)
                    else:
                        if error_msg:
                            st.error(assistant_response)
                        else:
                            st.warning(assistant_response)
        
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
                <li style="margin: 0.5rem 0;">🤖 AI-powered website refinement</li>
                <li style="margin: 0.5rem 0;">⚡ Instant preview and download</li>
                <li style="margin: 0.5rem 0;">🌐 Shareable live URL</li>
            </ul>
        </div>
        <p style="font-size: 1rem; opacity: 0.9;">👆 Upload your PDF résumé above to get started!</p>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")
st.markdown("""
<div class="dark-footer">
    <p style="margin: 0; font-size: 0.9rem;">
        <strong>📄 → 🌐 Résumé-to-Site</strong> | Powered by AI | 
        <a href="https://github.com/dromaniv/resume2site/blob/main/README.md" target="_blank" style="color: #667eea; text-decoration: none;">Documentation</a>
    </p>
    <p style="margin: 0.5rem 0 0 0; font-size: 0.8rem; opacity: 0.7;">
        © 2025 | Transform your career, one website at a time ✨
    </p>
</div>
""", unsafe_allow_html=True)
