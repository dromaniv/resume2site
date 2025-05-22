# Résumé-to-Site

Upload a PDF résumé → Get a dynamic, LLM-generated personal website!

✨ **Key Features** ✨
- **LLM-Powered Website Generation**: Directly creates modern, interactive websites from your résumé using an LLM (Devstral via Ollama).
- **Website Plan**: The LLM first analyzes the résumé and proposes a "website plan," which is displayed in the UI.
- **Automatic Generation**: Website generation starts automatically upon PDF upload or when changing generation modes.
- **Quality Analysis & Tweaks**: Includes an automated step to analyze the generated website for visual clarity, link validity, and basic accessibility, then prompts the LLM to make improvements.
- **Enhanced Preview**: View the generated website directly in the app with an enlarged preview pane.
- **Multiple Generation Modes**:
    - **LLM (Direct Website)**: The full LLM-powered generation with planning and quality tweaks.
    - **LLM (JSON + Template)**: Parses the résumé to JSON using an LLM, then uses a Jinja2 template.
    - **Rule-based (JSON + Template)**: Parses the résumé to JSON using traditional rules, then uses a Jinja2 template.
- **Caching**: LLM responses for plans and generated websites are cached to speed up subsequent runs with the same input.

---

## 📦 How to Run

1. **Clone the project**
   ```bash
   git clone <your-repo-url>
   cd resume2site
   ```

2. **Create and activate a virtual environment**
   ```bash
   python3.11 -m venv .venv  
   source .venv/bin/activate  # Mac/Linux
   .venv\Scripts\activate     # Windows
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Start Ollama (if using LLM mode)**
   - Install Ollama if you don't have it: https://ollama.com
   - Run locally:
     ```bash
     ollama run devstral
     ```

5. **Run the app**
   ```bash
   streamlit run app/gui.py
   ```

6. **Open your browser**
   - Go to: http://localhost:8501
   - Upload a PDF resume
   - Choose your preferred generation mode.
   - View the plan (for LLM Direct Website mode) and the generation process.
   - Preview and download your generated website!

---

## 📄 Project Structure

```
app/
 ├── extractor.py     # Extracts text from PDF
 ├── parser_llm.py    # LLM-based résumé to JSON parser
 ├── parser_rule.py   # Rule-based résumé to JSON parser
 ├── generator_llm.py # LLM-based résumé to Website generator (direct HTML)
 ├── generator_rule.py# Renders HTML from JSON using templates (formerly generator.py)
 ├── cleaner.py       # Schema normalizer and data cleanup
 ├── schema_resume.py # Base JSON schema for résumé data
 ├── gui.py           # Main Streamlit application UI and logic
 ├── utils.py         # Utility functions (e.g., hashing)
 ├── templates/
 │    └── base.html   # Jinja2 HTML template for JSON-based generation
 └── static/
      └── style.css   # CSS styles (primarily for template-based generation)
.cache/               # Stores cached LLM responses (plans, HTML)
```

---

## ⚡ Quick Notes

- The **LLM (Direct Website)** mode is the most advanced, offering features like website planning and quality-driven iterative improvements.
- The LLM modes cache results (website plans and final HTML) in the `.cache/` directory to avoid redundant Ollama queries.
- The in-app preview displays the website with all CSS and JS embedded.
- The download button provides a single `website.html` file.