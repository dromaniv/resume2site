"""
LLM-based HTML website generator (DeepSeek-Coder-v2 via Ollama).

• Caches responses in .cache/html/<sha256>.html so the model is
  queried only once per unique resume text.
• Includes basic HTML and CSS validation and a retry mechanism for fixes.
"""
from __future__ import annotations
import re
import textwrap
from pathlib import Path
from ollama import chat
from bs4 import BeautifulSoup
import html5lib # For HTML5 parsing
import cssutils
import logging
from typing import Callable # Add Callable

from utils import _sha

# Configure cssutils logging to be less verbose for common errors
cssutils.log.setLevel(logging.CRITICAL) # Only show critical errors from cssutils

# Model and cache configuration
_MODEL = "deepseek-coder-v2"

# Determine project root from this file's location
# app/generator_llm.py -> app.parent is app/ -> app.parent.parent is project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_HTML_CACHE_DIR = _PROJECT_ROOT / ".cache" / "html"  # Use absolute path

_HTML_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_MAX_FIX_ATTEMPTS = 2 # Maximum attempts to fix HTML/CSS issues

_SYSTEM_PROMPT_HTML = textwrap.dedent(f"""
You are an expert web designer and developer with a keen eye for modern aesthetics and user interaction.
Based on the provided résumé text, generate a COMPLETE, MODERN, BEAUTIFUL, and INTERACTIVE single HTML file for a personal portfolio website.

Key requirements for the generated HTML:
1.  **Structure**: Well-structured and semantically correct HTML5.
2.  **Content**: Accurately represent all relevant information from the résumé text, including:
    *   Name and Headline
    *   Contact Information (email, phone, GitHub, LinkedIn)
    *   Summary/About Me
    *   Work Experience (Job title, company, dates, responsibilities/achievements as bullet points)
    *   Education (Degree, school, dates)
    *   Skills (categorized if possible, e.g., languages, tools, soft skills)
    *   Projects (if any, with descriptions and links if available)
3.  **Styling (CSS)**:
    *   Embed all CSS directly within the HTML file, either in `<style>` tags in the `<head>` or as inline styles.
    *   The design should be visually appealing, modern, and professional. Use a good color palette, typography, and layout.
    *   Ensure the website is responsive and looks good on different screen sizes (desktop, tablet, mobile).
4.  **Interactivity (JavaScript)**:
    *   Embed all JavaScript directly within the HTML file in `<script>` tags, preferably at the end of the `<body>`.
    *   Incorporate subtle animations, smooth scrolling, interactive elements (e.g., hover effects, clickable project cards that expand, a simple contact form validation if you add a form).
    *   The interactivity should enhance the user experience, not detract from it.
5.  **Output Format**:
    *   Ensure the output is ONLY the HTML code, starting with `<!DOCTYPE html>` and ending with `</html>`.
    *   Do NOT include any markdown fences (like \`\`\`html) or any other text, comments, or explanations outside the HTML itself.

Strive for a polished, portfolio-quality website that the user would be proud to share.
Consider using modern design trends and interactive patterns.
""")

_SYSTEM_PROMPT_FIX_HTML = textwrap.dedent(f"""
You are an expert web developer. You previously generated HTML code that has some validation errors.
Your task is to fix the provided HTML code based on the error messages.
Output ONLY the corrected, complete HTML code, starting with <!DOCTYPE html> and ending with </html>.
Do NOT include any markdown fences or explanations, just the raw HTML.

Original Resume Text (for context):
{{{{resume_text}}}}

Previous HTML with errors:
{{{{previous_html}}}}

Validation Errors:
{{{{errors}}}}

Correct the HTML code to resolve these errors.
""")

def _extract_html(raw_html_output: str) -> str:
    """
    Extracts HTML content from the LLM's raw output.
    Tries to find <!DOCTYPE html>...</html> block.
    Also handles markdown code fences like ```html ... ```.
    """
    # Attempt to find the core HTML structure
    doctype_start = raw_html_output.lower().find("<!doctype html>")
    html_end_tag = "</html>"
    html_end = raw_html_output.lower().rfind(html_end_tag)

    if doctype_start != -1 and html_end != -1 and doctype_start < html_end:
        # Extract from <!doctype html> to </html>
        return raw_html_output[doctype_start : html_end + len(html_end_tag)]

    # Fallback for markdown code blocks
    stripped_output = raw_html_output.strip()
    if stripped_output.startswith("```html") and stripped_output.endswith("```"):
        return stripped_output[7:-3].strip()
    if stripped_output.startswith("```") and stripped_output.endswith("```"): # Generic backticks
        return stripped_output[3:-3].strip()
    
    # If no specific markers found, return the stripped output, hoping it's clean HTML
    return stripped_output

def _validate_html_css(html_content: str) -> list[str]:
    """Validates HTML structure and inline CSS. Returns a list of error messages."""
    errors = []
    try:
        # HTML validation using html5lib (which is strict)
        parser = html5lib.HTMLParser(strict=True)
        document = parser.parse(html_content)
        # If parsing succeeds without error, html5lib considers it valid enough for basic structure.
        # For more detailed validation, a dedicated HTML validator tool/API would be needed.

    except html5lib.html5parser.ParseError as e:
        errors.append(f"HTML ParseError: {e.msg} (Code: {e.code}) at line {e.line}, col {e.col}")

    # CSS validation (for <style> tags)
    soup = BeautifulSoup(html_content, 'html.parser')
    css_logger = logging.getLogger('cssutils')

    for style_tag in soup.find_all('style'):
        if style_tag.string:
            css_text = style_tag.string
            current_css_errors = []

            class CaptureCSSLogHandler(logging.Handler):
                def __init__(self, error_list):
                    super().__init__()
                    self.error_list = error_list

                def emit(self, record):
                    # record.getMessage() gives the formatted log message from cssutils
                    self.error_list.append(f"CSS Error in <style> tag: {record.getMessage()}")

            capture_handler = CaptureCSSLogHandler(current_css_errors)
            
            original_level = css_logger.level
            original_handlers = list(css_logger.handlers) # Make a copy

            css_logger.addHandler(capture_handler)
            css_logger.setLevel(logging.INFO) # Capture INFO (warnings) and ERROR messages
            
            parser = cssutils.CSSParser(
                validate=True, 
                raiseExceptions=False # We are capturing logs, not exceptions
            )
            stylesheet = parser.parseString(css_text)
            
            # Restore logger state
            css_logger.setLevel(original_level)
            css_logger.handlers = original_handlers # Restore original handlers
            # More precise: css_logger.removeHandler(capture_handler) if sure no other changes happened

            errors.extend(current_css_errors)
            
    return errors

def generate_html_llm(raw_text: str, status_callback: Callable[[str], None] | None = None) -> str:
    """
    Generates a full HTML website directly from raw resume text using an LLM,
    with validation and a retry mechanism for fixing issues.

    Args:
        raw_text: The raw text from the resume.
        status_callback: An optional function to call with status updates.
    """
    cache_path = _HTML_CACHE_DIR / f"{_sha(raw_text)}.html"
    if cache_path.exists():
        if status_callback:
            status_callback("📄 Found cached HTML.")
        return cache_path.read_text(encoding='utf-8')

    current_html = ""
    last_errors = []

    for attempt in range(_MAX_FIX_ATTEMPTS + 1):
        if attempt == 0:
            # Initial generation attempt
            if status_callback:
                status_callback("🤖 Calling LLM for initial HTML generation...")
            messages = [
                {"role": "system", "content": _SYSTEM_PROMPT_HTML},
                {"role": "user", "content": raw_text},
            ]
        else:
            # Fixing attempt
            if status_callback:
                status_callback(f"🛠️ Attempting to fix errors (Attempt {attempt}/{_MAX_FIX_ATTEMPTS})...")
            
            prompt_fix = _SYSTEM_PROMPT_FIX_HTML.replace("{{resume_text}}", raw_text) \
                                                .replace("{{previous_html}}", current_html) \
                                                .replace("{{errors}}", "\\n".join(last_errors))
            if status_callback:
                status_callback("🤖 Asking LLM to correct the HTML...")
            messages = [
                {"role": "system", "content": prompt_fix},
                # The user role here is effectively the problematic HTML + errors
                {"role": "user", "content": f"Fix the following HTML based on the errors provided in the system prompt."}
            ]

        rsp = chat(model=_MODEL, messages=messages)
        raw_output = rsp.message.content
        current_html = _extract_html(raw_output)
        
        if status_callback:
            status_callback("🔍 Validating generated HTML/CSS...")
        validation_errors = _validate_html_css(current_html)
        
        if not validation_errors:
            if status_callback:
                status_callback("✅ HTML/CSS validation passed!")
            print("HTML/CSS validation passed.")
            cache_path.write_text(current_html, encoding='utf-8')
            return current_html
        
        last_errors = validation_errors
        print(f"Validation errors found (attempt {attempt + 1}/{_MAX_FIX_ATTEMPTS + 1}):")
        for err in last_errors:
            print(f"- {err}")
        if status_callback:
            status_callback(f"⚠️ Validation failed (Attempt {attempt + 1}/{_MAX_FIX_ATTEMPTS + 1}). Errors: {len(last_errors)}")


    if status_callback:
        status_callback(f"❌ Failed to generate valid HTML after {_MAX_FIX_ATTEMPTS + 1} attempts. Using last version.")
    print(f"Failed to generate valid HTML after {_MAX_FIX_ATTEMPTS + 1} attempts. Returning last generated version.")
    cache_path.write_text(current_html, encoding='utf-8') # Cache the last attempt anyway
    return current_html
