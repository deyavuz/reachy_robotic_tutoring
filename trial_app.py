"""Local trial app for the Reachy Bayes study.

Runs on the same machine as the conversation app so it can share state
directly. Questionnaires are handled separately (Google Forms); this app only
runs the trial itself.

    python trial_app.py

Participant screen:  http://127.0.0.1:5001
Operator panel:      http://127.0.0.1:5001/admin?key=defne2026
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "src", "reachy_mini_conversation_app", "tools"))

from flask import Flask, request, redirect, url_for, render_template_string  # noqa: E402

from bayes_algorithm import (  # noqa: E402
    new_state, load_state, save_state, clear_state, open_question,
    open_practice, end_practice, update_mastery, undo_last, archive_session,
    PRACTICE, question_bank, question_order, kc_order, STATE_PATH,
    ZPD_LOW, ZPD_HIGH, PREREQ_THRESHOLD, N_RANDOM_MISTAKES,
)

try:
    from recorder import SessionRecorder, BACKEND as AUDIO_BACKEND
except Exception:
    SessionRecorder, AUDIO_BACKEND = None, None

PORT = 5001
ADMIN_TOKEN = "defne2026"

# Soft time guidance only — no visible countdown, no hard cutoff.
SOFT_GUIDANCE_AT = 420          # after 7 min, gently suggest wrapping up

app = Flask(__name__)
_recorder = None

BASE = """
<!doctype html><meta charset="utf-8"><title>{{ t }}</title>
<style>
 body{font-family:-apple-system,system-ui,sans-serif;max-width:42rem;margin:3.5rem auto;
      padding:0 1.5rem;line-height:1.65;color:#18181b}
 .q{font-size:1.2rem;background:#f4f4f5;padding:1.5rem 1.75rem;border-radius:8px;
    margin:1.5rem 0;white-space:pre-line;line-height:1.7}
 button{font-size:1.05rem;padding:.8rem 1.6rem;border-radius:6px;border:1px solid #18181b;
        background:#18181b;color:#fff;cursor:pointer;margin:0 .5rem .5rem 0}
 button.ghost{background:#fff;color:#18181b}
 button.warn{background:#fff;color:#b91c1c;border-color:#b91c1c}
 .muted{color:#71717a;font-size:.92rem}
 .lead{font-size:1.05rem}
 input,select{font-size:1rem;padding:.5rem}
 table{border-collapse:collapse;width:100%;margin:1rem 0;font-size:.9rem}
 th,td{text-align:left;padding:.4rem .6rem;border-bottom:1px solid #e4e4e7}
 .bar{display:inline-block;height:.7rem;background:#18181b;border-radius:2px;vertical-align:middle}
 .zpd{background:#16a34a}.low{background:#a1a1aa}.high{background:#3b82f6}
 code{background:#f4f4f5;padding:.1rem .3rem;border-radius:3px}
 #note{margin-top:1.5rem}
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
        return redirect(url_for("intro"))

    return page("""
      <h1>Session setup</h1>
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
    """, title="Setup", audio=AUDIO_BACKEND)


@app.route("/intro")
def intro():
    state = state_or_none()
    if state is None:
        return redirect(url_for("start"))
    return page("""
      <h1>Welcome — thanks for taking part</h1>
      <p class="lead">In this study you'll help a small robot that's still learning
      probability. You'll read it a series of short probability questions, one at a time,
      and talk each one through together.</p>
      <p class="lead">The robot is a learner, so it won't always get things right. When
      you think it's mistaken, say so and explain your thinking — that's exactly what
      we're interested in. There are no trick questions and nothing to revise.</p>
      <p class="lead">We'll start with one relaxed practice question so you can see how it
      works, and then move on to the real ones. Take your time throughout.</p>
      <form method="post" action="{{ url_for('practice') }}">
        <button type="submit">Start with the practice question</button>
      </form>
    """, title="Welcome")


@app.route("/practice", methods=["GET", "POST"])
def practice():
    state = state_or_none()
    if state is None:
        return redirect(url_for("start"))
    if state.get("practice_done"):
        return redirect(url_for("progress"))
    return page("""
      <p class="muted">Practice question · doesn't count</p>
      <h1>Let's try one together</h1>
      <p>When you're ready, read the question below out loud to the robot, then talk it
      through. If the robot gets it wrong, explain what you think the right answer is.</p>
      <div class="q">{{ text }}</div>
      <form method="post" action="{{ url_for('practice_begin') }}">
        <button type="submit">I've read it — let's talk to the robot</button>
      </form>
    """, title="Practice", text=PRACTICE["text"])


@app.route("/practice/begin", methods=["POST"])
def practice_begin():
    open_practice(load_state())
    return page("""
      <p class="muted">Practice question · doesn't count</p>
      <div class="q">{{ text }}</div>
      <p class="muted">Talk it through with the robot. When you're done, tap below.</p>
      <form method="post" action="{{ url_for('practice_judge') }}">
        <button type="submit" class="ghost">We're done — next</button>
      </form>
    """, title="Practice", text=PRACTICE["text"])


@app.route("/practice/judge", methods=["POST"])
def practice_judge():
    return page("""
      <h1>Was the robot's first answer correct?</h1>
      <p class="muted">You'll be asked this after every question. Just your honest read
      of the robot's <b>first</b> answer, before any correction.</p>
      <form method="post" action="{{ url_for('practice_done') }}">
        <button name="r" value="correct">Yes</button>
        <button name="r" value="wrong">No</button>
        <button name="r" value="dontknow" class="ghost">I'm not sure</button>
      </form>
    """, title="Practice")


@app.route("/practice/done", methods=["POST"])
def practice_done():
    end_practice(load_state())
    return page("""
      <h1>That's the idea</h1>
      <p class="lead">From here on the questions count. There are twelve of them. Read each
      one aloud, talk it through with the robot, and tell us whether its first answer was
      right. Take as long as you like on each.</p>
      <form method="post" action="{{ url_for('progress') }}">
        <button type="submit">Start the first question</button>
      </form>
    """, title="Ready")


@app.route("/progress", methods=["GET", "POST"])
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
          <h1>All done — thank you!</h1>
          <p class="lead">That's the end of the questions. There's a short questionnaire to
          finish up — the researcher will point you to it.</p>
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
      <p>Read this out loud to the robot when you're ready, then talk it through.</p>
      <form method="post" action="{{ url_for('begin') }}">
        <button type="submit">I've read it — let's talk to the robot</button>
      </form>
    """, n=state["index"] + 1, total=len(question_order),
         text=question_bank[qid]["text"])


@app.route("/begin", methods=["POST"])
def begin():
    state = load_state()
    open_question(state, question_order[state["index"]])
    return redirect(url_for("discuss"))


@app.route("/discuss")
def discuss():
    state = load_state()
    if state.get("current") is None:
        return redirect(url_for("progress"))
    qid = state["current"]["id"]
    return page("""
      <p class="muted">Question {{ n }} of {{ total }}</p>
      <div class="q">{{ text }}</div>
      <p id="note" class="muted">Talk it through with the robot. Tap below when you're done.</p>
      <form method="post" action="{{ url_for('judge') }}">
        <button type="submit" class="ghost">We're done — next</button>
      </form>
      <script>
        setTimeout(function(){
          document.getElementById('note').textContent =
            "Whenever you feel you've talked it through, tap below — no rush.";
        }, {{ guidance_ms }});
      </script>
    """, n=state["index"] + 1, total=len(question_order),
         text=question_bank[qid]["text"], guidance_ms=SOFT_GUIDANCE_AT * 1000)


@app.route("/judge", methods=["POST"])
def judge():
    return page("""
      <h1>Was the robot's first answer correct?</h1>
      <p class="muted">Your honest read of the robot's <b>first</b> answer, before any
      correction.</p>
      <form method="post" action="{{ url_for('record') }}">
        <button name="r" value="correct">Yes</button>
        <button name="r" value="wrong">No</button>
        <button name="r" value="dontknow" class="ghost">I'm not sure</button>
      </form>
    """, title="Judgement")


@app.route("/record", methods=["POST"])
def record():
    state = load_state()
    if state.get("current") is None:
        return redirect(url_for("progress"))
    kc, before, after = update_mastery(state, request.form["r"])
    archive_session(state, move_audio=False)      # live-save after every answer
    app.logger.info("%s: %s %.2f -> %.2f", state["participant_id"], kc, before, after)
    return redirect(url_for("progress"))


# ---------------------------------------------------------------- operator

@app.route("/admin")
def admin():
    if not admin_ok():
        return "Not found", 404
    state = state_or_none()
    if state is None:
        return page("<h1>Operator panel</h1><p class='muted'>No session open.</p>",
                    title="Admin")

    rows = []
    for kc in kc_order:
        m = state["mastery"][kc]
        cls = "zpd" if ZPD_LOW <= m <= ZPD_HIGH else ("high" if m > ZPD_HIGH else "low")
        rows.append({"kc": kc, "m": m, "cls": cls, "w": int(m * 160),
                     "gate": "open" if m > PREREQ_THRESHOLD else "closed"})

    upcoming = []
    for i, qid in enumerate(question_order):
        entry = next((l for l in state["log"] if l["question_id"] == qid), None)
        upcoming.append({
            "qid": qid, "kc": question_bank[qid]["kc"].split("_")[0],
            "fired": entry["mistake_fired"] if entry else "",
            "resp": entry["response"] if entry else "",
            "ok": entry["judgement_correct"] if entry else "",
            "live": (state.get("current") or {}).get("id") == qid,
        })

    return page("""
      <h1>Operator panel</h1>
      <p class="muted"><b>{{ s.participant_id }}</b> · {{ s.condition }} ·
        {{ s.index }}/{{ total }} done · started {{ s.started_at }}
        {% if s.condition == 'random' %}<br>plan: {{ s.random_plan|join(', ') }}{% endif %}
        {% if s.audio_path %}<br>audio: {{ s.audio_path }}{% endif %}</p>
      <h3>Mastery</h3>
      <table>
        {% for r in rows %}
        <tr><td>{{ r.kc }}</td><td>{{ '%.2f'|format(r.m) }}</td>
            <td><span class="bar {{ r.cls }}" style="width:{{ r.w }}px"></span></td>
            <td class="muted">gate {{ r.gate }}</td></tr>
        {% endfor %}
      </table>
      <p class="muted">green = in ZPD band · blue = mastered · grey = not ready</p>
      <h3>Questions</h3>
      <table>
        <tr><th>Q</th><th>KC</th><th>mistake</th><th>said</th><th>judged</th></tr>
        {% for u in upcoming %}
        <tr{% if u.live %} style="background:#fef9c3"{% endif %}>
          <td>{{ u.qid }}{% if u.live %} ←live{% endif %}</td>
          <td>{{ u.kc }}</td><td>{{ u.fired }}</td><td>{{ u.resp }}</td><td>{{ u.ok }}</td></tr>
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
        <button class="warn">Archive &amp; end</button>
      </form>
      <p class="muted" style="margin-top:2rem">Refresh to update.</p>
    """, title="Admin", s=state, rows=rows, upcoming=upcoming,
         total=len(question_order), key=ADMIN_TOKEN)


@app.route("/admin/undo", methods=["POST"])
def admin_undo():
    if not admin_ok():
        return "Not found", 404
    undo_last(load_state())
    return redirect(url_for("admin", key=ADMIN_TOKEN))


@app.route("/admin/clear-current", methods=["POST"])
def admin_clear_current():
    if not admin_ok():
        return "Not found", 404
    state = load_state()
    state["current"] = None
    save_state(state)
    return redirect(url_for("admin", key=ADMIN_TOKEN))


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
    return page("<h1>Session ended</h1><p class='muted'>Archived to <code>{{ f }}</code></p>"
                "<p><a href='{{ url_for('start') }}'>New session</a></p>",
                title="Ended", f=folder)


if __name__ == "__main__":
    print(f"  participant screen : http://127.0.0.1:{PORT}")
    print(f"  operator panel     : http://127.0.0.1:{PORT}/admin?key={ADMIN_TOKEN}\n")
    app.run(port=PORT, debug=False)