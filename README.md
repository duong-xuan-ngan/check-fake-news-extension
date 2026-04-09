# Fake News Checker - Chrome Extension

A Chrome extension that allows users to highlight text on any webpage and verify it for fake news using AI-powered analysis.

## 📋 Prerequisites

Before getting started, ensure you have the following installed:

- **Node.js** (v18 or higher) & npm
- **Python 3.13+**
- **[uv](https://docs.astral.sh/uv/)** package manager

  ```bash
  # Install uv on macOS
  brew install uv

  # Or via pip
  pip install uv
  ```

- **Google Chrome** browser

---

## 🚀 Quick Start

### Step 1: Set Up the Backend

The backend is a FastAPI service that handles AI-powered text analysis.

```bash
# Navigate to the backend directory
cd fn-extension-backend

# Install dependencies (creates virtual environment automatically)
uv sync

# Start the development server
uv run uvicorn main:app --reload
```

The backend server will start at **`http://localhost:8000`** with auto-reload enabled.

**Verify it's running:**
- Open `http://localhost:8000/health` in your browser - you should see `{"Service": "is up"}`
- Interactive API docs available at `http://localhost:8000/docs`

---

### Step 2: Build the Frontend (Side Panel)

The extension's UI is built with React and Vite.

```bash
# Navigate to the frontend source directory
cd sidepanel-src

# Install Node.js dependencies
npm install

# Build the extension assets
npm run build
```

This compiles the React app and outputs the built files to the `extension/` folder.

**Optional - Development mode:**
```bash
npm run dev
```

---

### Step 3: Install the Extension in Chrome

1. Open Chrome and navigate to: `chrome://extensions/`
2. Enable **Developer mode** (toggle in the top-right corner)
3. Click **Load unpacked** (appears in the top-left)
4. Select the `extension` folder from the project root (`check-fake-new-extension/extension`)

You should now see the **Fake News Checker** extension in your Chrome toolbar.

---

## 🎯 How to Use

1. **Ensure the backend server is running** on `http://localhost:8000`
2. Navigate to any webpage (note: extensions don't work on `chrome://` pages)
3. **Highlight any text** or news snippet you want to verify
4. **Right-click** on the highlighted text
5. Select **"Analyze with Fake News Checker"** from the context menu
6. The extension's side panel will open automatically and send the text to the backend for AI analysis

---

## 📁 Project Structure

```
check-fake-new-extension/
├── backend/                 # Simple backend directory (legacy)
├── data/                    # Data utilities
├── extension/               # Chrome extension files (manifest, icons, etc.)
│   ├── background.js        # Service worker
│   ├── content.js           # Content script
│   ├── manifest.json        # Extension manifest (v3)
│   └── icons/               # Extension icons
├── fn-extension-backend/    # FastAPI backend service
│   ├── main.py              # FastAPI application
│   ├── ai_core/             # AI analysis modules
│   ├── pyproject.toml       # Python dependencies
│   └── README.md            # Backend documentation
├── sidepanel-src/           # React side panel source code
│   ├── package.json         # Node dependencies
│   └── ...                  # React/Vite files
└── README.md                # This file
```

---

## 🔧 Troubleshooting

### Backend won't start
- Ensure Python 3.13+ is installed: `python --version`
- Try recreating the virtual environment: `rm -rf .venv && uv sync`

### Extension doesn't work
- Verify the backend is running at `http://localhost:8000`
- Check the browser console for errors (right-click extension icon → "Inspect")
- Make sure you built the frontend with `npm run build` before loading the extension

### CORS errors
- The backend is configured to allow requests from `chrome-extension://*` and localhost
- If you change the backend port, update the CORS settings in `fn-extension-backend/main.py`

---

## 🛠️ Development Workflow

When making changes to the frontend:

```bash
# After editing React files in sidepanel-src/
npm run build

# Then reload the extension in Chrome:
# 1. Go to chrome://extensions/
# 2. Click the reload icon on the Fake News Checker extension
```

The backend auto-reloads on file changes thanks to the `--reload` flag.

---

## 📚 API Endpoints

| Method | Endpoint     | Description              |
|--------|--------------|--------------------------|
| GET    | `/`          | Hello world              |
| GET    | `/health`    | Health check             |
| POST   | `/analyze`   | Analyze text for credibility |

Interactive docs: `http://localhost:8000/docs`
