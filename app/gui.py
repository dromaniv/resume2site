import streamlit as st, tempfile
from pathlib import Path
from extractor import pdf_to_text
from parser_llm import parse_resume_llm
from generator_llm import generate_html_llm 
from parser_rule import parse_resume_rule
from generator import json_to_html

st.set_page_config(page_title="Résumé-to-Site", layout="wide")
st.title("📄 → 🌐 Résumé-to-Site")

# Updated radio button options
parser_mode = st.radio(
    "Choose generation mode",
    ["LLM (JSON + Template)", "Rule-based (JSON + Template)", "LLM (Direct HTML)"]
)
pdf_file = st.file_uploader("Upload PDF résumé", type="pdf")

if pdf_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_file.read())
        pdf_path = Path(tmp.name)

    with st.spinner("Extracting text from PDF..."):
        raw_text = pdf_to_text(pdf_path)
    st.success("✅ PDF text extracted successfully!")

    if parser_mode == "LLM (Direct HTML)":
        st.subheader("LLM-Generated HTML Website")
        # Define current_status_label here, in the same scope as update_status will be defined
        current_status_label = ["🚀 Starting Direct HTML Generation..."] # Use a list to make it mutable from inner scope

        with st.status(current_status_label[0], expanded=True) as status_container:
            def update_status(message):
                current_status_label[0] = message # Update the mutable list's element
                status_container.update(label=message)
            
            html_direct_llm = generate_html_llm(raw_text, status_callback=update_status)
            
            # Use the mutable list's element for the condition
            if "✅ HTML/CSS validation passed!" in current_status_label[0] or \
               ("❌ Failed to generate valid HTML" in current_status_label[0] and html_direct_llm):
                status_container.update(label="🎉 Website generation process complete!", state="complete", expanded=False)
            else:
                status_container.update(label="💔 Website generation failed.", state="error", expanded=True)

        if html_direct_llm:
            st.components.v1.html(html_direct_llm, height=900, scrolling=True)
            st.download_button(
                "Download LLM_generated_site.html",
                html_direct_llm,
                file_name="LLM_generated_site.html",
                mime="text/html"
            )
        # Error message is handled by the status update now

    else: # JSON-based modes (LLM or Rule-based)
        data = None
        if parser_mode.startswith("LLM"):
            with st.status("Processing with LLM (JSON + Template)...", expanded=True) as status_container:
                status_container.update(label="🤖 Calling LLM to parse resume into JSON...")
                data = parse_resume_llm(raw_text) # Assuming parse_resume_llm doesn't have callback yet
                status_container.update(label="✅ Resume parsed to JSON.", state="complete")
        else: # Rule-based
            with st.status("Processing with Rule-based parser...", expanded=True) as status_container:
                status_container.update(label="⚙️ Parsing resume using rules...")
                data = parse_resume_rule(raw_text)
                status_container.update(label="✅ Resume parsed to JSON.", state="complete")

        if data:
            st.subheader("Parsed JSON")
            st.json(data)

            with st.spinner("🎨 Rendering HTML from template..."):
                html_inline_template = json_to_html(data, inline=True)
            st.success("✅ HTML rendered from template!")

            st.subheader("Preview (Template-based)")
            st.components.v1.html(html_inline_template, height=900, scrolling=True)

            html_file_template = json_to_html(data, inline=False)
            st.download_button(
                "Download index_template.html",
                html_file_template,
                file_name="index_template.html",
                mime="text/html"
            )
        else:
            st.error("❌ Failed to parse resume data.")
else:
    st.info("👋 Upload a PDF résumé to get started!")

st.write("---")
st.markdown("<p style='text-align: center; color: grey;'>Résumé-to-Site by Your Name/Organization</p>", unsafe_allow_html=True)