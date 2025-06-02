# Résumé-to-Site

Upload a PDF résumé → Get a dynamic, LLM-generated personal website!

✨ **Key Features** ✨
- **🤖 AI-Powered Website Generation**: Directly creates modern, interactive websites from your résumé using multiple LLM providers (OpenAI GPT-4o, GPT-4o-mini, or Ollama with DeepSeek Coder).
- **🔄 Multiple LLM Providers**: Easy switching between OpenAI API and Ollama with a modular, abstracted architecture.
- **🌐 Live Website Preview**: Built-in temporary HTTP server for real-time website preview - auto-opens in new browser tab, no external dependencies needed.
- **📝 Website Planning**: The LLM first analyzes the résumé and proposes a detailed "website plan," which is displayed in the UI before generation.
- **💬 Interactive Website Refinement**: After generation, use the built-in chat interface to request changes and improvements in natural language.
- **⚡ Automatic Generation**: Website generation starts automatically upon PDF upload or when changing generation modes.
- **🗂️ Smart Caching**: LLM responses for plans and generated websites are cached (SHA-256 based) to speed up subsequent runs with the same input.
- **🎨 Dark Theme UI**: Beautiful, modern dark theme with gradients and smooth animations throughout the interface.
- **📊 Website Statistics**: Real-time metrics showing file size, element count, generation mode, and number of refinements applied.
- **📱 Mobile-First Design**: Generated websites are responsive and mobile-optimized by default.
- **💾 Download & Share**: Download complete HTML files or share live preview URLs instantly.
- **🎯 Multiple Generation Modes**:
    - **AI Direct Build (Custom design & layout)**: Full LLM-powered generation with planning, HTML/CSS validation, and interactive refinement.
    - **AI Structured (Parsed data + Template)**: Parses the résumé to JSON using an LLM, then uses a professionally-designed Jinja2 template.
    - **Rule-based Parser (Pattern matching + Template)**: Parses the résumé to JSON using traditional pattern matching, then uses a Jinja2 template.
- **⚡ One-Click Enhancements**: Quick action buttons for instant improvements:
  - 🎨 **Professional Theme**: Modern color schemes with gradients
  - 📱 **Mobile Optimize**: Enhanced mobile responsiveness
  - ✨ **Add Animations**: Smooth hover effects and transitions
  - 🔤 **Typography Upgrade**: Better fonts and text hierarchy

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
     ```bash
     export OPENAI_API_KEY="your_openai_api_key_here"  # Mac/Linux
     ```
     ```powershell
     $env:OPENAI_API_KEY="your_openai_api_key_here"    # Windows
     ```
   - Or create a `.env` file in the project root:
     ```env
     LLM_PROVIDER=openai
     OPENAI_API_KEY=your_openai_api_key_here
     ```
   
   **Option B: Using Ollama (Local)**
   - Install Ollama if you don't have it: https://ollama.com
   - Set the environment variable:
     ```bash
     export LLM_PROVIDER="ollama"  # Mac/Linux
     ```
     ```powershell
     $env:LLM_PROVIDER="ollama"    # Windows
     ```
   - Pull and run the model:
     ```bash
     ollama pull deepseek-coder-v2
     ollama serve
     ```

5. **Run the app**
   ```bash
   streamlit run app/gui.py
   ```

6. **Open your browser**
   - Go to: http://localhost:8501
   - Upload a PDF resume
   - Choose your preferred generation mode
   - View the plan (for AI Direct Build mode) and the generation process
   - Your website will automatically open in a new tab for preview!
   - **Use the chat interface** to request changes and improvements to your website

---

## 🌐 Live Website Preview

The app now includes a built-in temporary HTTP server that automatically serves your generated website:

- **Automatic Preview**: Website opens in a new tab as soon as it's generated
- **Real-time Updates**: Changes made through the chat interface are instantly reflected
- **No Setup Required**: Server starts automatically - no external tools needed
- **Copy-Paste URL**: Click the server URL to copy it to your clipboard
- **Clean URLs**: Get a proper localhost URL that you can share or bookmark during development

---

## 💬 Interactive Website Refinement

After your website is generated, you can use the built-in chat interface to make changes:

### Quick Actions (One-Click Enhancements)
- **🎨 Professional Theme**: Apply modern professional color schemes with blues, grays, and gradients
- **📱 Mobile Optimize**: Enhance mobile responsiveness with proper stacking and touch-friendly elements
- **✨ Add Animations**: Add smooth hover effects, transitions, and animated progress bars
- **🔤 Typography Upgrade**: Improve fonts with modern Google Fonts and better text hierarchy

### Natural Language Requests
You can ask for virtually any change in plain English:
- "Change the color scheme to blue and white"
- "Add a dark mode toggle"
- "Make the skills section more visually appealing with progress bars"
- "Add hover effects to the project cards"
- "Increase the font size for better readability"
- "Add social media icons to the contact section"
- "Reorganize the layout to put projects before experience"
- "Add a professional photo placeholder"
- "Make it more modern and minimalist"
- "Add a navigation menu that scrolls to sections"

The LLM will process your request and update the website in real-time!

---

## 🔧 Technical Improvements

### Built-in HTTP Server
- **Zero Configuration**: Temporary server starts automatically when a website is generated
- **Smart Port Management**: Automatically finds available ports and handles conflicts
- **Session Management**: Proper cleanup when Streamlit session ends
- **Real-time Updates**: Website content updates instantly when changes are applied
- **Click-to-Copy URLs**: Server URLs can be copied to clipboard for easy sharing

### Enhanced LLM Integration
- **Provider Abstraction**: Unified interface for OpenAI and Ollama with easy switching
- **Model Configuration**: Environment-based model selection for different providers
- **Intelligent Caching**: SHA-256 based caching prevents redundant API calls
- **Error Handling**: Robust error recovery and retry mechanisms

### Improved User Experience
- **Live Preview**: Website opens automatically in new browser tab
- **Progress Tracking**: Real-time status updates during generation
- **Quick Actions**: One-click buttons for common website improvements
- **Chat Interface**: Natural language interaction for website modifications
- **Visual Feedback**: Clear status indicators and loading states
- **Dark Theme**: Comprehensive dark mode styling throughout the interface
- **Website Statistics**: Real-time metrics including file size, element count, and refinement tracking

---

## 📋 Project Structure

```
app/
 ├── extractor.py     # Extracts text from PDF
 ├── parser_llm.py    # LLM-based résumé to JSON parser
 ├── parser_rule.py   # Rule-based résumé to JSON parser (pattern matching)
 ├── generator_llm.py # LLM-based résumé to Website generator (direct HTML)
 ├── generator_rule.py# Renders HTML from JSON using templates
 ├── llm_client.py    # LLM abstraction layer for multiple providers
 ├── config.py        # Configuration for LLM providers and models
 ├── cleaner.py       # Schema normalizer and data cleanup
 ├── schema_resume.py # Base JSON schema for résumé data
 ├── gui.py           # Main Streamlit application UI and logic
 ├── utils.py         # Utility functions (e.g., hashing)
 ├── temp_server.py   # Built-in HTTP server for website preview
 ├── templates/
 │    └── base.html   # Jinja2 HTML template for JSON-based generation
 └── static/
      └── style.css   # CSS styles for template-based generation
.cache/               # Stores cached LLM responses (plans, HTML)
 ├── html/            # Cached generated HTML files  
 └── plans/           # Cached website plans
.env                  # Environment configuration (create from example)
requirements.txt      # Python dependencies
```

---

## ⚡ Quick Notes

- The **AI Direct Build** mode is the most advanced, offering features like website planning, HTML/CSS validation, and interactive refinement.
- The **AI Structured** mode combines LLM parsing with consistent templating for reliable results.
- The **Rule-based Parser** mode uses pattern matching for fast, deterministic parsing without LLM calls.
- All LLM modes cache results (website plans and final HTML) in the `.cache/` directory to avoid redundant API calls.
- The built-in preview server starts automatically and updates in real-time as you make changes.
- The download button provides a single, self-contained `website.html` file with all CSS and assets embedded.
- Environment variables can be set in a `.env` file or directly in your shell for easy configuration switching.
- The dark theme UI provides a modern, professional experience with smooth animations and gradients.
- Quick action buttons allow for instant website improvements without typing detailed requests.
- Chat interface maintains a history of all refinements for easy tracking of changes.
- Website statistics provide real-time metrics about your generated site including file size and modification count.