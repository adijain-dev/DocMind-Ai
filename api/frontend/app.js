// ╔══════════════════════════════════════════════════════════════════╗
// ║  app.js — API QnA Agent — Complete Frontend Logic              ║
// ║  Features: Streaming · Voice · Suggestions · PDF Export        ║
// ╚══════════════════════════════════════════════════════════════════╝

// ─── State ──────────────────────────────────────────────────────────────────
let streamingEnabled  = true;
let isRecording       = false;
let recognition       = null;           // SpeechRecognition instance
let chatHistory       = [];             // For PDF export: [{role, content, timestamp}]
let suggestionsTimer  = null;

// Smart suggestion bank — question type se map hota hai
const SUGGESTION_BANK = {
  auth:        ["How do I authenticate?", "What auth methods are supported?", "How to use API key?", "OAuth flow kaise kaam karta hai?"],
  error:       ["What does 401 error mean?", "How to handle rate limiting?", "Common error codes kya hain?", "Retry strategy kya honi chahiye?"],
  endpoint:    ["What endpoints are available?", "What is the base URL?", "How to call the search endpoint?", "List all GET endpoints"],
  param:       ["What parameters are required?", "What is the response format?", "Query params kaise pass kare?", "Request body ka structure kya hai?"],
  limit:       ["What are the rate limits?", "How many requests per minute?", "Is there a free tier?", "Request quota kya hai?"],
  example:     ["Show me an example request", "Give me a curl example", "Postman collection hai kya?", "Sample code in Python?"],
  default:     ["What can this API do?", "How do I get started?", "What is the authentication method?", "Show available endpoints"],
};

// ─── Init ────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
  loadApiList();
  initStreamToggle();
  initVoiceInput();
  initSmartSuggestions();
  initUploadForm();
  initAutoDetect();
  initTesterTab();
  initPdfExport();
});

// ─── 1. API List ─────────────────────────────────────────────────────────────
async function loadApiList() {
  try {
    const res  = await fetch("/api/apis");
    const data = await res.json();
    const sel  = document.getElementById("api-select");
    if (!sel) return;

    sel.innerHTML = '<option value="">— API Select karo —</option>';
    (data.apis || []).forEach(name => {
      const opt   = document.createElement("option");
      opt.value   = name;
      opt.textContent = name;
      sel.appendChild(opt);
    });
  } catch (err) {
    console.error("API list load failed:", err);
  }
}

// ─── 2. Streaming Toggle ─────────────────────────────────────────────────────
function initStreamToggle() {
  const toggle = document.getElementById("stream-toggle");
  if (!toggle) return;
  toggle.checked = streamingEnabled;
  toggle.addEventListener("change", () => {
    streamingEnabled = toggle.checked;
    showToast(streamingEnabled ? "⚡ Streaming ON" : "📦 Streaming OFF");
  });
}

// ─── 3. Send Question ────────────────────────────────────────────────────────
async function sendQuestion() {
  const input     = document.getElementById("question-input");
  const apiSelect = document.getElementById("api-select");
  const answerBox = document.getElementById("answer-box");
  const sendBtn   = document.getElementById("send-btn");

  const question = input?.value?.trim();
  const apiName  = apiSelect?.value;

  if (!question)                { showToast("❗ Question likho pehle");    return; }
  if (!apiName)                 { showToast("❗ Pehle ek API select karo"); return; }
  if (!answerBox)               return;

  // UI Reset
  answerBox.textContent = "";
  setLoading(sendBtn, true);
  hideSuggestions();

  // Save user message to history
  pushToHistory("user", question);
  input.value = "";

  if (streamingEnabled) {
    await sendStreaming(question, apiName, answerBox);
  } else {
    await sendNonStreaming(question, apiName, answerBox);
  }

  setLoading(sendBtn, false);
}

// Streaming request
async function sendStreaming(question, apiName, answerBox) {
  try {
    const res = await fetch("/api/chat/stream", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ question, api_name: apiName }),
    });

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buffer  = "";
    let   fullAnswer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith("data: ")) continue;
        try {
          const event = JSON.parse(line.slice(6));
          if (event.error) {
            answerBox.textContent += "\n\n❌ " + event.error;
            break;
          }
          if (!event.done) {
            answerBox.textContent += event.text;
            fullAnswer            += event.text;
          } else {
            updateTokenCount(event.tokens_used);
          }
        } catch (_) {}
      }
    }

    pushToHistory("assistant", fullAnswer.trim());

  } catch (err) {
    answerBox.textContent = "❌ Network error: " + err.message;
  }
}

// Non-streaming request
async function sendNonStreaming(question, apiName, answerBox) {
  try {
    const res  = await fetch("/api/chat", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ question, api_name: apiName }),
    });
    const data = await res.json();
    const answer = data.answer || data.detail || "Error occurred";
    answerBox.textContent = answer;
    updateTokenCount(data.tokens_used);
    pushToHistory("assistant", answer);
  } catch (err) {
    answerBox.textContent = "❌ Network error: " + err.message;
  }
}

// ─── 4. 🎤 Voice Input ───────────────────────────────────────────────────────
function initVoiceInput() {
  const micBtn = document.getElementById("mic-btn");
  if (!micBtn) return;

  // Browser support check
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRec) {
    micBtn.title   = "Voice input browser mein support nahi hai";
    micBtn.style.opacity = "0.4";
    micBtn.style.cursor  = "not-allowed";
    return;
  }

  recognition = new SpeechRec();
  recognition.lang          = "en-IN";   // Indian English
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  recognition.onstart = () => {
    isRecording = true;
    micBtn.classList.add("recording");
    micBtn.title = "Bol raha hoon... (click to stop)";
    showToast("🎤 Bol raha hoon...");
  };

  recognition.onresult = (event) => {
    const input = document.getElementById("question-input");
    if (!input) return;
    const transcript = Array.from(event.results)
      .map(r => r[0].transcript)
      .join("");
    input.value = transcript;
    triggerSuggestions(transcript);   // Voice se bhi suggestions trigger ho
  };

  recognition.onend = () => {
    isRecording = false;
    micBtn.classList.remove("recording");
    micBtn.title = "🎤 Voice Input";
  };

  recognition.onerror = (e) => {
    isRecording = false;
    micBtn.classList.remove("recording");
    showToast("🎤 Error: " + e.error);
  };

  micBtn.addEventListener("click", () => {
    if (isRecording) {
      recognition.stop();
    } else {
      recognition.start();
    }
  });
}

// ─── 5. 💭 Smart Suggestions ─────────────────────────────────────────────────
function initSmartSuggestions() {
  const input = document.getElementById("question-input");
  if (!input) return;

  input.addEventListener("input", () => {
    clearTimeout(suggestionsTimer);
    const val = input.value.trim();
    if (val.length < 2) { hideSuggestions(); return; }
    suggestionsTimer = setTimeout(() => triggerSuggestions(val), 300);
  });

  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendQuestion();
    }
    if (e.key === "Escape") hideSuggestions();
  });

  // Click outside → hide suggestions
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#suggestions-box") && e.target !== input) {
      hideSuggestions();
    }
  });
}

function triggerSuggestions(text) {
  const lower    = text.toLowerCase();
  let   matched  = SUGGESTION_BANK.default;

  if (lower.match(/auth|key|token|login|oauth|bearer/))
    matched = SUGGESTION_BANK.auth;
  else if (lower.match(/error|fail|4\d\d|5\d\d|status|retry/))
    matched = SUGGESTION_BANK.error;
  else if (lower.match(/endpoint|route|url|path|api|resource/))
    matched = SUGGESTION_BANK.endpoint;
  else if (lower.match(/param|body|header|format|response|request/))
    matched = SUGGESTION_BANK.param;
  else if (lower.match(/limit|rate|quota|tier|free|plan/))
    matched = SUGGESTION_BANK.limit;
  else if (lower.match(/example|sample|curl|code|demo|show/))
    matched = SUGGESTION_BANK.example;

  // Filter: jo already type ho raha hai usse match kare
  const filtered = matched.filter(s => s.toLowerCase().includes(lower) || lower.length < 4);
  showSuggestions(filtered.slice(0, 4));
}

function showSuggestions(items) {
  let box = document.getElementById("suggestions-box");

  // Box exist nahi karta toh create karo
  if (!box) {
    box = document.createElement("div");
    box.id = "suggestions-box";
    box.style.cssText = `
      position: absolute; z-index: 999;
      background: #1e1e2e; border: 1px solid #3a3a5c;
      border-radius: 8px; box-shadow: 0 4px 16px rgba(0,0,0,0.4);
      max-width: 500px; overflow: hidden;
    `;
    const inputEl = document.getElementById("question-input");
    inputEl?.parentElement?.style?.setProperty("position", "relative");
    inputEl?.parentElement?.appendChild(box);
  }

  if (!items.length) { hideSuggestions(); return; }

  box.innerHTML = items.map(s => `
    <div class="suggestion-item"
         style="padding:10px 14px; cursor:pointer; color:#cdd6f4; font-size:13px;
                border-bottom:1px solid #2a2a40; transition:background 0.15s;"
         onmouseover="this.style.background='#2a2a50'"
         onmouseout="this.style.background='transparent'"
         onclick="applySuggestion(${JSON.stringify(s)})">
      💭 ${s}
    </div>
  `).join("");
  box.style.display = "block";
}

function hideSuggestions() {
  const box = document.getElementById("suggestions-box");
  if (box) box.style.display = "none";
}

function applySuggestion(text) {
  const input = document.getElementById("question-input");
  if (input) {
    input.value = text;
    input.focus();
  }
  hideSuggestions();
}

// ─── 6. 📤 Upload Form ────────────────────────────────────────────────────────
function initUploadForm() {
  const form = document.getElementById("upload-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const fileInput = document.getElementById("file-input");
    const apiInput  = document.getElementById("api-name-input");
    const statusEl  = document.getElementById("upload-status");

    if (!fileInput?.files?.[0]) { showToast("❗ File select karo"); return; }
    if (!apiInput?.value?.trim()) { showToast("❗ API name daalo"); return; }

    const formData = new FormData();
    formData.append("file",     fileInput.files[0]);
    formData.append("api_name", apiInput.value.trim());

    if (statusEl) statusEl.textContent = "⏳ Uploading...";
    try {
      const res  = await fetch("/api/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (res.ok) {
        showToast(`✅ ${data.chunks_stored} chunks stored!`);
        if (statusEl) statusEl.textContent = `✅ Done — ${data.chunks_stored} chunks`;
        loadApiList();
        form.reset();
      } else {
        if (statusEl) statusEl.textContent = `❌ ${data.detail}`;
        showToast("❌ Upload failed");
      }
    } catch (err) {
      if (statusEl) statusEl.textContent = "❌ Network error";
    }
  });
}

// ─── 7. 🔍 Auto Detect Name ──────────────────────────────────────────────────
function initAutoDetect() {
  const autoBtn   = document.getElementById("auto-detect-btn");
  const fileInput = document.getElementById("file-input");
  const apiInput  = document.getElementById("api-name-input");
  if (!autoBtn || !fileInput || !apiInput) return;

  autoBtn.addEventListener("click", async () => {
    if (!fileInput.files?.[0]) { showToast("❗ Pehle file choose karo"); return; }

    autoBtn.textContent = "🔍 Detecting...";
    autoBtn.disabled    = true;

    const fd = new FormData();
    fd.append("file", fileInput.files[0]);

    try {
      const res  = await fetch("/api/detect-name", { method: "POST", body: fd });
      const data = await res.json();
      if (res.ok && data.detected_name) {
        apiInput.value = data.detected_name;
        const sourceLabel = { spec: "spec file", heading: "heading", filename: "filename" };
        showToast(`✅ Naam mila: "${data.detected_name}" (${sourceLabel[data.source] || data.source})`);
      } else {
        showToast("⚠️ Naam detect nahi ho paya");
      }
    } catch (err) {
      showToast("❌ Auto detect failed");
    } finally {
      autoBtn.textContent = "🔍 Auto";
      autoBtn.disabled    = false;
    }
  });
}

// ─── 8. 🧪 API Tester ────────────────────────────────────────────────────────
function initTesterTab() {
  const testBtn = document.getElementById("run-test-btn");
  if (!testBtn) return;

  testBtn.addEventListener("click", async () => {
    const url     = document.getElementById("test-url")?.value?.trim();
    const method  = document.getElementById("test-method")?.value || "GET";
    const headersRaw = document.getElementById("test-headers")?.value?.trim();
    const body    = document.getElementById("test-body")?.value?.trim();
    const resultEl = document.getElementById("test-result");

    if (!url) { showToast("❗ URL daalo"); return; }

    let headers = {};
    if (headersRaw) {
      try { headers = JSON.parse(headersRaw); }
      catch { showToast("❗ Headers valid JSON mein daalo"); return; }
    }

    testBtn.textContent = "⏳ Testing...";
    testBtn.disabled    = true;
    if (resultEl) resultEl.textContent = "Sending request...";

    try {
      const res  = await fetch("/api/test", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ url, method, headers, body: body || null }),
      });
      const data = await res.json();

      if (resultEl) {
        const statusColor = data.success ? "#a6e3a1" : "#f38ba8";
        resultEl.innerHTML = `
          <div style="margin-bottom:8px">
            <span style="color:${statusColor}; font-weight:bold; font-size:15px">
              ${data.success ? "✅" : "❌"} ${data.status_code}
            </span>
            <span style="color:#888; margin-left:12px; font-size:12px">
              ${data.response_time_ms}ms
            </span>
          </div>
          <pre style="white-space:pre-wrap; word-break:break-all; color:#cdd6f4; font-size:12px">${
            JSON.stringify(data.body, null, 2)
          }</pre>
        `;
      }
    } catch (err) {
      if (resultEl) resultEl.textContent = "❌ Error: " + err.message;
    } finally {
      testBtn.textContent = "▶ Run";
      testBtn.disabled    = false;
    }
  });
}

// ─── 9. 📕 PDF Export ────────────────────────────────────────────────────────
function initPdfExport() {
  const exportBtn = document.getElementById("export-pdf-btn");
  if (!exportBtn) return;

  exportBtn.addEventListener("click", async () => {
    const apiName = document.getElementById("api-select")?.value;
    if (!apiName) { showToast("❗ Pehle API select karo"); return; }
    if (!chatHistory.length) { showToast("❗ Pehle kuch baat karo — history empty hai"); return; }

    exportBtn.textContent = "⏳ Exporting...";
    exportBtn.disabled    = true;

    try {
      const res = await fetch("/api/export-pdf", {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ api_name: apiName, messages: chatHistory }),
      });

      if (!res.ok) {
        const err = await res.json();
        showToast("❌ Export failed: " + err.detail);
        return;
      }

      // Blob ke roop mein download karo
      const blob      = await res.blob();
      const url       = URL.createObjectURL(blob);
      const anchor    = document.createElement("a");
      const filename  = res.headers.get("Content-Disposition")
        ?.match(/filename="?([^"]+)"?/)?.[1] || "chat_export.pdf";
      anchor.href     = url;
      anchor.download = filename;
      anchor.click();
      URL.revokeObjectURL(url);
      showToast("📕 PDF download ho raha hai!");

    } catch (err) {
      showToast("❌ Network error: " + err.message);
    } finally {
      exportBtn.textContent = "📕 Export PDF";
      exportBtn.disabled    = false;
    }
  });
}

// ─── Helpers ─────────────────────────────────────────────────────────────────

function pushToHistory(role, content) {
  chatHistory.push({
    role,
    content,
    timestamp: new Date().toLocaleString("en-IN", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    }),
  });
}

function updateTokenCount(tokens) {
  const el = document.getElementById("token-count");
  if (el && tokens) el.textContent = `Tokens used: ${tokens}`;
}

function setLoading(btn, isLoading) {
  if (!btn) return;
  btn.disabled     = isLoading;
  btn.textContent  = isLoading ? "⏳ Thinking..." : "Send ➤";
}

function showToast(message, duration = 3000) {
  let toast = document.getElementById("toast-msg");
  if (!toast) {
    toast = document.createElement("div");
    toast.id = "toast-msg";
    toast.style.cssText = `
      position:fixed; bottom:24px; right:24px; z-index:9999;
      background:#313244; color:#cdd6f4; padding:10px 18px;
      border-radius:8px; font-size:14px; box-shadow:0 4px 16px rgba(0,0,0,0.4);
      opacity:0; transition:opacity 0.25s; pointer-events:none;
    `;
    document.body.appendChild(toast);
  }
  toast.textContent = message;
  toast.style.opacity = "1";
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => { toast.style.opacity = "0"; }, duration);
}