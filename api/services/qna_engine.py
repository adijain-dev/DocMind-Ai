import re
import threading
from groq import Groq

try:
    from config import GROQ_API_KEY
    from services.vector_store import find_relevant_chunks
except ImportError:
    from ..config import GROQ_API_KEY
    from ..services.vector_store import find_relevant_chunks

MODEL      = "llama-3.3-70b-versatile"
MODEL_FAST = "llama-3.1-8b-instant"   # Fast model for simple questions


def get_groq_client():
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is not configured in .env file.")
    return Groq(api_key=GROQ_API_KEY)


# ─── Language Detection ───────────────────────────────────────────────────────
HINGLISH_RE = re.compile(
    r'\b(kya|kaise|kyun|mujhe|batao|karo|hai|hoga|chahiye|aur|nahi|matlab|'
    r'samjho|dena|krna|kr|bata|yeh|iska|uska|iske|uske|bhai|yaar|theek|'
    r'accha|pls|plz|hain|kar|mein|se|ke|ka|ki|ko|pe|par|ho|tha|thi|the|'
    r'jaise|waise|phir|pehle|baad|upar|neeche|seedha|likh|dikha|samjha)\b',
    re.IGNORECASE
)

# ─── Code Language Detection ─────────────────────────────────────────────────
CODE_LANG_RE = {
    'Python':     re.compile(r'\b(python|py|django|flask|fastapi|pandas|numpy)\b', re.IGNORECASE),
    'JavaScript': re.compile(r'\b(javascript|js|node|nodejs|react|vue|angular|typescript|ts|axios|fetch)\b', re.IGNORECASE),
    'Java':       re.compile(r'\b(java|spring|maven|gradle|springboot)\b', re.IGNORECASE),
    'Go':         re.compile(r'\b(golang|go lang)\b', re.IGNORECASE),
    'PHP':        re.compile(r'\b(php|laravel|wordpress)\b', re.IGNORECASE),
    'Ruby':       re.compile(r'\b(ruby|rails)\b', re.IGNORECASE),
    'Rust':       re.compile(r'\b(rust|cargo)\b', re.IGNORECASE),
    'C#':         re.compile(r'\b(c#|csharp|dotnet|\.net)\b', re.IGNORECASE),
    'cURL':       re.compile(r'\b(curl|bash|shell|terminal|command line)\b', re.IGNORECASE),
    'Swift':      re.compile(r'\b(swift|ios|xcode)\b', re.IGNORECASE),
    'Kotlin':     re.compile(r'\b(kotlin|android)\b', re.IGNORECASE),
}


def detect_language(text: str) -> str:
    """Detect if user is writing in Hinglish or English."""
    return 'hinglish' if HINGLISH_RE.search(text) else 'english'


def detect_code_language(text: str) -> str | None:
    """Detect if user wants code in a specific language. Returns None if not specified."""
    for lang, pattern in CODE_LANG_RE.items():
        if pattern.search(text):
            return lang
    return None


# ─── System Prompt Builder ────────────────────────────────────────────────────
def build_system_prompt(detected_lang: str, code_lang: str | None,
                        context_text: str, history: list) -> str:

    # Language instruction
    if detected_lang == 'hinglish':
        lang_instr = (
            "CRITICAL RULE — Language:\n"
            "User Hinglish mein likh raha hai (Hindi + English mix).\n"
            "Tum bhi Hinglish mein jawab do — bilkul naturally.\n"
            "Example: 'Authentication ke liye pehle API key generate karni hogi. "
            "Yeh kuch is tarah kaam karta hai:'\n"
            "KABHI pure English mein jawab mat dena jab user Hinglish mein pooche."
        )
    else:
        lang_instr = (
            "CRITICAL RULE — Language:\n"
            "Respond in clear, concise English only."
        )

    # Code instruction — VERY explicit
    if code_lang:
        code_instr = f"""ABSOLUTE MANDATORY RULE — CODE LANGUAGE:
THE USER WANTS **{code_lang.upper()}** CODE ONLY.
- Output ONLY {code_lang} code blocks
- DO NOT write Python if user asked Java
- DO NOT write JavaScript if user asked Python  
- DO NOT give multiple languages
- One working {code_lang} example is enough
- Start with ```{code_lang.lower()} and end with ```

EXAMPLE of correct behavior when user asks "Java mein dikhao":
```{code_lang.lower()}
// {code_lang} code here only
```
NOT other languages — ONLY {code_lang}."""
    else:
        code_instr = """CODE RULE:
- Only add code if question clearly needs it (how to call, example, etc.)
- If needed: give Python first, then JavaScript — skip Java unless asked
- Keep examples SHORT (10-15 lines max), working, copy-paste ready
- No code needed for: "what is X", "explain Y", "list endpoints" type questions"""

    # History context
    history_ctx = ""
    if history:
        history_ctx = "\n\nCONVERSATION HISTORY (for context):\n"
        for msg in history[-6:]:
            role = "User" if msg.get('role') == 'user' else "Assistant"
            content = msg.get('content', '')
            if len(content) > 300:
                content = content[:300] + "..."
            history_ctx += f"{role}: {content}\n\n"
        history_ctx += (
            "Use this history to:\n"
            "- Avoid repeating what was already explained\n"
            "- Build on previous answers if user asks follow-up\n"
            "- If user copies partial output and asks about it, refer to history\n"
        )

    return f"""You are an expert API documentation assistant — like a senior developer who explains things clearly.

{lang_instr}

{code_instr}

RESPONSE STYLE (follow this strictly):
1. Answer directly and concisely — no fluff
2. First sentence = direct answer to the question
3. Use bullet points for lists, not long paragraphs
4. Code blocks only when needed — keep them short and working
5. If follow-up question: build on previous answer, don't repeat basics
6. Max response length: enough to answer, not more

{history_ctx}

API DOCUMENTATION (use this as source of truth):
{context_text}"""


# ─── Main Functions ───────────────────────────────────────────────────────────

def generate_answer(question: str, api_name: str, conversation_history: list = None) -> dict:
    """
    Generate a complete answer (non-streaming).
    Supports: language detection, code language detection, conversation memory.
    """
    if conversation_history is None:
        conversation_history = []

    detected_lang = detect_language(question)
    code_lang     = detect_code_language(question)

    relevant_chunks = find_relevant_chunks(question, api_name, how_many=3)

    if not relevant_chunks:
        no_doc_msg = (
            "Is API ke liye koi documentation nahi mili. Pehle documentation upload karein."
            if detected_lang == 'hinglish'
            else "No documentation found for this API. Please upload documentation first."
        )
        return {
            "answer":        no_doc_msg,
            "sources_used":  [],
            "tokens_used":   0,
            "detected_lang": detected_lang,
            "code_lang":     code_lang,
        }

    context_text  = "\n\n---\n\n".join(relevant_chunks)
    system_prompt = build_system_prompt(detected_lang, code_lang, context_text, conversation_history)

    messages = [{"role": "system", "content": system_prompt}]
    for msg in conversation_history[-4:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": question})

    use_model = MODEL if code_lang else MODEL_FAST
    if len(question) > 80 or any(w in question.lower() for w in ['compare', 'explain', 'difference', 'how does']):
        use_model = MODEL

    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model=use_model,
            messages=messages,
            temperature=0.1,
            max_tokens=1024,
        )

        return {
            "answer":        response.choices[0].message.content,
            "sources_used":  relevant_chunks,
            "tokens_used":   response.usage.total_tokens if response.usage else 0,
            "detected_lang": detected_lang,
            "code_lang":     code_lang,
        }
    except Exception as e:
        return {
            "answer":        f"Error generating answer: {str(e)}",
            "sources_used":  relevant_chunks,
            "tokens_used":   0,
            "detected_lang": detected_lang,
            "code_lang":     code_lang,
        }


def stream_answer(question: str, api_name: str, conversation_history: list = None):
    """
    Real streaming generator from Groq.
    Yields text chunks as they arrive.
    """
    if conversation_history is None:
        conversation_history = []

    detected_lang = detect_language(question)
    code_lang     = detect_code_language(question)

    relevant_chunks = find_relevant_chunks(question, api_name, how_many=3)

    if not relevant_chunks:
        no_doc_msg = (
            "Is API ke liye koi documentation nahi mili. Pehle documentation upload karein."
            if detected_lang == 'hinglish'
            else "No documentation found for this API. Please upload documentation first."
        )
        yield no_doc_msg
        return

    context_text  = "\n\n---\n\n".join(relevant_chunks)
    system_prompt = build_system_prompt(detected_lang, code_lang, context_text, conversation_history)

    messages = [{"role": "system", "content": system_prompt}]
    for msg in conversation_history[-4:]:
        messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
    messages.append({"role": "user", "content": question})

    use_model = MODEL if code_lang else MODEL_FAST
    if len(question) > 80 or any(w in question.lower() for w in ['compare', 'explain', 'difference', 'how does']):
        use_model = MODEL

    try:
        client = get_groq_client()
        response = client.chat.completions.create(
            model=use_model,
            messages=messages,
            temperature=0.1,
            max_tokens=1024,
            stream=True,
        )

        for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content
    except Exception as e:
        yield f"Error in stream: {str(e)}"
