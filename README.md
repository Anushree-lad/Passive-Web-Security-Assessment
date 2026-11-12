# Assistant Hub

A local FastAPI skeleton matching your sidebar sketch:

```
💻 Project Assistant   🛡 Cyber Assistant   📄 Assignment Assistant
🧠 Research Assistant  📚 Study Assistant   🐍 Python Assistant
🌐 Web Dev Assistant   🗄 SQL Assistant     📊 Data Analysis Assistant
📁 Project Memory      ⚙ Settings
```

## Run it

```bash
cd assistant-hub
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open **http://127.0.0.1:8000** — it redirects to Project Assistant.

## How it's structured

```
assistant-hub/
├── main.py               # FastAPI app: SECTIONS list drives the whole sidebar
├── requirements.txt
├── templates/
│   ├── base.html         # sidebar + layout shell (Jinja2)
│   └── page.html         # per-section content (chat shell, or skills list for Settings)
└── static/
    ├── style.css          # dark, monospace, IDE-inspired theme
    └── script.js          # stub chat behaviour — no backend wired up yet
```

Every sidebar item is one entry in the `SECTIONS` list in `main.py`. Add,
remove, rename, or reorder assistants by editing that list — the sidebar,
routes (`/assistant/<key>`), and page titles all follow automatically.

## Where to plug in real logic

Right now every assistant page (except Settings) renders an empty chat shell
that just echoes a stub reply — see the comment block at the top of
`static/script.js`. To make a section actually do something:

1. Add a route in `main.py`, e.g.:
   ```python
   @app.post("/assistant/{key}/message")
   def handle_message(key: str, payload: dict):
       text = payload["text"]
       # call Ollama, a script, a DB query, whatever this assistant needs
       return {"reply": "..."}
   ```
2. Replace the `setTimeout` stub in `script.js` with a `fetch()` call to that route.
3. If a section needs its own layout instead of the generic chat shell (e.g.
   Data Analysis Assistant showing a table, or Project Memory showing saved
   notes), give it a dedicated template and branch on `active.key` in
   `page.html`, the same way Settings already branches to show the skill list.

## Settings page

`SKILLS` in `main.py` mirrors the checklist you shared (Python, SQL, HTML,
CSS, JavaScript, FastAPI, Git & GitHub, AI). Edit that list to update status
as you progress — no template changes needed.
