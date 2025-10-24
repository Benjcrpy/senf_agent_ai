import os, json, requests, textwrap
import streamlit as st

# ---- ENV defaults (override via Coolify env) ----
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://217.15.175.196:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")

st.set_page_config(page_title="EvoAgentX · Ollama", page_icon="🤖", layout="centered")

st.title("EvoAgentX (Self-Evolving) · Ollama")
st.caption("Simple web UI powered by Streamlit + your Ollama server")

with st.sidebar:
    st.subheader("LLM Settings")
    api_base = st.text_input("Ollama Base URL", value=OLLAMA_API_BASE, help="No /v1 for direct Ollama")
    model = st.text_input("Model", value=OLLAMA_MODEL, help="e.g. llama3.2:1b")
    use_openai_v1 = st.checkbox("Use /v1 chat (OpenAI-compatible)", value=False,
                                help="Tick only if your proxy expects /v1/chat/completions")

    st.subheader("Generation")
    temperature = st.slider("Temperature", 0.0, 1.5, 0.7, 0.1)
    max_tokens = st.number_input("Max tokens", 128, 8192, 1000, 64)

st.write("**Goal** (the agent will plan & iterate):")
goal = st.text_area(" ", placeholder="e.g., Make a 2-day Cebu food crawl under ₱1500...", height=140)

col1, col2 = st.columns(2)
run_mode = col1.selectbox("Mode", ["Self-Evolving (3-pass)", "Single pass only"])
submit = col2.button("Run", type="primary", use_container_width=True)

# ---- Prompts (same structure as your FastAPI fallback) ----
FALLBACK_SYSTEM = """You are a senior product/engineering planner.
Produce crisp, concrete, English outputs. Avoid fluff. Use lists and short sentences."""
FALLBACK_TASK = """Goal: {goal}

Produce a clear plan for a SIMPLE Todo List app.

Sections:
1) Core Features (3-6 bullets)
2) Entities / Data Model (3-6 bullets)
3) Tech Stack (FE/BE/DB)
4) Milestones by Day (Day 1..N)

Output ONLY the plan, no preface.
"""
FALLBACK_CRITIQUE = """You are reviewing the plan below. Find gaps and concrete improvements.
- Are features minimal but sufficient?
- Are entity fields precise?
- Are tech choices realistic for a weekend build?
- Are milestones granular Day 1..N?

Return a concise bullet list of improvements ONLY.

--- PLAN START ---
{plan}
--- PLAN END ---
"""
FALLBACK_REVISE = """Rewrite the plan applying ALL improvements below. Keep the same 4 sections and formatting.

--- ORIGINAL PLAN ---
{plan}

--- IMPROVEMENTS ---
{improvements}
"""

def ollama_generate_raw(prompt: str) -> str:
    url = f"{api_base}/api/generate"
    payload = {"model": model, "prompt": prompt, "stream": False, "options": {
        "temperature": temperature, "num_predict": max_tokens
    }}
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data.get("response") or json.dumps(data)

def openai_v1_chat(prompt: str) -> str:
    url = f"{api_base}/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }
    r = requests.post(url, json=payload, timeout=120)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"]

def generate(prompt: str) -> str:
    if use_openai_v1:
        return openai_v1_chat(prompt)
    return ollama_generate_raw(prompt)

def self_evolving(goal_text: str) -> dict:
    draft = generate(FALLBACK_SYSTEM + "\n\n" + FALLBACK_TASK.format(goal=goal_text))
    critique = generate(FALLBACK_SYSTEM + "\n\n" + FALLBACK_CRITIQUE.format(plan=draft))
    final = generate(FALLBACK_SYSTEM + "\n\n" + FALLBACK_REVISE.format(plan=draft, improvements=critique))
    return {"draft": draft, "critique": critique, "final": final}

if submit:
    if not goal.strip():
        st.warning("Type a goal first.")
        st.stop()
    with st.status("Running…", expanded=True) as status:
        if run_mode.startswith("Self-Evolving"):
            status.update(label="Pass 1: Drafting…")
            res = self_evolving(goal.strip())
            st.subheader("Final Plan")
            st.markdown(res["final"])
            with st.expander("See draft and critique"):
                st.markdown("**Draft**")
                st.markdown(res["draft"])
                st.markdown("**Critique**")
                st.markdown(res["critique"])
            status.update(label="Done!", state="complete")
        else:
            status.update(label="Single pass…")
            out = generate(FALLBACK_SYSTEM + "\n\n" + FALLBACK_TASK.format(goal=goal.strip()))
            st.subheader("Output")
            st.markdown(out)
            status.update(label="Done!", state="complete")

st.markdown("---")
st.caption("Tip: If your gateway exposes /v1 (OpenAI-compatible), toggle **Use /v1 chat** in the sidebar.")
