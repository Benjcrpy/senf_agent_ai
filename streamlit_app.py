import os
import json
import re
import requests
import streamlit as st
import streamlit.components.v1 as components

# ===== ENV from Coolify =====
OLLAMA_API_BASE = os.getenv("OLLAMA_API_BASE", "http://217.15.175.196:11434").rstrip("/")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:1b")

st.set_page_config(page_title="EvoAgentX · Ollama", page_icon="🤖", layout="wide")
st.title("EvoAgentX (Self-Evolving) • Ollama")
st.caption("Simple web UI powered by Streamlit + your Ollama server")

# ===== Sidebar =====
with st.sidebar:
    st.subheader("LLM Settings")
    api_base = st.text_input("Ollama Base URL", value=OLLAMA_API_BASE)
    model = st.text_input("Model", value=OLLAMA_MODEL)
    use_openai_v1 = st.checkbox("Use /v1 chat (OpenAI-compatible)", value=False)
    st.subheader("Generation")
    temperature = st.slider("Temperature", 0.0, 1.5, 0.7, 0.1)
    max_tokens = st.number_input("Max tokens", 128, 8192, 1000, 64)

# ===== Inputs =====
st.write("**Goal** (the agent will plan & iterate):")
goal = st.text_area("", placeholder="e.g., Create me a website todo app...", height=140)
mode = st.selectbox("Mode", ["Self-Evolving (3-pass)", "Single pass only"])
run = st.button("Run", type="primary", use_container_width=True)

# ===== Prompts =====
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

UI_SYSTEM = """You are a precise front-end engineer.
When asked to build a small website/app, output a single self-contained HTML document
with minimal CSS and vanilla JS. Keep it lightweight and responsive. Do not explain."""
UI_TASK = """Build a minimal **To-Do website** with:
- Add task, mark done/undo, delete task
- Persist to localStorage
- Clean modern styling
Output ONLY one fenced code block:

```html
<!-- full HTML here -->
<html>
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width,initial-scale=1" />
    <title>To-Do</title>
    <style>
      body{font-family:system-ui, sans-serif;max-width:720px;margin:40px auto;padding:0 16px}
      h1{margin:0 0 16px}
      .row{display:flex;gap:8px}
      input{flex:1;padding:10px;border:1px solid #ddd;border-radius:8px}
      button{padding:10px 14px;border:0;border-radius:8px;background:#111;color:#fff;cursor:pointer}
      ul{list-style:none;padding:0;margin:16px 0}
      li{display:flex;justify-content:space-between;align-items:center;padding:10px;border:1px solid #eee;border-radius:8px;margin-bottom:8px}
      li.done span{text-decoration:line-through;color:#777}
      .small{font-size:12px;color:#777}
    </style>
  </head>
  <body>
    <h1>To-Do</h1>
    <div class="row">
      <input id="task" placeholder="Add a task..." />
      <button onclick="add()">Add</button>
    </div>
    <ul id="list"></ul>
    <p class="small">Tasks are stored in your browser (localStorage).</p>
    <script>
      const key='todos-v1';
      const listEl=document.getElementById('list');
      const inputEl=document.getElementById('task');

      function load(){
        const data=JSON.parse(localStorage.getItem(key)||'[]');
        listEl.innerHTML='';
        data.forEach((t,i)=>render(t,i));
      }
      function save(){
        const items=[...listEl.querySelectorAll('li')].map(li=>({
          text: li.querySelector('span').textContent,
          done: li.classList.contains('done')
        }));
        localStorage.setItem(key, JSON.stringify(items));
      }
      function render(t,i){
        const li=document.createElement('li');
        if(t.done) li.classList.add('done');
        const span=document.createElement('span');
        span.textContent=t.text;
        const left=document.createElement('div');
        left.appendChild(span);
        const right=document.createElement('div');
        const btnDone=document.createElement('button');
        btnDone.textContent=t.done?'Undo':'Done';
        btnDone.onclick=()=>{ li.classList.toggle('done'); btnDone.textContent=li.classList.contains('done')?'Undo':'Done'; save(); };
        const btnDel=document.createElement('button');
        btnDel.textContent='Delete';
        btnDel.style.marginLeft='6px';
        btnDel.onclick=()=>{ li.remove(); save(); };
        right.appendChild(btnDone); right.appendChild(btnDel);
        li.appendChild(left); li.appendChild(right);
        listEl.appendChild(li);
      }
      function add(){
        const txt=inputEl.value.trim();
        if(!txt) return;
        render({text:txt,done:false});
        inputEl.value='';
        save();
      }
      // init
      const initial=JSON.parse(localStorage.getItem(key)||'[]');
      if(initial.length===0){ localStorage.setItem(key, JSON.stringify([])); }
      load();
    </script>
  </body>
</html>
"""

# ===== HTML extraction =====
CODE_RE = re.compile(r"html\s*(.+?)\s*", re.DOTALL | re.IGNORECASE)
def extract_html_from_text(text: str) -> str | None:
m = CODE_RE.search(text or "")
return m.group(1).strip() if m else None

def render_html_preview(text: str):
html = extract_html_from_text(text)
if html:
components.html(html, height=650, scrolling=True)
return True
return False

===== Ollama / OpenAI-compatible calls =====
def _ollama_generate(prompt: str) -> str:
url = f"{api_base}/api/generate"
payload = {
"model": model,
"prompt": prompt,
"stream": False,
"options": {"temperature": temperature, "num_predict": max_tokens},
}
r = requests.post(url, json=payload, timeout=180)
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
r = requests.post(url, json=payload, timeout=180)
r.raise_for_status()
data = r.json()
return data["choices"][0]["message"]["content"]

def gen(prompt: str) -> str:
return _openai_v1(prompt) if use_openai_v1 else _ollama_generate(prompt)

def self_evolving(goal_text: str):
draft = gen(SYSTEM + "\n\n" + TASK.format(goal=goal_text))
crit = gen(SYSTEM + "\n\n" + CRIT.format(plan=draft))
final = gen(SYSTEM + "\n\n" + REV.format(plan=draft, improvements=crit))
return draft, crit, final

===== Main logic =====
if run:
if not goal.strip():
st.warning("Enter a goal first.")
st.stop()

sql
Copy code
col_left, col_right = st.columns([3, 2])
want_ui = any(k in goal.lower() for k in [
    "website", "web app", "todo app", "to-do app", "landing page", "frontend", "html"
])

if want_ui:
    with st.status("Generating website…", expanded=True) as s:
        html_text = gen(UI_SYSTEM + "\n\n" + UI_TASK)
        s.update(label="Done!", state="complete")

    with col_left:
        st.subheader("Raw HTML Output")
        st.code(html_text, language="html")

    with col_right:
        st.subheader("Live Preview")
        if not render_html_preview(html_text):
            st.info("No HTML block detected. Try again or lower temperature.")

else:
    if mode.startswith("Self-Evolving"):
        with st.status("Running self-evolving agent…", expanded=True) as s:
            draft, crit, final = self_evolving(goal.strip())
            s.update(label="Done!", state="complete")

        with col_left:
            st.subheader("✅ Final Plan")
            st.markdown(final)
            tab1, tab2 = st.tabs(["📝 Draft", "🔍 Critique"])
            with tab1:
                st.markdown(draft)
            with tab2:
                st.markdown(crit)

        with col_right:
            st.subheader("Preview")
            render_html_preview(final)

    else:
        with st.status("Running single pass…", expanded=True) as s:
            out = gen(SYSTEM + "\n\n" + TASK.format(goal=goal.strip()))
            s.update(label="Done!", state="complete")

        with col_left:
            st.subheader("✅ Output")
            st.markdown(out)

        with col_right:
            st.subheader("Preview")
            render_html_preview(out)
