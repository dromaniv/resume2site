# Résumé-to-Site

Upload a PDF résumé → Get a dynamic, LLM-generated personal website!

✨ **Key Features** ✨
- **LLM-Powered Website Generation**: Directly creates modern, interactive websites from your résumé using multiple LLM providers (OpenAI GPT models or Ollama with Devstral).
- **Multiple LLM Providers**: Easy switching between OpenAI API and Ollama with a modular architecture.
- **Website Plan**: The LLM first analyzes the résumé and proposes a "website plan," which is displayed in the UI.
- **Interactive Website Refinement**: After generation, use the built-in chat interface to request changes and improvements to your website.
- **Automatic Generation**: Website generation starts automatically upon PDF upload or when changing generation modes.
- **Enhanced Preview**: View the generated website directly in the app with an enlarged preview pane.
- **Multiple Generation Modes**:
    - **LLM (Direct Website)**: The full LLM-powered generation with planning and validation, plus interactive refinement.
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

4. **Configure LLM Provider**
   
   **Option A: Using OpenAI API (Recommended)**
   - Set your OpenAI API key as an environment variable:
     ```powershell
     $env:OPENAI_API_KEY="your_openai_api_key_here"
     ```
   - Or create a `.env` file in the project root:
     ```
     LLM_PROVIDER=openai
     OPENAI_API_KEY=your_openai_api_key_here
     ```
   
   **Option B: Using Ollama (Local)**
   - Install Ollama if you don't have it: https://ollama.com
   - Set the environment variable:
     ```powershell
     $env:LLM_PROVIDER="ollama"
     ```
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
   - Preview your generated website!
   - **Use the chat interface** to request changes and improvements to your website.

---

## 💬 Interactive Website Refinement

After your website is generated, you can use the built-in chat interface to make changes:

### Quick Actions
- **🎨 Change Colors**: Request color scheme updates
- **📱 Improve Mobile**: Enhance mobile responsiveness  
- **✨ Add Animations**: Add hover effects and smooth transitions
- **🔤 Improve Typography**: Enhance fonts and text styling

### Example Requests
- "Change the color scheme to blue and white"
- "Add a dark mode toggle"
- "Make the skills section more visually appealing with progress bars"
- "Add hover effects to the project cards"
- "Increase the font size for better readability"
- "Add social media icons to the contact section"
- "Reorganize the layout to put projects before experience"
- "Add a professional photo placeholder"

The LLM will process your request and update the website in real-time!

---

## 📄 Project Structure

```
app/
 ├── extractor.py     # Extracts text from PDF
 ├── parser_llm.py    # LLM-based résumé to JSON parser
 ├── parser_rule.py   # Rule-based résumé to JSON parser
 ├── generator_llm.py # LLM-based résumé to Website generator (direct HTML)
 ├── generator_rule.py# Renders HTML from JSON using templates (formerly generator.py)
 ├── llm_client.py    # LLM abstraction layer for multiple providers
 ├── config.py        # Configuration for LLM providers and models
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

- The **LLM (Direct Website)** mode is the most advanced, offering features like website planning and HTML/CSS validation.
- The LLM modes cache results (website plans and final HTML) in the `.cache/` directory to avoid redundant LLM queries.
- The in-app preview displays the website with all CSS and JS embedded.
- The download button provides a single `website.html` file.