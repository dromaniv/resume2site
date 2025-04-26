import streamlit as st, tempfile
from pathlib import Path
from extractor import pdf_to_text
from parser_llm import parse_resume_llm
from parser_rule import parse_resume_rule
from generator import json_to_html

st.set_page_config(page_title="Résumé-to-Site", layout="wide")
st.title("📄 → 🌐 Résumé-to-Site")

parser_mode = st.radio("Choose parser", ["LLM (DeepSeek)", "Rule-based"])
pdf_file = st.file_uploader("Upload PDF résumé", type="pdf")

if pdf_file:
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(pdf_file.read())
        pdf_path = Path(tmp.name)

    raw = pdf_to_text(pdf_path)
    data = parse_resume_llm(raw) if parser_mode.startswith("LLM") else parse_resume_rule(raw)

    st.subheader("Parsed JSON")
    st.json(data)

    # inline CSS for Streamlit iframe
    html_inline = json_to_html(data, inline=True)
    st.subheader("Preview")
    st.components.v1.html(html_inline, height=900, scrolling=True)

    # external CSS for offline use
    html_file = json_to_html(data, inline=False)
    st.download_button("Download index.html", html_file,
                       file_name="index.html", mime="text/html")