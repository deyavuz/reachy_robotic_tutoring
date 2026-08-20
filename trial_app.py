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

from flask import Flask, request, redirect, url_for, render_template_string  # noqa: E402

from bayes_algorithm import (  # noqa: E402
    new_state, load_state, save_state, clear_state, open_question,
    update_mastery, undo_last, archive_session,
    question_bank, question_order, kc_order, STATE_PATH,
    ZPD_LOW, ZPD_HIGH, PREREQ_THRESHOLD, N_RANDOM_MISTAKES,
)

try:
    from recorder import SessionRecorder, BACKEND as AUDIO_BACKEND
except Exception:
    SessionRecorder, AUDIO_BACKEND = None, None

PORT = 5001                      # 5000 is AirPlay on macOS
SECONDS_PER_QUESTION = 120
SOFT_WARNING_AT = 105            # 1:45

app = Flask(__name__)
_recorder = None

BASE = """
<!doctype html><meta charset="utf-8"><title>{{ t }}</title>
<style>
 body{font-family:-apple-system,system-ui,sans-serif;max-width:42rem;margin:4rem auto;
      padding:0 1.5rem;line-height:1.6;color:#18181b}
 .q{font-size:1.25rem;background:#f4f4f5;padding:1.5rem;border-radius:8px;margin:2rem 0}
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
        return redirect(url_for("progress"))

    existing = state_or_none()
    return page("""
      <h1>Session setup</h1>
      {% if existing %}
        <p class="muted">A session for <b>{{ existing.participant_id }}</b> is already
        open ({{ existing.index }} of {{ total }} done). Starting a new one will
        discard it. <a href="{{ url_for('admin') }}">Open the operator panel</a>.</p>
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


@app.route("/progress")
def progress():
    global _recorder
    state = state_or_none()
    if state is None:
        return redirect(url_for("start"))

    if state["index"] >= len(question_order):
        if _recorder is not None:
            _recorder.stop()
            _recorder = None
            state = load_state()
        folder = archive_session(state)
        save_state(state)
        return page("""
          <h1>All done</h1>
          <p>Thank you — that's the end of the session.</p>
          <p class="muted">Saved to <code>{{ folder }}</code></p>
        """, title="Done", folder=folder)

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
      <div id="timer">2:00</div>
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
    app.logger.info("%s: %s %.2f -> %.2f", state["participant_id"], kc, before, after)
    return redirect(url_for("progress"))


# ---------------------------------------------------------------- operator

@app.route("/admin")
def admin():
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
      <form method="post" action="{{ url_for('admin_undo') }}" style="display:inline">
        <button class="ghost" {% if not s.log %}disabled{% endif %}>Undo last answer</button>
      </form>
      <form method="post" action="{{ url_for('admin_clear_current') }}" style="display:inline">
        <button class="ghost" {% if not s.current %}disabled{% endif %}>Close live question</button>
      </form>
      <form method="post" action="{{ url_for('admin_abort') }}" style="display:inline"
            onsubmit="return confirm('Archive and end this session?')">
        <button class="warn">Archive &amp; end session</button>
      </form>
      <p class="muted" style="margin-top:2rem">Refresh to update.</p>
    """, title="Admin", s=state, rows=rows, upcoming=upcoming,
         total=len(question_order))


@app.route("/admin/undo", methods=["POST"])
def admin_undo():
    state = load_state()
    entry = undo_last(state)
    app.logger.warning("UNDO %s", entry["question_id"] if entry else "nothing")
    return redirect(url_for("admin"))


@app.route("/admin/clear-current", methods=["POST"])
def admin_clear_current():
    state = load_state()
    state["current"] = None
    save_state(state)
    return redirect(url_for("admin"))


@app.route("/admin/abort", methods=["POST"])
def admin_abort():
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