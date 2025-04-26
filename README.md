# Résumé-to-Site

Upload a PDF résumé → Get a static personal website!

✅ Supports both:
- Rule-based extraction (fast, offline, classic)
- LLM-based extraction (DeepSeek Coder V2 via Ollama)

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
     ollama run deepseek-coder:2
     ```

5. **Run the app**
   ```bash
   streamlit run app/gui.py
   ```

6. **Open your browser**
   - Go to: http://localhost:8501
   - Upload a PDF resume
   - Choose "LLM" or "Rule-based"
   - Download your generated website!

---

## 📄 Project Structure

```
app/
 ├── extractor.py     # Extracts text from PDF
 ├── parser_llm.py    # LLM parsing (DeepSeek)
 ├── parser_rule.py   # Rule-based parsing
 ├── generator.py     # Renders HTML from JSON
 ├── cleaner.py       # Schema normalizer
 ├── schema_resume.py # Base JSON schema
 ├── templates/
 │    └── base.html   # HTML template
 └── static/
      └── style.css   # CSS styles
```

---

## ⚡ Quick Notes

- The **LLM mode** caches results so it won't query Ollama every time.
- Preview uses **inline CSS** inside Streamlit for correct styling.
- Download button gives you a **clean `index.html`** + separate `static/style.css`.