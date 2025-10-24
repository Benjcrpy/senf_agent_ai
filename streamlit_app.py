import os, json, requests, streamlit as st

# ----- ENV from Coolify -----
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://217.15.175.196:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")

st.set_page_config(page_title="EvoAgentX · Ollama", page_icon="🤖", layout="wide")
st.title("EvoAgentX (Self-Evolving) • Ollama")
st.caption("Simple web UI powered by Streamlit + your Ollama server")

with st.sidebar:
    st.subheader("LLM Settings")
    api_base = st.text_input("Ollama Base URL", value=OLLAMA_API_BASE, help="No /v1 for direct Ollama")
    model = st.text_input("Model", value=OLLAMA_MODEL, help="e.g. llama3.2:1b")
    use_openai_v1 = st.checkbox("Use /v1 chat (OpenAI-compatible)", value=False)
    st.subheader("Generation")
    temperature = st.slider("Temperature", 0.0, 1.5, 0.7, 0.1)
    max_tokens = st.number_input("Max tokens", 128, 8192, 1000, 64)

st.write("**Goal** (the agent will plan & iterate):")
goal = st.text_area("", placeholder="e.g., Make a 2-day Cebu food crawl under ₱1500...", height=140)
mode = st.selectbox("Mode", ["Self-Evolving (3-pass)", "Single pass only"])
run = st.button("Run", type="primary", use_container_width=True)

# ---- Prompts ----
SYSTEM = """You are a senior product/engineering planner.
Produce crisp, concrete, English outputs. Avoid fluff. Use lists and short sentences."""
TASK = """Goal: {goal}

Produce a clear plan for a SIMPLE Todo List app.

Sections:
1) Core Features (3-6 bullets)
2) Entities / Data Model (3-6 bullets)
3) Tech Stack (FE/BE/DB)
4) Milestones by Day (Day 1..N)

Output ONLY the plan, no preface.
"""
CRIT = """You are reviewing the plan below. Find gaps and concrete improvements.
Return a concise bullet list of improvements ONLY.

--- PLAN START ---
{plan}
--- PLAN END ---
"""
REV = """Rewrite the plan applying ALL improvements below. Keep the same 4 sections and formatting.

--- ORIGINAL PLAN ---
{plan}

--- IMPROVEMENTS ---
{improvements}
"""

def _ollama_generate(prompt: str) -> str:
    url = f"{api_base}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False, "options": {
        "temperature": temperature, "num_predict": max_tokens
    }}
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data.get("response") or json.dumps(data)

def _openai_v1(prompt: str) -> str:
    url = f"{api_base}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]

def gen(prompt: str) -> str:
    return _openai_v1(prompt) if use_openai_v1 else _ollama_generate(prompt)

def self_evolving(goal_text: str):
    draft = gen(SYSTEM + "\n\n" + TASK.format(goal=goal_text))
    crit  = gen(SYSTEM + "\n\n" + CRIT.format(plan=draft))
    final = gen(SYSTEM + "\n\n" + REV.format(plan=draft, improvements=crit))
    return draft, crit, final

if run:
    if not goal.strip():
        st.warning("Enter a goal first.")
        st.stop()

    if mode.startswith("Self-Evolving"):
        with st.status("Running self-evolving agent…", expanded=True) as s:
            draft, crit, final = self_evolving(goal.strip())
            s.update(label="Done!", state="complete")
        # Render outside the status (fixes nesting bug)
        st.subheader("✅ Final Plan")
        st.markdown(final)
        tab1, tab2 = st.tabs(["📝 Draft", "🔍 Critique"])
        with tab1: st.markdown(draft)
        with tab2: st.markdown(crit)
    else:
        with st.status("Running single pass…", expanded=True) as s:
            out = gen(SYSTEM + "\n\n" + TASK.format(goal=goal.strip()))
            s.update(label="Done!", state="complete")
        st.subheader("✅ Output")
        st.markdown(out)
