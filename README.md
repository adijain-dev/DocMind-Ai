# DocMind AI — Intelligent API Documentation & SDK Agent 🚀

**DocMind AI** is an AI-powered documentation assistant, API tester, and SDK generator for developers. It ingests API specifications (OpenAPI/Swagger in YAML or JSON, PDFs, Markdown, and plain text), chunks and embeds them locally into a vector database (ChromaDB), and enables natural-language multi-lingual querying (English & Hinglish), code generation, live HTTP API testing, API comparison, and PDF chat exports.

---

## 🛠 Tech Stack

### Backend
- **Framework:** [FastAPI](https://fastapi.tiangolo.com/) (Python 3.10 - 3.14+)
- **Server:** [Uvicorn](https://www.uvicorn.org/) (ASGI server with auto-reload)
- **AI / LLM Provider:** [Groq](https://groq.com/) Cloud SDK
  - Default Model: `llama-3.3-70b-versatile`
  - Fast Model: `llama-3.1-8b-instant` (for simple queries)
- **Vector Database:** [ChromaDB](https://www.trychroma.com/) (Local persistent HNSW cosine index)
- **Embedding Model:** [SentenceTransformers](https://www.sbert.net/) (`all-MiniLM-L6-v2`)
- **Document Parsing:**
  - `PyMuPDF` (`fitz`) for PDF extraction
  - `PyYAML` and standard `json` for OpenAPI 3.x and Swagger 2.0 specs
- **HTTP Client / API Tester:** `httpx` (async HTTP/1.1 & HTTP/2 client)
- **Exporting:** `fpdf2` (vector PDF generator)
- **Validation:** `pydantic` v2

### Frontend
- **Interface:** Modern SPA Dashboard built with vanilla HTML5, CSS3, and modern ES6+ JavaScript
- **Typography:** JetBrains Mono & Syne
- **Features:** Dark/Light mode theme toggle, Real-time SSE (Server-Sent Events) chat streaming, Web Speech API voice input, Smart autocomplete suggestions, API comparison viewer, Interactive HTTP API testing console, SDK & README generator, and PDF/Markdown/Text chat export.

---

## 📂 Project Structure

```
├── api/
│   ├── api_docs/                # Pre-downloaded sample API specs (GitHub, Stripe, NASA, Discord, etc.)
│   ├── data/
│   │   ├── chroma_db/           # Persistent ChromaDB vector collections & SQLite index
│   │   └── uploads/             # Uploaded documentation files (.yaml, .json, .pdf, .md)
│   ├── frontend/
│   │   ├── index.html           # Main dashboard web interface
│   │   ├── app.js               # Legacy frontend script
│   │   └── style.css            # Legacy stylesheet
│   ├── routes/
│   │   ├── chat.py              # Chat Q&A, SSE streaming, API comparison, and PDF export
│   │   ├── generate.py          # SDK code generation & README generation
│   │   ├── test_api.py          # Real HTTP request tester endpoint
│   │   └── upload.py            # Spec/file parser and vector database ingestion
│   ├── services/
│   │   ├── document_parser.py   # PDF, Markdown, and OpenAPI/Swagger parsing
│   │   ├── qna_engine.py        # Language detection (English/Hinglish), prompt engineering & Groq LLM
│   │   └── vector_store.py      # ChromaDB embeddings, indexing, and semantic similarity search
│   ├── config.py                # Centralized paths and environment variable configuration
│   ├── download_apis.py         # Utility script to download 10 popular OpenAPI specifications
│   ├── main.py                  # FastAPI application entry point
│   ├── requirements.txt         # Package requirements
│   └── .env                     # API keys and environment variables
├── requirements.txt             # Root requirements file
├── run.py                       # Root launcher script
└── README.md                    # Project documentation
```

---

## ⚡ Getting Started

### 1. Prerequisites
- Python 3.10+ (tested up to Python 3.14)
- Groq API Key (get one free at [console.groq.com](https://console.groq.com))

### 2. Configure Environment Variables
Inside `api/.env`:
```env
GROQ_API_KEY=your_groq_api_key_here
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the Server
From the project root:
```bash
python run.py
```
Or with uvicorn directly:
```bash
uvicorn api.main:app --reload
```

### 5. Access the Web Dashboard
- **Web App:** [http://localhost:8000](http://localhost:8000)
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Alternative Redoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)

---

## 📡 API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | Health check endpoint |
| `GET` | `/api/apis` | List all indexed APIs in ChromaDB |
| `POST` | `/api/upload` | Upload and vectorize documentation (.pdf, .yaml, .json, .md) |
| `POST` | `/api/chat` | Non-streaming question answering with conversational memory |
| `POST` | `/api/chat/stream` | Server-Sent Events (SSE) streaming answers from Groq |
| `POST` | `/api/compare` | Parallel comparison of two APIs for a single query |
| `POST` | `/api/export-pdf` | Export conversation history to formatted PDF |
| `POST` | `/api/test` | Live HTTP client for endpoint testing with response timing |
| `POST` | `/api/generate-sdk` | Generate client SDK in Python, JS, Java, or cURL |
| `POST` | `/api/generate-readme` | Generate structured markdown README for any API |
| `POST` | `/api/download-sdk` | Download generated SDK code as a file |
| `POST` | `/api/download-readme` | Download generated README as a `.md` file |
