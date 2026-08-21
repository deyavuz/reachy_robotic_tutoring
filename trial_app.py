"""Local trial app for the Reachy Bayes study.

Runs on the same machine as the conversation app so it can share state
directly — no API, no tunnel.

    python trial_app.py

Participant screen:  http://127.0.0.1:5001
Operator panel:      http://127.0.0.1:5001/admin      (keep this on your own screen)
"""

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "src", "reachy_mini_conversation_app", "tools"))

from questionnaires import PRE_ITEMS, POST_SECTIONS, POST_OPEN

from flask import Flask, request, redirect, url_for, render_template_string  # noqa: E402

from bayes_algorithm import (
    new_state, load_state, save_state, clear_state, open_question,
    update_mastery, undo_last, archive_session,
    PRACTICE, open_practice, end_practice,
    question_bank, question_order, kc_order, save_questionnaire, STATE_PATH,
    ZPD_LOW, ZPD_HIGH, PREREQ_THRESHOLD, N_RANDOM_MISTAKES,
)

try:
    from recorder import SessionRecorder, BACKEND as AUDIO_BACKEND
except Exception:
    SessionRecorder, AUDIO_BACKEND = None, None

PORT = 5001                      # 5000 is AirPlay on macOS
ADMIN_TOKEN = "finduk1709" 
SECONDS_PER_QUESTION = 480      # 8 minutes
SOFT_WARNING_AT = 450           # warn at 7:30

app = Flask(__name__)
_recorder = None

BASE = """
<!doctype html><meta charset="utf-8"><title>{{ t }}</title>
<style>
 body{font-family:-apple-system,system-ui,sans-serif;max-width:42rem;margin:4rem auto;
      padding:0 1.5rem;line-height:1.6;color:#18181b}
 .q{font-size:1.2rem;background:#f4f4f5;padding:1.5rem 1.75rem;border-radius:8px;
    margin:2rem 0;white-space:pre-line;line-height:1.7}
 button{font-size:1rem;padding:.75rem 1.5rem;border-radius:6px;border:1px solid #18181b;
        background:#18181b;color:#fff;cursor:pointer;margin:0 .5rem .5rem 0}
 button.ghost{background:#fff;color:#18181b}
 button.warn{background:#fff;color:#b91c1c;border-color:#b91c1c}
 #timer{font-size:3rem;font-variant-numeric:tabular-nums;margin:2rem 0}
 #timer.warn{color:#b45309}
 .muted{color:#71717a;font-size:.9rem}
 input,select{font-size:1rem;padding:.5rem}
 table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.9rem}
 th,td{text-align:left;padding:.4rem .6rem;border-bottom:1px solid #e4e4e7}
 .bar{display:inline-block;height:.7rem;background:#18181b;border-radius:2px;
      vertical-align:middle}
 .zpd{background:#16a34a} .low{background:#a1a1aa} .high{background:#3b82f6}
 code{background:#f4f4f5;padding:.1rem .3rem;border-radius:3px}
</style>
{{ body|safe }}
"""


def page(body, title="Study", **kw):
    return render_template_string(BASE, t=title,
                                  body=render_template_string(body, **kw))


def state_or_none():
    try:
        return load_state()
    except FileNotFoundError:
        return None

def admin_ok():
    return request.args.get("key") == ADMIN_TOKEN
# ------------------------------------------------------------- participant

@app.route("/", methods=["GET", "POST"])
def start():
    global _recorder
    if request.method == "POST":
        pid = request.form["pid"].strip()
        state = new_state(pid, request.form["condition"])

        if SessionRecorder is not None:
            _recorder = SessionRecorder(pid)
            path = _recorder.start()
            if path:
                state["audio_path"] = path
                state["audio_started_at"] = _recorder.started_at
                save_state(state)
        return redirect(url_for("pre_questionnaire"))

    existing = state_or_none()
    return page("""
      <h1>Session setup</h1>
      {% if existing %}
        <p class="muted">Unfinished session for <b>{{ existing.participant_id }}</b>
        ({{ existing.index }} of {{ total }} done). Its data is already saved to
        <code>data/{{ existing.participant_id }}/</code>. Starting a new session
        discards the live state but keeps that data.</p>
      {% endif %}
      <form method="post">
        <p><label>Participant ID<br><input name="pid" required autofocus></label></p>
        <p><label>Condition<br>
          <select name="condition">
            <option value="zpd">zpd</option>
            <option value="random">random</option>
          </select></label></p>
        <p><button type="submit">Begin</button></p>
      </form>
      <p class="muted">Audio backend: {{ audio or 'NONE — use a phone' }} ·
      Restart the conversation app before each participant.</p>
    """, title="Setup", existing=existing, total=len(question_order),
         audio=AUDIO_BACKEND)


@app.route("/practice")
def practice():
    state = state_or_none()
    if state is None:
        return redirect(url_for("start"))
    if state.get("practice_done"):
        return redirect(url_for("progress"))
    return page("""
      <p class="muted">Practice</p>
      <h1>Let's try one together first</h1>
      <p>This one doesn't count — it's just so you can see how it works. Say
      "practice question" out loud, then read the question and the options to
      the robot. The robot will answer, and you can talk it through together.</p>
      <div class="q">{{ text }}</div>
      <form method="post" action="{{ url_for('practice_begin') }}">
        <button type="submit">I'm ready to start the conversation</button>
      </form>
    """, title="Practice", text=PRACTICE["text"])


@app.route("/practice/begin", methods=["POST"])
def practice_begin():
    open_practice(load_state())
    return redirect(url_for("practice_timer"))


@app.route("/practice/timer")
def practice_timer():
    return page("""
      <p class="muted">Practice</p>
      <div class="q">{{ text }}</div>
      <p class="muted">Take as long as you like — there's no timer on this one.</p>
      <form method="post" action="{{ url_for('practice_judge') }}">
        <button type="submit" class="ghost">I'm done</button>
      </form>
    """, title="Practice", text=PRACTICE["text"])


@app.route("/practice/judge", methods=["GET", "POST"])
def practice_judge():
    return page("""
      <h1>Was the robot's answer correct?</h1>
      <p class="muted">You'll be asked this after every question.</p>
      <form method="post" action="{{ url_for('practice_done') }}">
        <button name="response" value="correct">Yes</button>
        <button name="response" value="wrong">No</button>
        <button name="response" value="dontknow" class="ghost">I don't know</button>
      </form>
    """, title="Practice")


@app.route("/practice/done", methods=["POST"])
def practice_done():
    end_practice(load_state())
    return page("""
      <h1>That's the idea</h1>
      <p>The robot got that one wrong — it treated red and blue as equally likely,
      but there are three red balls and only one blue.</p>
      <p>From here on the questions count, and you'll have two minutes each.</p>
      <form method="post" action="{{ url_for('progress') }}">
        <button type="submit">Start</button>
      </form>
    """, title="Practice")

@app.route("/progress", methods=["GET", "POST"])
def progress():
    global _recorder
    state = state_or_none()
    if state is None:
        return redirect(url_for("start"))

    if state["index"] >= len(question_order):
        return redirect(url_for("post_questionnaire"))

    return page("""
      <p class="muted">Question {{ n }} of {{ total }}</p>
      <h1>Ready for the next question?</h1>
      <form method="post" action="{{ url_for('show') }}">
        <button type="submit">Show me question {{ n }}</button>
      </form>
    """, n=state["index"] + 1, total=len(question_order))


@app.route("/show", methods=["POST"])
def show():
    state = load_state()
    qid = question_order[state["index"]]
    return page("""
      <p class="muted">Question {{ n }} of {{ total }}</p>
      <div class="q">{{ text }}</div>
      <p>Say the question number out loud, then read the question to the robot.</p>
      <form method="post" action="{{ url_for('begin') }}">
        <button type="submit">I'm ready to start the conversation</button>
      </form>
    """, n=state["index"] + 1, total=len(question_order),
         text=question_bank[qid]["text"] or f"[{qid}: question text not yet entered]")


@app.route("/begin", methods=["POST"])
def begin():
    state = load_state()
    open_question(state, question_order[state["index"]])
    return redirect(url_for("timer"))


@app.route("/timer")
def timer():
    state = load_state()
    if state.get("current") is None:
        return redirect(url_for("progress"))
    qid = state["current"]["id"]
    return page("""
      <p class="muted">Question {{ n }} of {{ total }}</p>
      <div class="q">{{ text }}</div>
      <div id="timer">8:00</div>
      <p id="note" class="muted">Talk it through with the robot.</p>
      <form method="post" action="{{ url_for('judge') }}">
        <button type="submit" class="ghost">I'm done</button>
      </form>
      <script>
        let left = {{ secs }};
        const el = document.getElementById('timer'), note = document.getElementById('note');
        const tick = setInterval(() => {
          left--;
          el.textContent = Math.floor(left/60) + ':' + String(left%60).padStart(2,'0');
          if (left === {{ secs }} - {{ warn }}) {
            el.classList.add('warn');
            note.textContent = "About fifteen seconds left — finish your thought.";
          }
          if (left <= 0) { clearInterval(tick); window.location = "{{ url_for('judge') }}"; }
        }, 1000);
      </script>
    """, n=state["index"] + 1, total=len(question_order),
         text=question_bank[qid]["text"] or f"[{qid}]",
         secs=SECONDS_PER_QUESTION, warn=SOFT_WARNING_AT)


@app.route("/judge", methods=["GET", "POST"])
def judge():
    return page("""
      <h1>Was the robot's answer correct?</h1>
      <form method="post" action="{{ url_for('record') }}">
        <button name="response" value="correct">Yes</button>
        <button name="response" value="wrong">No</button>
        <button name="response" value="dontknow" class="ghost">I don't know</button>
      </form>
    """, title="Judgement")


@app.route("/record", methods=["POST"])
def record():
    state = load_state()
    if state.get("current") is None:
        return redirect(url_for("progress"))
    kc, before, after = update_mastery(state, request.form["response"])
    archive_session(state, move_audio=False)
    app.logger.info("%s: %s %.2f -> %.2f", state["participant_id"], kc, before, after)
    return redirect(url_for("progress"))

# ============================================================
# QUESTIONNAIRE ROUTES
# ============================================================

def _radio(key, options):
    opts = "".join(
        f'<label style="display:block;margin:.3rem 0;font-weight:normal">'
        f'<input type="radio" name="{key}" value="{o}" required> {o}</label>'
        for o in options)
    return opts

def _scale5(key):
    cells = "".join(
        f'<label style="display:inline-block;text-align:center;margin:0 .4rem">'
        f'<input type="radio" name="{key}" value="{n}" required><br>'
        f'<span class="muted">{n}</span></label>'
        for n in range(1, 6))
    return cells


@app.route("/pre", methods=["GET", "POST"])
def pre_questionnaire():
    state = state_or_none()
    if state is None:
        return redirect(url_for("start"))

    if request.method == "POST":
        answers = {k: request.form.get(k, "") for k, *_ in PRE_ITEMS}
        save_questionnaire(state, "pre", answers)
        return redirect(url_for("practice"))

    rows = []
    for key, prompt, kind, options in PRE_ITEMS:
        if kind == "radio":
            field = _radio(key, options)
        elif kind == "number":
            field = f'<input name="{key}" required style="width:8rem">'
        else:  # text
            field = f'<textarea name="{key}" rows="3" style="width:100%"></textarea>'
        rows.append(f'<div style="margin:1.5rem 0"><p><b>{prompt}</b></p>{field}</div>')

    return page("""
      <h1>Before we begin</h1>
      <p class="muted">A few quick questions about your background. You can pick
      "Prefer not to say" where offered.</p>
      <form method="post">
        {{ content|safe }}
        <p><button type="submit">Continue</button></p>
      </form>
    """, title="Pre-task", content="".join(rows))


@app.route("/post", methods=["GET", "POST"])
def post_questionnaire():
    state = state_or_none()
    if state is None:
        return redirect(url_for("start"))

    if request.method == "POST":
        answers = {}
        for _, _, items in POST_SECTIONS:
            for key, _stmt in items:
                answers[key] = request.form.get(key, "")
        for key, _prompt, kind in POST_OPEN:
            answers[key] = request.form.get(key, "")
            if kind == "yesno_text":
                answers[key + "_detail"] = request.form.get(key + "_detail", "")
        save_questionnaire(state, "post", answers)

        # finalise: archive everything and clear the live session
        global _recorder
        if _recorder is not None:
            _recorder.stop()
            _recorder = None
            state = load_state()
        folder = archive_session(state)
        clear_state()
        return page("""
          <h1>All done</h1>
          <p>Thank you so much — that's the end of the session.</p>
          <p class="muted">Saved to <code>{{ folder }}</code></p>
        """, title="Done", folder=folder)

    parts = []
    for title, scale_note, items in POST_SECTIONS:
        parts.append(f'<h3 style="margin-top:2rem">{title}</h3>'
                     f'<p class="muted">{scale_note}</p>')
        for key, stmt in items:
            parts.append(
                f'<div style="margin:1rem 0;padding-bottom:.5rem;'
                f'border-bottom:1px solid #eee"><p>{stmt}</p>{_scale5(key)}</div>')

    parts.append('<h3 style="margin-top:2rem">A few open questions</h3>'
                 '<p class="muted">All optional.</p>')
    for key, prompt, kind in POST_OPEN:
        if kind == "yesno_text":
            parts.append(
                f'<div style="margin:1rem 0"><p>{prompt}</p>'
                f'<label style="font-weight:normal"><input type="radio" name="{key}" '
                f'value="No" checked> No</label> '
                f'<label style="font-weight:normal"><input type="radio" name="{key}" '
                f'value="Yes"> Yes</label>'
                f'<br><textarea name="{key}_detail" rows="2" style="width:100%;margin-top:.4rem" '
                f'placeholder="If yes, please describe"></textarea></div>')
        else:
            parts.append(
                f'<div style="margin:1rem 0"><p>{prompt}</p>'
                f'<textarea name="{key}" rows="3" style="width:100%"></textarea></div>')

    return page("""
      <h1>After the activity</h1>
      <p class="muted">There are no right or wrong answers — just your honest
      impressions.</p>
      <form method="post">
        {{ content|safe }}
        <p style="margin-top:2rem"><button type="submit">Finish</button></p>
      </form>
    """, title="Post-task", content="".join(parts))

# ---------------------------------------------------------------- operator

@app.route("/admin")
def admin():
    if not admin_ok():
        return "Not found", 404
    state = state_or_none()
    if state is None:
        return page("""
          <h1>Operator panel</h1>
          <p class="muted">No session open. <a href="{{ url_for('start') }}">Start one</a>.</p>
        """, title="Admin")

    rows = []
    for kc in kc_order:
        m = state["mastery"][kc]
        cls = "zpd" if ZPD_LOW <= m <= ZPD_HIGH else ("high" if m > ZPD_HIGH else "low")
        rows.append({"kc": kc, "m": m, "cls": cls, "w": int(m * 160),
                     "gate": "open" if m > PREREQ_THRESHOLD else "closed"})

    upcoming = []
    for i, qid in enumerate(question_order):
        e = question_bank[qid]
        done = i < state["index"]
        entry = next((l for l in state["log"] if l["question_id"] == qid), None)
        upcoming.append({
            "qid": qid, "kc": e["kc"].split("_")[0], "done": done,
            "fired": entry["mistake_fired"] if entry else "",
            "resp": entry["response"] if entry else "",
            "ok": entry["judgement_correct"] if entry else "",
            "live": (state.get("current") or {}).get("id") == qid,
        })

    return page("""
      <h1>Operator panel</h1>
      <p class="muted">
        <b>{{ s.participant_id }}</b> · {{ s.condition }} ·
        {{ s.index }}/{{ total }} done ·
        started {{ s.started_at }}
        {% if s.condition == 'random' %}<br>plan: {{ s.random_plan|join(', ') }}{% endif %}
        {% if s.audio_path %}<br>audio: {{ s.audio_path }}{% endif %}
      </p>

      <h3>Mastery</h3>
      <table>
        {% for r in rows %}
        <tr><td>{{ r.kc }}</td><td>{{ '%.2f'|format(r.m) }}</td>
            <td><span class="bar {{ r.cls }}" style="width:{{ r.w }}px"></span></td>
            <td class="muted">gate {{ r.gate }}</td></tr>
        {% endfor %}
      </table>
      <p class="muted">green = in the ZPD band, blue = mastered, grey = not ready</p>

      <h3>Questions</h3>
      <table>
        <tr><th>Q</th><th>KC</th><th>mistake</th><th>said</th><th>judged</th></tr>
        {% for u in upcoming %}
        <tr{% if u.live %} style="background:#fef9c3"{% endif %}>
          <td>{{ u.qid }}{% if u.live %} ←live{% endif %}</td>
          <td>{{ u.kc }}</td><td>{{ u.fired }}</td>
          <td>{{ u.resp }}</td><td>{{ u.ok }}</td></tr>
        {% endfor %}
      </table>

      <h3>Controls</h3>
      <form method="post" action="{{ url_for('admin_undo', key=key) }}" style="display:inline">
        <button class="ghost" {% if not s.log %}disabled{% endif %}>Undo last answer</button>
      </form>
      <form method="post" action="{{ url_for('admin_clear_current', key=key) }}" style="display:inline">
        <button class="ghost" {% if not s.current %}disabled{% endif %}>Close live question</button>
      </form>
      <form method="post" action="{{ url_for('admin_abort', key=key) }}" style="display:inline"
            onsubmit="return confirm('Archive and end this session?')">
        <button class="warn">Archive &amp; end session</button>
      </form>
      <p class="muted" style="margin-top:2rem">Refresh to update.</p>
    """, title="Admin", s=state, rows=rows, upcoming=upcoming,
         total=len(question_order))


@app.route("/admin/undo", methods=["POST"])
def admin_undo():
    if not admin_ok():
        return "Not found", 404
    state = load_state()
    entry = undo_last(state)
    app.logger.warning("UNDO %s", entry["question_id"] if entry else "nothing")
    return redirect(url_for("admin"))


@app.route("/admin/clear-current", methods=["POST"])
def admin_clear_current():
    if not admin_ok():
        return "Not found", 404
    state = load_state()
    state["current"] = None
    save_state(state)
    return redirect(url_for("admin"))


@app.route("/admin/abort", methods=["POST"])
def admin_abort():
    if not admin_ok():
        return "Not found", 404
    global _recorder
    state = load_state()
    if _recorder is not None:
        _recorder.stop()
        _recorder = None
        state = load_state()
    folder = archive_session(state)
    save_state(state)
    clear_state()
    return page("""
      <h1>Session ended</h1>
      <p class="muted">Archived to <code>{{ folder }}</code></p>
      <p><a href="{{ url_for('start') }}">Start a new session</a></p>
    """, title="Ended", folder=folder)


if __name__ == "__main__":
    missing = [q for q, e in question_bank.items() if not e["text"]]
    if missing:
        print(f"\n  WARNING: {len(missing)} questions have no text yet: "
              f"{', '.join(missing)}\n")
    print(f"  participant screen : http://127.0.0.1:{PORT}")
    print(f"  operator panel     : http://127.0.0.1:{PORT}/admin\n")
    app.run(port=PORT, debug=False)