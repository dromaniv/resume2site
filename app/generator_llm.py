"""
LLM-based HTML website generator.

• Supports multiple LLM providers (Ollama with Devstral, OpenAI with GPT models)
• Caches responses in .cache/html/<sha256>.html so the model is
  queried only once per unique resume text.
• Includes basic HTML and CSS validation and a retry mechanism for fixes.
"""

from __future__ import annotations
import re
import textwrap
from pathlib import Path
from llm_client import chat
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
try:
    from config import get_model_for_provider
    _MODEL = get_model_for_provider()
except ImportError:
    _MODEL = "devstral"  # Fallback if config is not available

# Determine project root from this file's location
# app/generator_llm.py -> app.parent is app/ -> app.parent.parent is project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_HTML_CACHE_DIR = _PROJECT_ROOT / ".cache" / "html"  # Use absolute path
_PLAN_CACHE_DIR = _PROJECT_ROOT / ".cache" / "plans"  # Cache for plans

_HTML_CACHE_DIR.mkdir(parents=True, exist_ok=True)
_PLAN_CACHE_DIR.mkdir(parents=True, exist_ok=True)  # Create plan cache directory
_MAX_FIX_ATTEMPTS = 2  # Maximum attempts to fix HTML/CSS issues
_SYSTEM_PROMPT_PLAN = textwrap.dedent(
    f"""\
You are an expert resume analyzer and web planner. Your job is to parse a given text and produce a structured plan for a personal resume website with multiple pages.

Instructions:

1. Resume Check: First, determine if the provided text ({{resume_text}}) is a resume. A resume typically contains structured information about a person’s career (e.g. work experience, education, skills, etc.). If the text lacks clear resume sections or reads like a narrative/cover letter, it may not be a resume.

2. Not a Resume: If the input is not clearly a resume, output exactly:
   IS_RESUME: FALSE
   Explanation: <brief reason the text is not a resume>
   Do not include any additional content. For example, if the text has no employment or education details, you might say it appears to be a cover letter or unrelated text.

3. Resume Plan: If the input is a resume, output a detailed website content plan in YAML format (no Markdown or code fences). Follow these guidelines for the YAML structure:
   - Begin with IS_RESUME: TRUE.
   - Next, have a top-level key sections: that contains a list of sections/pages for the personal website. Each section will correspond to a separate HTML file.
   - Include appropriate sections based on the resume content. Common section names (as separate pages) include Home, About, Experience, Education, Skills, Projects, Contact. Use these exact names for consistency. Only include sections that have relevant information in the resume. For example, include a "Projects" section only if projects are mentioned in the resume.
   - Each section in the list should be an item with a name field and the content extracted from the resume:
     - Home: Provide the person’s name and a brief tagline or headline (e.g. current job title or personal slogan). Example: name: John Doe, tagline: Full-Stack Developer with 5 years of experience.
     - About: A short bio or professional summary. Use the resume’s summary/objective statement if available, or create a brief overview of the candidate’s profile using details from the resume. This should be a few sentences highlighting key themes (e.g. "Software engineer with expertise in front-end development...").
     - Experience: List each work experience as an item. For each job, include sub-fields: job title/role, company (and location if given), dates (start to end, or start to present), and a description of responsibilities or achievements. The description can be a brief paragraph or bullet points summarizing key accomplishments. Ensure this section is granular – include multiple jobs if present, in reverse chronological order.
     - Education: List educational background. For each degree or qualification, include: degree title (e.g. B.Sc. in Computer Science), institution, graduation year (or years attended), and any notable honors or GPA if mentioned.
     - Skills: Provide a list of skills. If the resume groups skills by category (e.g. Programming Languages, Tools, Languages), preserve those groupings with sub-lists or headings. Otherwise, list all key skills as a YAML list.
     - Projects: If the resume mentions personal or professional projects, list each project with a name/title, a short description, and optionally technologies used or a link if provided.
     - Contact: Extract contact information. Include fields like email, phone, address/location, and any web links (LinkedIn, GitHub, personal website). Use labels as keys (e.g. email: jane.doe@example.com, linkedin: linkedin.com/in/janedoe). If the resume has a dedicated contact section, use that. If not, use details from the header of the resume.
   - Maintain clear indentation in the YAML. Each section (page) should be listed under the sections: list with its respective content nested properly. For example:
       IS_RESUME: TRUE
       sections:
         - name: Home
           name_on_page: Jane Doe
           tagline: Full-Stack Developer with 5+ years of experience
         - name: About
           summary: "Passionate software engineer with experience in developing scalable web applications and a background in computer science..."
         - name: Experience
           jobs:
             - title: Senior Developer
               company: TechCorp Inc, New York, NY
               dates: 2019 - Present
               details:
                 - Led a team of 5 engineers to develop...
                 - Implemented a CI/CD pipeline that reduced deployment time by 30%...
             - title: Junior Developer
               company: Web Solutions, San Francisco, CA
               dates: 2016 - 2019
               details:
                 - Collaborated on front-end development for client projects...
                 - Maintained documentation and assisted in...
         - name: Education
           degrees:
             - degree: B.Sc. in Computer Science
               institution: University of XYZ
               year: 2016
               honors: "Magna Cum Laude"
         - name: Skills
           skills:
             - JavaScript
             - Python
             - React
             - Node.js
             - HTML
             - CSS
             - Git
             - Agile methodologies
         - name: Projects
           projects:
             - title: "Personal Portfolio Website"
               description: "Designed and developed a responsive portfolio site to showcase projects, using HTML, CSS, and JavaScript."
             - title: "Machine Learning Blog"
               description: "Created a technical blog platform with a recommendation system, using Python (Flask) and deployed on Heroku."
         - name: Contact
           contact_info:
             email: jane.doe@example.com
             phone: 123-456-7890
             linkedin: linkedin.com/in/janedoe
             location: "San Francisco, CA"
       *The above is an example structure. The actual content and sections should be derived from the provided resume.*
   - Do not fabricate information. Use only details present in the resume_text. If certain typical sections (like Projects or Summary) are missing from the resume, simply omit them from the plan rather than adding new content.
   - Keep the plan concise but comprehensive. It should capture all important resume details in an organized way.

4. Output Only the Plan: The assistant’s answer should only contain the YAML plan (or the IS_RESUME false notice). Do not include explanations, commentary, or any formatting outside the YAML structure. The YAML should be valid and properly indented for easy reading.

Ensure the output strictly follows the above guidelines.

"""
)

_SYSTEM_PROMPT_HTML = textwrap.dedent(
    f"""\
You are a seasoned front-end web developer. Using the website_plan and the original resume_text, your task is to generate one complete, single-file HTML website containing all sections of a personal resume. The overall site structure and content details are provided in {{website_plan}}. Produce a polished, standalone HTML page that includes every section (Home, About, Experience, Education, Skills, Projects, Contact) in a single document, adhering to the following requirements:

- Page Content & Structure:
  - All Sections in One File: Include every section listed in {{website_plan}} (e.g., Home, About, Experience, Education, Skills, Projects, Contact) within one HTML file. Use distinct <section> elements (with id attributes matching their section names, e.g., <section id="skills">) so navigation links can scroll to each part.
  - Header & Navigation: At the top of the page, include a consistent site header with a navigation bar that appears on all viewports. The nav bar should have links to all sections listed in {{website_plan}} (use exact names and order). Each link should use an anchor href to scroll to the corresponding section (e.g., href="#experience"). The currently viewed section link should be highlighted as the user scrolls (you can add an "active" class via JavaScript).
  - Footer: At the bottom of the file, include a footer that appears on all pages within this single document. It can contain the person’s name, a copyright notice, and contact info or social links.
  - Section Content: For each section, present its details clearly:
    - Home: Create an attractive landing “hero” at the top of the page featuring the person’s name and tagline (from {{website_plan}}). Include a brief welcome message or overview paragraph pulled from the plan’s Home content.
    - About: Present the bio or professional summary from the plan in a well-formatted paragraph or two. Use headings (<h2>) for the section title.
    - Experience: List each work experience from the plan in reverse chronological order. For each job, create a “card” or <article> containing:
      • Job title (<h3>), company and location (<p>), and dates (<p>).
      • A list (<ul>) or paragraph summarizing responsibilities/achievements.
      Separate each job with spacing or a horizontal rule (<hr>) to maintain clarity.
    - Education: For each degree from the plan, create a sub-section with:
      • Degree and institution (<h3>), date/year (<p>), and any honors or details.
      List degrees in reverse chronological order.
    - Skills: If the plan groups skills by category, create sub-headings for each category (e.g., <h3>Programming Languages</h3>) and display each skill as a “badge” (e.g., <span class="badge">JavaScript</span>). Use a flex or grid layout so badges wrap flexibly across multiple columns.
    - Projects: For each project from the plan, create a card (<div class="project-card">) containing:
      • Project title (<h3>), a short description (<p>), and if available, links (GitHub or live demo) as <a> elements styled as buttons.  
      Use consistent card styles (background, padding, border-radius).
    - Contact: Present contact details clearly: email, phone, LinkedIn, GitHub, location. Use appropriate icons (e.g., ✉️, 📞, 📍) next to each item. Also include a simple contact form (<form>) with Name, Email, Message fields and a submit button that uses a mailto: action to open the user’s email client.
  - Active Section Indication: As the user scrolls, the navigation link for the section currently in view should be visually highlighted. Implement this using JavaScript that adds/removes an .active class on nav <a> elements based on scroll position.

- Design & Styling:
  - Inline CSS: Embed all CSS within a single <style> block in the <head>. Define a consistent theme:
    • Choose a primary color for header background and link highlights, and an accent color for buttons and badges.
    • Select a font-family for headings and body (use web-safe fonts, e.g., "Helvetica Neue", Arial, sans-serif).
    • Define global styles for body (margin, padding, line-height, background-color), headings, paragraphs, links, lists, and badges.
    • Style the navigation bar: fixed or sticky at top, with a background color, horizontal list of links, and hover/focus effects.
    • Style each section (<section>) with padding (e.g., padding: 60px 0) and alternate background colors or subtle separators to distinguish between sections.
    • Card Styles: For Experience and Projects, cards should have a white background, subtle box-shadow, border-radius, and padding.
    • Badge Styles: Display each <span class="badge"> with inline-block, background-color (light accent), padding (4px 8px), border-radius: 12px, and margin: 4px.
    • Contact Form: Style inputs and textarea with full width, padding, border, border-radius. Style the submit button with the primary color and hover effect.
    • Footer: Style the footer with smaller text, background matching header or a dark shade, and centered content.
  - Consistent Aesthetics: Use the same color palette and typography across all sections. If using section background variations (e.g., alternating white and light gray), keep them subtle to maintain a cohesive look.
  - Hero/Banner: For Home, implement a full-width banner with a background color or gradient. Display the person’s name in a large, bold font (<h1>) and the tagline in a slightly smaller font (<h2>). Center the text vertically and horizontally.
  - Visual Elements: Incorporate cards, badges, and icons:
    • Cards: Use for Experience and Projects. Cards should use consistent padding, margin, and box-shadow. On hover, slightly increase the shadow or scale (use transition).
    • Badges: Use for skills. Arrange badges in a wrapping flex container.
    • Icons: Use Unicode emoji (✉️, 📞, 🎓, 💼, 📍) or embed simple SVG icons inline. If decorative, use aria-hidden="true"; if informative, add aria-label.
  - Animations: Add subtle CSS transitions/animations:
    • For nav links: on hover, change color or add underline with transition: 0.2s.
    • For cards: on hover, increase box-shadow or slightly scale (transition: transform 0.2s, box-shadow 0.2s).
    • Section Fade-In: Add a fade-in effect for each section when it scrolls into view (use CSS classes and JavaScript to add .visible).
  - Semantic HTML5: Use <header> for the navigation, <nav> for the nav menu, <main> wrapping all <section> elements, and <footer> for the footer. Each Experience card and Project card can be wrapped in <article>.

- Responsive Design:
  - Mobile-First: Define styles for small screens first, then use @media queries for larger viewports:
    • Mobile: Nav links collapse into a hamburger menu. Include a <button id="menu-toggle">☰</button> that toggles the nav menu’s visibility using JavaScript. Sections stack vertically, and cards use full width.
    • Tablets & Desktops (min-width: 768px): Nav links display horizontally. Experience and Project cards arrange in a multi-column grid. Skills badges display in multiple columns. Sections have increased padding.
  - Use flexible units (%) or rem for spacing and typography. Ensure images (if any) use max-width: 100% so they scale down.

- Accessibility:
  - Provide alt text for any images (if you include a profile photo in Home, use <img alt="Photo of [Name]">). For inline SVG or emoji icons, if not purely decorative add aria-label or aria-hidden="true" if decorative.
  - Use a <button> element for the hamburger menu with aria-label="Toggle navigation" and aria-expanded attributes. When the menu is opened, set aria-expanded="true".
  - Ensure proper heading hierarchy: Home’s <h1> is followed by <h2> for subheadings; each section title uses <h2>; Experience job titles use <h3>, etc.
  - Maintain sufficient color contrast: text on background should meet WCAG AA.
  - Add :focus styles for links and buttons (e.g., outline or box-shadow) so keyboard users can navigate.

- Inline Script:
  - At the end of the <body>, include a <script> block with JavaScript to:
    • Toggle the mobile menu by adding/removing an .open class on the nav when the hamburger <button> is clicked.
    • Highlight the active section link as the user scrolls by adding/removing an .active class on nav <a> elements based on scroll position.
    • Add a fade-in effect: on scroll, detect when each <section> enters the viewport and add a .visible class to trigger CSS transitions.

- Output Format:
  - The result must be a fully valid HTML5 document, starting with <!DOCTYPE html> and ending with </html>. Include <html lang="en">, <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head> and a <title> (e.g., "John Doe – Resume").
  - Self-Contained: All CSS and JavaScript must be embedded in <style> and <script> tags within the same file. Do not link to external resources (stylesheets, scripts, or images). If you need icons, use inline SVG or Unicode.
  - No Extra Text: Output only the raw HTML code. Do not include any explanation, comments (unless necessary HTML comments), or Markdown. Do not wrap the HTML in code fences.

Generate the complete single-file HTML website containing all sections from {{website_plan}}, following these guidelines.

Website Plan:
{{{{website_plan}}}}

Résumé Text:
{{{{resume_text}}}}
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

_SYSTEM_PROMPT_USER_CHANGES = textwrap.dedent(
    f"""\
You are an expert web developer helping a user refine their personal website.
The user has a generated website and wants to make specific changes to improve it.

Current Website HTML:
```html
{{{{current_html}}}}
```

Original Résumé Text (for context):
{{{{resume_text}}}}

Website Plan (for context):
{{{{website_plan}}}}

User's Change Request:
{{{{user_request}}}}

Instructions:
1. Carefully read and understand the user's change request.
2. Apply the requested changes to the current HTML while maintaining the overall structure and quality.
3. Common change types and how to handle them:
   - **Color scheme changes**: Update CSS color variables and styles
   - **Layout changes**: Modify CSS flexbox, grid, or positioning
   - **Content additions**: Add new HTML elements with appropriate styling
   - **Typography changes**: Update font families, sizes, weights in CSS
   - **Interactive features**: Add or modify JavaScript functionality
   - **Responsive design**: Ensure changes work across different screen sizes
4. If the request is unclear, make reasonable interpretations that improve the site.
5. Preserve all existing functionality and maintain the professional quality.
6. Ensure all CSS remains in `<style>` tags or inline, and all JS remains in `<script>` tags.
7. Keep the website responsive and maintain modern design principles.
8. The output should be the complete, modified HTML code, starting with `<!DOCTYPE html>` and ending with `</html>`.
9. Do NOT include any markdown fences (like \\`\\`\\`html) or any other text, comments, or explanations outside the HTML itself.

Focus on making the requested changes while preserving the professional quality and functionality of the website.
If you cannot implement a specific feature due to complexity, make a simpler version that achieves a similar visual effect.
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
        errors.append(f"HTML ParseError: {str(e)}")

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


def _generate_website_plan(
    raw_text: str, 
    status_callback: Callable[[str], None] | None = None, 
    model: str | None = None
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
    rsp = chat(model=model or _MODEL, messages=messages)
    plan_output = rsp.message.content.strip()

    # Save the raw output to cache
    plan_cache_path.write_text(plan_output, encoding="utf-8")

    is_resume_line = plan_output.split("\\n", 1)[0]
    is_resume = "IS_RESUME: TRUE" in is_resume_line

    if is_resume:
        # For a valid resume, return the plan content after "IS_RESUME: TRUE"
        plan_content = plan_output.strip()
        if status_callback:
            status_callback("📝 Plan generated successfully.")
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
    raw_text: str, 
    status_callback: Callable[[str], None] | None = None,
    model: str | None = None
) -> str:
    """
    Generates a full HTML website directly from raw resume text using an LLM,
    with validation, a retry mechanism for fixing issues, and visual tweaking.

    Args:
        raw_text: The raw text from the resume.
        status_callback: An optional function to call with status updates.
    """    # Step 1: Generate/retrieve website plan
    website_plan, is_resume, reason = _generate_website_plan(raw_text, status_callback, model)

    if not is_resume:
        error_message = (
            f"The provided text does not appear to be a valid resume. Reason: {reason}"
        )
        if status_callback:
            status_callback(f"❌ {error_message}")  # Error message starts with ❌
        return ""

    if not website_plan:  # Should not happen if is_resume is True, but as a safeguard
        error_message = "Failed to generate a website plan, even though input was considered a resume."
        if status_callback:
            status_callback(f"❌ {error_message}")  # Error message starts with ❌
        return ""

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
                {"role": "system", "content": prompt_fix},                {
                    "role": "user",
                    "content": "Fix the provided HTML based on the errors.",
                },  # Simplified user message
            ]

        rsp = chat(model=model or _MODEL, messages=messages)
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

    if status_callback:
        status_callback("💾 Caching final website version.")
    cache_path.write_text(current_html, encoding="utf-8")
    return current_html


def apply_user_changes_llm(
    current_html: str,
    user_request: str,
    resume_text: str = "",
    website_plan: str = "",
    status_callback: Callable[[str], None] | None = None,
    model: str | None = None
) -> str:
    """
    Applies user-requested changes to the current website HTML using an LLM.

    Args:
        current_html: The current HTML website code
        user_request: The user's change request
        resume_text: Original resume text for context
        website_plan: Website plan for context
        status_callback: Optional function to call with status updates

    Returns:
        Modified HTML code with the requested changes applied
    """
    if status_callback:
        status_callback("🔄 Processing your change request...")

    # Prepare the prompt with user request and current HTML
    prompt_changes = _SYSTEM_PROMPT_USER_CHANGES.replace("{{current_html}}", current_html)
    prompt_changes = prompt_changes.replace("{{resume_text}}", resume_text)
    prompt_changes = prompt_changes.replace("{{website_plan}}", website_plan)
    prompt_changes = prompt_changes.replace("{{user_request}}", user_request)

    messages = [
        {"role": "system", "content": prompt_changes},
        {
            "role": "user",
            "content": f"Please apply the following changes to my website: {user_request}",
        },
    ]

    if status_callback:
        status_callback("🤖 Calling LLM to apply changes...")

    try:
        rsp = chat(model=model or _MODEL, messages=messages)
        raw_output = rsp.message.content
        modified_html = _extract_html(raw_output)

        if status_callback:
            status_callback("🔍 Validating modified website...")

        # Validate the modified HTML
        validation_errors = _validate_html_css(modified_html)

        if validation_errors:
            if status_callback:
                status_callback(f"⚠️ Validation found {len(validation_errors)} issues, but applying changes anyway.")
            # Note: We could implement a fixing loop here like in generate_html_llm, 
            # but for user changes, we'll be more permissive
        else:
            if status_callback:
                status_callback("✅ Modified website validation passed!")

        return modified_html

    except Exception as e:
        error_msg = f"Error applying changes: {str(e)}"
        if status_callback:
            status_callback(f"❌ {error_msg}")
        print(error_msg)
        return current_html  # Return original HTML if changes failed

def summarize_html_changes_llm(old_html: str, new_html: str, model: str | None = None) -> str:
    """
    Use LLM to analyze and summarize the major changes between two HTML versions.
    
    Args:
        old_html: The original HTML content
        new_html: The modified HTML content  
        model: The LLM model to use (optional)
        
    Returns:
        A natural language summary of the changes made
    """
    
    # Extract key differences for analysis
    def extract_key_info(html_content: str) -> dict:
        """Extract key information from HTML for comparison"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract text content by sections
            sections = {}
            for header in soup.find_all(['h1', 'h2', 'h3', 'h4']):
                section_name = header.get_text().strip()
                # Get content until next header of same or higher level
                content = []
                for sibling in header.find_next_siblings():
                    if sibling.name in ['h1', 'h2', 'h3', 'h4']:
                        break
                    if sibling.get_text().strip():
                        content.append(sibling.get_text().strip())
                sections[section_name] = ' '.join(content)[:200]  # Limit length
                
            # Extract styling info
            style_tags = soup.find_all('style')
            css_content = ' '.join([tag.get_text() for tag in style_tags])
            
            # Look for key CSS properties
            colors = re.findall(r'color:\s*([^;]+)', css_content)
            backgrounds = re.findall(r'background[^:]*:\s*([^;]+)', css_content)
            fonts = re.findall(r'font-family:\s*([^;]+)', css_content)
            
            return {
                'sections': sections,
                'colors': colors[:5],  # Limit to first 5
                'backgrounds': backgrounds[:3],
                'fonts': fonts[:3],
                'total_length': len(html_content)
            }
        except Exception:
            return {'error': 'Could not parse HTML'}
    
    old_info = extract_key_info(old_html)
    new_info = extract_key_info(new_html)
    
    # Create analysis prompt
    analysis_prompt = f"""
Analyze the changes between two versions of a resume website and provide a concise summary.

OLD VERSION INFO:
- Sections: {list(old_info.get('sections', {}).keys())}
- Colors used: {old_info.get('colors', [])}
- Fonts: {old_info.get('fonts', [])}
- Content length: {old_info.get('total_length', 0)} characters

NEW VERSION INFO:  
- Sections: {list(new_info.get('sections', {}).keys())}
- Colors used: {new_info.get('colors', [])}
- Fonts: {new_info.get('fonts', [])}
- Content length: {new_info.get('total_length', 0)} characters

SECTION CONTENT CHANGES:
"""
    
    # Compare section content
    old_sections = old_info.get('sections', {})
    new_sections = new_info.get('sections', {})
    
    for section in set(list(old_sections.keys()) + list(new_sections.keys())):
        old_content = old_sections.get(section, "")
        new_content = new_sections.get(section, "")
        
        if section not in old_sections:
            analysis_prompt += f"\n+ NEW SECTION '{section}': {new_content[:100]}..."
        elif section not in new_sections:
            analysis_prompt += f"\n- REMOVED SECTION '{section}'"
        elif old_content != new_content:
            analysis_prompt += f"\n* MODIFIED '{section}': Content changed from {len(old_content)} to {len(new_content)} chars"
    
    analysis_prompt += """

Please provide a concise, user-friendly summary of the major changes made. Focus on:
1. Visual/design changes (colors, fonts, layout)
2. Content changes (new sections, expanded content, etc.)
3. Structural improvements (SEO, accessibility, etc.)

Format as bullet points with emojis. Be specific but concise. Example:
• 🎨 Changed color scheme to professional blue and gray palette
• 📝 Expanded the Projects section with technical details and metrics
• 📱 Improved mobile responsiveness with better layout stacking
• 🔍 Added SEO meta tags for better search visibility

Keep it under 150 words and focus on the most impactful changes.
"""

    try:
        messages = [{"role": "user", "content": analysis_prompt}]
        response = chat(model=model or _MODEL, messages=messages)
          # Extract content from LLM response
        summary = response.message.content.strip()
        
        # Clean up the response formatting
        # Handle cases where bullets are formatted as "• - " or similar
        summary = summary.replace('• - ', '• ')
        summary = summary.replace('•-', '• ')
        
        # Ensure proper line breaks between bullet points
        if '• ' in summary and '\n' not in summary:
            # If all bullet points are on one line, split them
            summary = summary.replace('• ', '\n• ')
            summary = summary.strip()
        
        # Ensure it starts with a bullet point
        if not summary.startswith('•'):
            # If response doesn't start with bullet, try to format it
            lines = summary.split('\n')
            formatted_lines = []
            for line in lines:
                line = line.strip()
                if line and not line.startswith('•'):
                    formatted_lines.append(f"• {line}")
                elif line.startswith('•'):
                    formatted_lines.append(line)
            summary = '\n'.join(formatted_lines)
        
        return summary if summary else "• ✨ Website has been updated with your requested changes"
        
    except Exception as e:
        print(f"Error summarizing changes: {e}")
        return "• ✨ Website has been updated with your requested changes"
