import random
import json
import os
import streamlit as st
from openai import OpenAI

# ── Constants ─────────────────────────────────────────────────────────────────

SUBJECTS = [
    "Anatomy", "Physiology", "Biochemistry", "Pathology", "Pharmacology",
    "Microbiology", "Medicine", "Surgery", "OBG", "Pediatrics",
    "Psychiatry", "Dermatology", "ENT", "Ophthalmology", "Forensic Medicine",
    "Orthopedics", "Radiology", "Anesthesia", "PSM"
]

QUESTIONS_PER_SESSION = 30
SUBJECTS_PER_SESSION  = 15
PROGRESS_FILE = "medmavericks_progress.json"

# ── Groq client configuration ──────────────────────────────────────────────────

client = OpenAI(
    api_key=st.secrets["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1"
)

MODEL_NAME = "llama-3.1-8b-instant" 

# ── Progress helpers ──────────────────────────────────────────────────────────

def load_progress() -> dict:
    if os.path.exists(PROGRESS_FILE):
        try:
            with open(PROGRESS_FILE, "r") as f:
                return json.load(f)
        except:
            return {"used_questions": [], "all_time_score": 0, "best_streak": 0}
    return {"used_questions": [], "all_time_score": 0, "best_streak": 0}

def save_progress(data: dict):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=2)

def reset_progress():
    if os.path.exists(PROGRESS_FILE):
        try:
            os.remove(PROGRESS_FILE)
        except:
            pass

# ── AI question generator (Groq Version) ──────────────────────────────────────

def generate_questions(used_stems: list) -> list:
    chosen_subjects = random.sample(SUBJECTS, SUBJECTS_PER_SESSION)

    avoid_block = ""
    if used_stems:
        recent = used_stems[-40:]
        avoid_block = "\n\nAvoid these specific topics: " + ", ".join(recent)

    # Groq needs a prompt that explicitly asks for a JSON object with a key
    prompt = f"""You are a NEET PG high-yield question generator for Indian medical students.
Generate exactly {QUESTIONS_PER_SESSION} MCQs (2 per subject) for these subjects: {', '.join(chosen_subjects)}.

Return a JSON object with a single key "questions" containing an array of objects. 
Each object must have these exact keys:
"q" (the question stem), 
"a" (the correct answer string), 
"ops" (a list of 4 answer strings), 
"cat" (the subject name), 
"fact" (a 1-2 sentence high-yield memory tip).

Rules:
1. "a" must match one of the entries in "ops" exactly.
2. Ensure high-yield clinical relevance for NEET PG 2026.{avoid_block}"""

    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        response_format={"type": "json_object"} 
    )
    
    raw = response.choices[0].message.content.strip()

    try:
        data = json.loads(raw)
        
        # Robustly extract the list
        if isinstance(data, dict) and "questions" in data:
            questions = data["questions"]
        elif isinstance(data, list):
            questions = data
        else:
            questions = list(data.values())[0]

        # Shuffle options inside each question
        for q in questions:
            if "ops" in q:
                random.shuffle(q["ops"])

        random.shuffle(questions)
        return questions

    except Exception as e:
        raise ValueError(f"AI Response Format Error. Please retry. (Details: {str(e)})")

# ── Session & UI Logic ────────────────────────────────────────────────────────

def init_session():
    progress = load_progress()
    st.session_state.used_questions  = progress.get("used_questions", [])
    st.session_state.all_time_score  = progress.get("all_time_score", 0)
    st.session_state.best_streak     = progress.get("best_streak", 0)
    st.session_state.score           = 0
    st.session_state.streak          = 0
    st.session_state.q_index         = 0
    st.session_state.answered        = False
    st.session_state.chosen          = None
    st.session_state.session_done    = False
    st.session_state.error           = None
    # Add a session_id to keep button keys unique across sessions
    st.session_state.session_id      = random.randint(1000, 9999)

    with st.spinner("🔬 Scanning medical database for NEET PG 2026 yield patterns..."):
        try:
            questions = generate_questions(st.session_state.used_questions)
            st.session_state.questions = questions
            st.session_state.used_questions.extend([q["q"] for q in questions])
            _persist()
        except Exception as e:
            st.session_state.error = str(e)
            st.session_state.questions = []

    st.session_state.initialized = True

def _persist():
    save_progress({
        "used_questions": st.session_state.used_questions,
        "all_time_score": st.session_state.all_time_score,
        "best_streak":    st.session_state.best_streak,
    })

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(page_title="MedMavericks", page_icon="🏥", layout="centered")

st.markdown("""
<style>
div[data-testid="stButton"] button {
    width: 100%;
    text-align: left;
    border-radius: 8px;
    padding: 0.55rem 0.9rem;
    font-size: 0.93rem;
}
div[data-testid="stMetric"] {
    background: #f8f9fa;
    border-radius: 10px;
    padding: 0.5rem 0.75rem;
}
</style>
""", unsafe_allow_html=True)

# ── Bootstrap ─────────────────────────────────────────────────────────────────

if "initialized" not in st.session_state:
    init_session()

# ── Error screen ──────────────────────────────────────────────────────────────

if st.session_state.get("error"):
    st.title("🏥 MedMavericks")
    st.error(f"**Failed to generate questions:** {st.session_state.error}")
    st.info("Check your `GROQ_API_KEY` in Streamlit Secrets. If the error persists, the AI might have sent malformed data—try retrying.")
    if st.button("🔄 Retry"):
        for k in list(st.session_state.keys()):
            del st.session_state[k]
        st.rerun()
    st.stop()

questions = st.session_state.questions

# ── Session-complete screen ───────────────────────────────────────────────────

if st.session_state.session_done:
    st.title("🏥 MedMavericks")
    total = len(questions)
    score = st.session_state.score
    pct   = round(score / total * 100) if total else 0
    medal = "🏆" if pct >= 80 else ("👏" if pct >= 60 else "📖")

    st.markdown(f"## {medal} Session Complete!")
    col1, col2, col3 = st.columns(3)
    col1.metric("Session score",  f"{score}/{total}")
    col2.metric("Accuracy",       f"{pct}%")
    col3.metric("All-time score", st.session_state.all_time_score)

    st.divider()
    st.markdown(f"**Best streak ever:** {st.session_state.best_streak} 🔥")
    st.markdown(f"**Total questions seen:** {len(st.session_state.used_questions)}")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("▶️  Next 30 questions"):
            for k in ["questions", "q_index", "answered", "chosen", "session_done", "score", "streak", "initialized", "error"]:
                st.session_state.pop(k, None)
            st.rerun()
    with col_b:
        if st.button("🔁  Reset all progress"):
            reset_progress()
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()
    st.stop()

# ── Quiz UI ───────────────────────────────────────────────────────────────────

st.title("🏥 MedMavericks")
st.caption("Prescribing yourself a daily dose of discipline")

col1, col2, col3 = st.columns(3)
col1.metric("Score",        st.session_state.score)
col2.metric("Streak 🔥",    st.session_state.streak)
col3.metric("Best streak",  st.session_state.best_streak)

q_index = st.session_state.q_index
total   = len(questions)
st.progress((q_index) / total)
st.caption(f"Question {q_index + 1} of {total}")

st.divider()

if questions:
    q    = questions[q_index]
    opts = q["ops"]
    sid  = st.session_state.session_id

    st.markdown(f"`{q['cat']}`")
    st.subheader(q["q"])

    if not st.session_state.answered:
        for opt in opts:
            if st.button(opt, key=f"btn_{sid}_{q_index}_{opt}"):
                st.session_state.answered = True
                st.session_state.chosen   = opt

                if opt == q["a"]:
                    st.session_state.score          += 1
                    st.session_state.all_time_score += 1
                    st.session_state.streak         += 1
                    if st.session_state.streak > st.session_state.best_streak:
                        st.session_state.best_streak = st.session_state.streak
                else:
                    st.session_state.streak = 0

                _persist()
                st.rerun()
    else:
        for opt in opts:
            if opt == q["a"]:
                st.success(f"✓  {opt}")
            elif opt == st.session_state.chosen:
                st.error(f"✗  {opt}")
            else:
                st.button(opt, key=f"dis_{sid}_{q_index}_{opt}", disabled=True)

        if st.session_state.chosen == q["a"]:
            st.success("✅ Correct!")
        else:
            st.error(f"❌ Wrong — correct answer: **{q['a']}**")

        st.info(f"💡 **Remember:** {q['fact']}")
        st.divider()

        if st.button("Next Question →"):
            if q_index + 1 >= total:
                st.session_state.session_done = True
            else:
                st.session_state.q_index  += 1
                st.session_state.answered  = False
                st.session_state.chosen    = None
            st.rerun()
