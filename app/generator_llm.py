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
import html5lib  # For HTML5 parsing
import cssutils
import logging
import json  # Add json import
from typing import Callable  # Add Callable

from utils import _sha

# Configure cssutils logging to be less verbose for common errors
cssutils.log.setLevel(logging.CRITICAL)  # Only show critical errors from cssutils

# Model and cache configuration
_MODEL = "deepseek-coder-v2"

# Determine project root from this file's location
# app/generator_llm.py -> app.parent is app/ -> app.parent.parent is project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_HTML_CACHE_DIR = _PROJECT_ROOT / ".cache" / "html"  # Use absolute path
_PLAN_CACHE_DIR = _PROJECT_ROOT / ".cache" / "plans"  # Cache for plans

_HTML_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_PLAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)  # Create plan cache directory
_MAX_FIX_ATTEMPTS = 2  # Maximum attempts to fix HTML/CSS issues
_MAX_VISUAL_TWEAK_ATTEMPTS = 1  # Maximum attempts for visual tweaks

_SYSTEM_PROMPT_PLAN = textwrap.dedent(
    f"""\
You are an expert resume analyst and web strategist.
Your task is to analyze the provided text. 
First, determine if the text likely contains information typically found in a resume (e.g., skills, experience, education, projects).
If it DOES, generate a concise plan for a personal portfolio website based on its content. The plan should outline the main sections and key information to include.
If it does NOT seem to contain resume-like information, state that briefly.

Output Format:
- Start with "IS_RESUME: TRUE" or "IS_RESUME: FALSE".
- If "IS_RESUME: TRUE", follow with "PLAN:" on a new line, then the plan details (e.g., Header, Contact, Summary, Experience, Education, Skills, Projects).
- If "IS_RESUME: FALSE", follow with "REASON:" on a new line, then a very brief, neutral explanation (e.g., "The text does not appear to contain typical resume sections.").

Example for a resume-like text:
IS_RESUME: TRUE
PLAN:
- Header: [Candidate's Name], [Candidate's Tagline/Current Role]
- Contact Information: Email, Phone, LinkedIn, GitHub
- Summary/About Me: Brief overview.
- Work Experience: Roles, companies, dates, responsibilities.
- Education: Degrees, institutions, dates.
- Skills: List of skills.
- Projects: Project descriptions.

Example for non-resume text:
IS_RESUME: FALSE
REASON: The text does not appear to contain typical resume sections.
"""
)

_SYSTEM_PROMPT_HTML = textwrap.dedent(
    f"""\
You are an expert web designer and developer with a keen eye for modern aesthetics and user interaction.
Your goal is to transform this resume into a compelling *personal online presence* that showcases the individual's skills, experience, and personality.
Think beyond a simple document conversion; aim to build a mini-website that tells a story and encourages engagement.

You will be given a plan for a personal portfolio website, derived from a resume.
Based on the provided résumé text AND the website plan, generate a COMPLETE, MODERN, BEAUTIFUL, and INTERACTIVE single HTML file.

Website Plan:
{{{{website_plan}}}}

Résumé Text:
{{{{resume_text}}}}

Key requirements for the generated HTML:
1.  **Structure**: Well-structured and semantically correct HTML5, following the provided website plan.
    *   Consider creative layouts (e.g., a prominent hero section, two-column sections where appropriate, card-based designs for projects/experience) to make the page visually interesting and not just a linear list.
2.  **Content**: Accurately represent all relevant information from the résumé text, organized according to the plan.
    *   **Hero Section**: Create an impactful header or hero section with the candidate's name and headline/tagline.
    *   **Contact Information**: Clearly present email, phone, GitHub, LinkedIn. Consider using icons for these.
    *   **Summary/About Me**: Craft an engaging Summary/About Me section. If the resume is formal, try to inject a bit of personality while remaining professional. This is a key area to make it feel like a personal site.
    *   **Work Experience**: Detail job titles, companies, dates, and responsibilities/achievements (ideally as bullet points).
    *   **Education**: List degrees, institutions, and dates.
    *   **Skills**: Categorize skills if possible (e.g., languages, tools, frameworks). Consider a visually appealing way to present these (e.g., badges, grouped lists).
    *   **Projects**: If present, make this a highlight. For each project, include descriptions and links if available. Consider a card-based or gallery-like layout if there are multiple projects.
    *   **Call to Action**: Include a subtle but clear call to action, perhaps inviting users to connect on LinkedIn, view projects on GitHub, or reach out via email.
3.  **Styling (CSS)**:
    *   Embed all CSS directly within the HTML file, either in `<style>` tags in the `<head>` or as inline styles.
    *   The design should be visually appealing, modern, professional, and *personal*.
    *   Use a good color palette (consider a unique but professional primary/accent color), excellent typography (web-safe fonts, clear hierarchy), and thoughtful layout.
    *   Ensure the website is responsive and looks good on different screen sizes (desktop, tablet, mobile). Use a viewport meta tag.
    *   Employ icons (e.g., from a simple SVG set or font icon if easily embeddable) to enhance visual appeal for contact info, section titles, or skills.
4.  **Interactivity (JavaScript)**:
    *   Embed all JavaScript directly within the HTML file in `<script>` tags, preferably at the end of the `<body>`.
    *   Incorporate subtle animations, smooth scrolling for internal links, interactive elements (e.g., hover effects on cards, perhaps a simple filter for skills/projects if applicable and easy to implement).
    *   The interactivity should enhance the user experience and modern feel, not be distracting.
5.  **Favicon**: Include a simple, generic favicon in the `<head>`. This could be an appropriate emoji embedded as an SVG data URI, or a simple SVG icon.
    *   Example Emoji Favicon: `<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📄</text></svg>">` (Replace 📄 with a more suitable emoji like 🧑‍💻, 💼, ✨, or similar).
6.  **Output Format**:
    *   Ensure the output is ONLY the HTML code, starting with `<!DOCTYPE html>` and ending with `</html>`.
    *   Do NOT include any markdown fences (like \\\\`\\\\`\\\\`html) or any other text, comments, or explanations outside the HTML itself.

Strive for a polished, portfolio-quality website that the user would be proud to share.
Remember, the output should be a *personal website*, not just a digital resume. Make it memorable, engaging, and reflective of a professional brand.
Consider modern design trends and interactive patterns.
"""
)

_SYSTEM_PROMPT_FIX_HTML = textwrap.dedent(
    f"""\
You are an expert web developer. You previously generated HTML code that had some issues.
Your task is to fix the provided HTML code based on the validation errors.

Original Résumé Text (for context, do not regenerate from this, only fix the HTML):
{{{{resume_text}}}}

Website Plan (for context):
{{{{website_plan}}}}

Previously Generated HTML (with issues):
```html
{{{{previous_html}}}}
```

Validation Errors:
```
{{{{errors}}}}
```

Instructions:
1.  Carefully analyze the validation errors.
2.  Modify ONLY the problematic parts of the `previous_html` to fix these errors.
3.  Ensure all CSS is in `<style>` tags or inline, and all JS is in `<script>` tags.
4.  The output should be the complete, corrected HTML code, starting with `<!DOCTYPE html>` and ending with `</html>`.
5.  Do NOT include any markdown fences (like \\`\\`\\`html) or any other text, comments, or explanations outside the HTML itself.
"""
)

_SYSTEM_PROMPT_QUALITY_TWEAKS = textwrap.dedent(
    f"""\
You are an expert web designer and developer. You previously generated an HTML website that is structurally valid,
but it could be improved for overall quality (including visual clarity, accessibility, and basic functionality) based on the following suggestions.

Original Résumé Text (for context, do not regenerate from this, only tweak the HTML):\n{{{{resume_text}}}}

Website Plan (for context):\n{{{{website_plan}}}}

Current HTML:\n```html\n{{{{current_html}}}}\n```

Quality Improvement Suggestions:\n```\n{{{{quality_feedback}}}}\n```

Instructions:

1.  Carefully review the quality improvement suggestions.
2.  Modify the `current_html` to address these suggestions. Focus on CSS adjustments, minor HTML structural changes for layout/accessibility, or fixing simple issues like broken internal links if feasible.
3.  Do NOT significantly alter the content or the core structure defined by the website plan.
4.  Ensure all CSS is in `<style>` tags or inline, and all JS is in `<script>` tags.
5.  The output should be the complete, tweaked HTML code, starting with `<!DOCTYPE html>` and ending with `</html>`.
6.  Do NOT include any markdown fences (like \\\\`\\\\`\\\\`html) or any other text, comments, or explanations outside the HTML itself.
"""
)


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
    if stripped_output.startswith("```") and stripped_output.endswith(
        "```"
    ):  # Generic backticks
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
        errors.append(
            f"HTML ParseError: {e.msg} (Code: {e.code}) at line {e.line}, col {e.col}"
        )

    # CSS validation (for <style> tags)
    soup = BeautifulSoup(html_content, "html.parser")
    css_logger = logging.getLogger("cssutils")

    for style_tag in soup.find_all("style"):
        if style_tag.string:
            css_text = style_tag.string
            current_css_errors = []

            class CaptureCSSLogHandler(logging.Handler):
                def __init__(self, error_list):
                    super().__init__()
                    self.error_list = error_list

                def emit(self, record):
                    # record.getMessage() gives the formatted log message from cssutils
                    self.error_list.append(
                        f"CSS Error in <style> tag: {record.getMessage()}"
                    )

            capture_handler = CaptureCSSLogHandler(current_css_errors)

            original_level = css_logger.level
            original_handlers = list(css_logger.handlers)  # Make a copy

            css_logger.addHandler(capture_handler)
            css_logger.setLevel(
                logging.INFO
            )  # Capture INFO (warnings) and ERROR messages

            parser = cssutils.CSSParser(
                validate=True,
                raiseExceptions=False,  # We are capturing logs, not exceptions
            )
            stylesheet = parser.parseString(css_text)

            # Restore logger state
            css_logger.setLevel(original_level)
            css_logger.handlers = original_handlers  # Restore original handlers
            # More precise: css_logger.removeHandler(capture_handler) if sure no other changes happened

            errors.extend(current_css_errors)

    return errors


def _analyze_website_quality(html_content: str) -> list[str]:
    """
    Performs a heuristic analysis of the HTML for potential quality issues (visual, accessibility, basic functionality).
    Returns a list of textual feedback/suggestions.
    """
    feedback = []
    soup = BeautifulSoup(html_content, "html.parser")

    # --- Visual Clarity Checks (existing) ---
    # 1. Viewport meta tag
    if not soup.find("meta", attrs={"name": "viewport"}):
        feedback.append(
            'Visual: Consider adding a viewport meta tag for responsiveness: <meta name=\\"viewport\\" content=\\"width=device-width, initial-scale=1.0\\">.'
        )

    # 2. Basic font size
    body_style = soup.body.get("style", "") if soup.body else ""
    style_tags = soup.find_all("style")
    body_font_size = None
    # Check inline style on body
    if "font-size" in body_style:
        match = re.search(r"font-size:\\s*(\\d+)px", body_style)
        if match:
            body_font_size = int(match.group(1))

    # Check style tags for body font-size (simplified: looks for 'body {' and 'font-size')
    if not body_font_size:
        for tag in style_tags:
            if tag.string and "body {" in tag.string and "font-size" in tag.string:
                match = re.search(
                    r"body\\s*{[^}]*font-size:\\s*(\\d+)px", tag.string, re.DOTALL
                )
                if match:
                    body_font_size = int(match.group(1))
                    break

    if body_font_size and body_font_size < 14:
        feedback.append(
            f"Visual: Base body font size ({body_font_size}px) seems small. Consider increasing to 14-16px for readability."
        )
    elif not body_font_size:
        feedback.append(
            "Visual: Consider explicitly setting a base font-size for the body (e.g., 16px) for consistent readability."
        )

    # 3. Heading differentiation
    h1_tags = soup.find_all("h1")
    h2_tags = soup.find_all("h2")
    p_tags = soup.find_all("p")

    # This is a very rough check. Real check needs computed styles.
    if h1_tags and p_tags:
        feedback.append(
            "Visual: Ensure <h1> headings are significantly larger than paragraph text for clear visual hierarchy."
        )
    if h2_tags and p_tags:
        feedback.append(
            "Visual: Ensure <h2> headings are noticeably larger than paragraph text and distinct from <h1>."
        )

    # 4. Basic spacing/padding
    #    Checks if any style attribute or rule *mentions* padding or margin for these.
    common_sections = soup.find_all(
        ["header", "footer", "main", "section", "article", "aside"]
    )
    cards = soup.find_all(
        lambda tag: "card" in tag.get("class", [])
    )  # Example: finds class="card"

    elements_to_check_spacing = common_sections + cards
    if elements_to_check_spacing:
        missing_spacing_count = 0
        for elem in elements_to_check_spacing[:3]:  # Check a few samples
            has_spacing_style = False
            if elem.get("style") and (
                "padding:" in elem.get("style") or "margin:" in elem.get("style")
            ):
                has_spacing_style = True

            if not has_spacing_style:
                # Check <style> tags for rules targeting this element's tag name or class
                for s_tag in style_tags:
                    if s_tag.string:
                        # Simplified check for tag name
                        if f"{elem.name} {{" in s_tag.string and (
                            "padding:" in s_tag.string or "margin:" in s_tag.string
                        ):
                            has_spacing_style = True
                            break
                        # Simplified check for class (if any)
                        for cls in elem.get("class", []):
                            if f".{cls} {{" in s_tag.string and (
                                "padding:" in s_tag.string or "margin:" in s_tag.string
                            ):
                                has_spacing_style = True
                                break
                        if has_spacing_style:
                            break
            if not has_spacing_style:
                missing_spacing_count += 1

        if (
            missing_spacing_count > 1
        ):  # If multiple checked elements lack explicit spacing
            feedback.append(
                "Visual: Some key sections/blocks might lack sufficient padding/margins. Review spacing."
            )

    # 5. Image presence
    if not soup.find_all("img"):
        feedback.append(
            "Visual: No images (<img> tags) found. Consider adding images/icons for engagement."
        )

    # 6. Simplified Contrast Check
    elements_for_contrast = soup.find_all(["p", "span", "li", "a"] + h1_tags + h2_tags)
    contrast_issues_found = 0
    for elem in elements_for_contrast[:10]:  # Check a sample
        style_str = elem.get("style", "")
        fg_color_match = re.search(r"color:\\s*([^;]+)", style_str)
        bg_color_match = re.search(
            r"(?:background-color|background):\\s*([^;]+)", style_str
        )
        if (
            fg_color_match
            and bg_color_match
            and fg_color_match.group(1).strip() == bg_color_match.group(1).strip()
            and fg_color_match.group(1).strip() not in ["transparent", "inherit"]
        ):
            contrast_issues_found += 1
            break
    if contrast_issues_found > 0:
        feedback.append(
            "Visual: Potential low contrast. Found elements where foreground/background colors might be too similar."
        )

    # --- Functionality & Accessibility Checks (New) ---
    # 7. Link validation
    all_links = soup.find_all("a", href=True)
    broken_internal_links = 0
    suspicious_external_links = 0
    for link_tag in all_links:
        href = link_tag["href"]
        if href.startswith("#") and len(href) > 1:
            target_id = href[1:]
            if not soup.find(id=target_id):
                broken_internal_links += 1
                feedback.append(
                    f"Link: Internal link '{href}' appears broken (no element with id='{target_id}' found)."
                )
        elif href.startswith("http://") or href.startswith("https://"):
            if (
                "." not in href.split("://", 1)[-1]
            ):  # Very basic check for a domain part
                suspicious_external_links += 1
                feedback.append(
                    f"Link: External link '{href}' seems malformed or lacks a domain. (Note: This doesn't check if the link works)."
                )
        # mailto:, tel: etc. are ignored for this basic check

    # 8. Button accessibility
    buttons = soup.find_all("button")
    buttons_without_text = 0
    for btn in buttons:
        btn_text = btn.get_text(strip=True)
        aria_label = btn.get("aria-label", "").strip()
        if not btn_text and not aria_label:
            buttons_without_text += 1
            feedback.append(
                f"Accessibility: A <button> element was found without discernible text content or an aria-label. Add one for clarity."
            )
            if buttons_without_text >= 2:  # Limit feedback messages for this
                break

    return feedback


def _generate_website_plan(
    raw_text: str, status_callback: Callable[[str], None] | None = None
) -> tuple[str | None, bool, str | None]:
    """
    Analyzes resume text, determines if it's a valid resume, and generates a website plan.
    Caches the plan and validity.

    Returns:
        A tuple: (plan_text_or_none, is_resume_bool, reason_if_not_resume_or_none)
    """
    cache_key = _sha(raw_text)
    plan_cache_path = _PLAN_CACHE_DIR / f"{cache_key}.txt"  # Store as text file

    if plan_cache_path.exists():
        if status_callback:
            status_callback("📄 Found cached website plan.")
        cached_content = plan_cache_path.read_text(encoding="utf-8")

        is_resume_line = cached_content.split("\\n", 1)[0]
        is_resume = "IS_RESUME: TRUE" in is_resume_line

        if is_resume:
            # Ensure "PLAN:" exists before splitting
            if "PLAN:" in cached_content:
                plan_content = cached_content.split("PLAN:", 1)[1].strip()
            else:  # Fallback if format is slightly off but IS_RESUME is TRUE
                plan_content = "Plan details not found in expected format in cache."
            return plan_content, True, None
        else:
            # Ensure "REASON:" exists before splitting
            if "REASON:" in cached_content:
                reason_content = cached_content.split("REASON:", 1)[1].strip()
            else:  # Fallback if format is slightly off
                reason_content = "Reason not found in expected format in cache."
            return None, False, reason_content

    if status_callback:
        status_callback("🧠 Analyzing resume and generating website plan...")

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT_PLAN},
        {"role": "user", "content": raw_text},
    ]
    rsp = chat(model=_MODEL, messages=messages)
    plan_output = rsp.message.content.strip()

    # Save the raw output to cache
    plan_cache_path.write_text(plan_output, encoding="utf-8")

    is_resume_line = plan_output.split("\\n", 1)[0]
    is_resume = "IS_RESUME: TRUE" in is_resume_line

    if is_resume:
        # Ensure "PLAN:" exists before splitting
        if "PLAN:" in plan_output:
            plan_content = plan_output.split("PLAN:", 1)[1].strip()
            if status_callback:
                status_callback(
                    f"📝 Plan generated successfully."
                )  # Simplified message for brevity in status
        else:
            plan_content = "Plan generation succeeded, but plan details are not in the expected format."
            if status_callback:
                status_callback(
                    f"⚠️ Plan generated, but details might be missing from output."
                )
        return plan_content, True, None
    else:
        # Ensure "REASON:" exists before splitting
        if "REASON:" in plan_output:
            reason_content = plan_output.split("REASON:", 1)[1].strip()
        else:
            reason_content = "Could not determine reason for invalid resume (output format unexpected)."
        if status_callback:
            status_callback(f"⚠️ Not a valid resume. Reason: {reason_content}")
        return None, False, reason_content


def generate_html_llm(
    raw_text: str, status_callback: Callable[[str], None] | None = None
) -> str:
    """
    Generates a full HTML website directly from raw resume text using an LLM,
    with validation, a retry mechanism for fixing issues, and visual tweaking.

    Args:
        raw_text: The raw text from the resume.
        status_callback: An optional function to call with status updates.
    """
    # Step 1: Generate/retrieve website plan
    website_plan, is_resume, reason = _generate_website_plan(raw_text, status_callback)

    if not is_resume:
        error_message = (
            f"The provided text does not appear to be a valid resume. Reason: {reason}"
        )
        if status_callback:
            status_callback(f"❌ {error_message}")  # Error message starts with ❌
        return f"<html><head><title>Error</title></head><body><h1>Input Error</h1><p>{error_message}</p></body></html>"

    if not website_plan:  # Should not happen if is_resume is True, but as a safeguard
        error_message = "Failed to generate a website plan, even though input was considered a resume."
        if status_callback:
            status_callback(f"❌ {error_message}")  # Error message starts with ❌
        return f"<html><head><title>Error</title></head><body><h1>Processing Error</h1><p>{error_message}</p></body></html>"

    if status_callback:
        # Send plan separately
        status_callback(f"📝 **Website Plan:**\n```\n{website_plan}\n```")
        # Then send status about starting HTML generation
        status_callback("⏳ Now generating Website based on this plan...")

    # Step 2: Generate HTML based on the plan and resume text
    # HTML cache key is based on raw_text + plan_text to ensure plan changes trigger regeneration
    html_cache_key_content = raw_text + "||PLAN||" + website_plan
    cache_path = _HTML_CACHE_DIR / f"{_sha(html_cache_key_content)}.html"

    if cache_path.exists():
        if status_callback:
            status_callback("📄 Found cached Website (post-plan).")
        return cache_path.read_text(encoding="utf-8")

    current_html = ""
    last_errors: list[str] = []

    # --- Stage 1: HTML Generation and Validation ---
    for attempt in range(_MAX_FIX_ATTEMPTS + 1):
        if attempt == 0:
            # Initial generation attempt
            if status_callback:
                status_callback(
                    f"🤖 Attempt {attempt + 1}/{_MAX_FIX_ATTEMPTS + 1}: Calling LLM for initial Website generation (using plan)..."
                )

            current_system_prompt_html = _SYSTEM_PROMPT_HTML.replace(
                "{{website_plan}}", website_plan
            )
            current_system_prompt_html = current_system_prompt_html.replace(
                "{{resume_text}}", raw_text
            )

            messages = [
                {"role": "system", "content": current_system_prompt_html},
                {
                    "role": "user",
                    "content": "Generate the HTML website based on the provided plan and resume text.",
                },
            ]
        else:
            # Fixing attempt
            if status_callback:
                status_callback(
                    f"🛠️ Attempt {attempt + 1}/{_MAX_FIX_ATTEMPTS + 1}: Trying to fix Website. Errors: {len(last_errors)}"
                )

            prompt_fix = _SYSTEM_PROMPT_FIX_HTML.replace("{{resume_text}}", raw_text)
            prompt_fix = prompt_fix.replace(
                "{{website_plan}}", website_plan
            )  # Add plan to fix prompt
            prompt_fix = prompt_fix.replace("{{previous_html}}", current_html)
            prompt_fix = prompt_fix.replace("{{errors}}", "\\n".join(last_errors))

            messages = [
                {"role": "system", "content": prompt_fix},
                {
                    "role": "user",
                    "content": "Fix the provided HTML based on the errors.",
                },  # Simplified user message
            ]

        rsp = chat(model=_MODEL, messages=messages)
        raw_output = rsp.message.content
        current_html = _extract_html(raw_output)

        if status_callback:
            status_callback("🔍 Validating generated Website (HTML/CSS)...")
        validation_errors = _validate_html_css(current_html)

        if not validation_errors:
            if status_callback:
                status_callback("✅ Website (HTML/CSS) validation passed!")
            print("HTML/CSS validation passed.")
            # HTML is valid, break this loop and proceed to visual analysis or caching
            break

        last_errors = validation_errors
        print(
            f"Validation errors found (attempt {attempt + 1}/{_MAX_FIX_ATTEMPTS + 1}):"
        )
        for err_item in last_errors:  # Renamed err to err_item to avoid conflict
            print(f"- {err_item}")
        if status_callback:
            status_callback(
                f"⚠️ Validation failed (Attempt {attempt + 1}/{_MAX_FIX_ATTEMPTS + 1}). Errors: {len(last_errors)}"
            )

        if (
            attempt == _MAX_FIX_ATTEMPTS
        ):  # If it's the last attempt and still has errors
            final_failure_message = f"Failed to generate valid Website after {attempt + 1} attempts due to HTML/CSS errors. Returning last generated version."
            if status_callback:
                status_callback(f"❌ {final_failure_message}")
            print(final_failure_message)
            cache_path.write_text(
                current_html, encoding="utf-8"
            )  # Cache the last attempt anyway
            return current_html

    # --- Stage 2: Visual Clarity Analysis and Tweaking ---
    if not validation_errors:  # Proceed only if HTML/CSS is valid
        for visual_attempt in range(_MAX_VISUAL_TWEAK_ATTEMPTS + 1):
            if status_callback:
                status_callback(
                    f"🎨 Analyzing website quality (Attempt {visual_attempt + 1}/{_MAX_VISUAL_TWEAK_ATTEMPTS + 1})..."
                )

            quality_feedback = _analyze_website_quality(current_html)

            if not quality_feedback:
                if status_callback:
                    status_callback(
                        "✨ Website quality analysis passed, no immediate suggestions."
                    )
                break  # No feedback, so no tweaks needed.

            if (
                visual_attempt == _MAX_VISUAL_TWEAK_ATTEMPTS
            ):  # Maxed out visual tweak attempts
                if status_callback:
                    status_callback(
                        f"⚠️ Reached max quality tweak attempts. Using current version. Feedback: {quality_feedback}"
                    )
                break

            if status_callback:
                status_callback(
                    f"🖌️ Attempting quality tweaks based on {len(quality_feedback)} suggestions..."
                )
                status_callback(
                    f"Suggestions:\\n"
                    + "\\n".join([f"- {f}" for f in quality_feedback])
                )

            prompt_quality_tweaks = _SYSTEM_PROMPT_QUALITY_TWEAKS.replace(
                "{{resume_text}}", raw_text
            )
            prompt_quality_tweaks = prompt_quality_tweaks.replace(
                "{{website_plan}}", website_plan
            )
            prompt_quality_tweaks = prompt_quality_tweaks.replace(
                "{{current_html}}", current_html
            )
            prompt_quality_tweaks = prompt_quality_tweaks.replace(
                "{{quality_feedback}}", "\\n".join(quality_feedback)
            )

            messages_visual = [
                {"role": "system", "content": prompt_quality_tweaks},
                {
                    "role": "user",
                    "content": "Refine the HTML based on the quality improvement suggestions provided.",
                },
            ]

            rsp_visual = chat(model=_MODEL, messages=messages_visual)
            raw_output_visual = rsp_visual.message.content
            tweaked_html = _extract_html(raw_output_visual)

            # Validate the tweaked HTML again (important!)
            if status_callback:
                status_callback("🔍 Validating tweaked Website (HTML/CSS)...")
            validation_errors_after_tweak = _validate_html_css(tweaked_html)

            if not validation_errors_after_tweak:
                if status_callback:
                    status_callback("✅ Tweaked Website passed HTML/CSS validation!")
                current_html = tweaked_html  # Update current_html with the successfully tweaked version
                break
            else:
                if status_callback:
                    status_callback(
                        f"⚠️ Tweaked Website failed HTML/CSS validation. Errors: {validation_errors_after_tweak}. Reverting to pre-tweak version for this attempt."
                    )

    # --- Final Stage: Caching and Returning ---
    if status_callback:
        status_callback("💾 Caching final website version.")
    cache_path.write_text(current_html, encoding="utf-8")
    return current_html
