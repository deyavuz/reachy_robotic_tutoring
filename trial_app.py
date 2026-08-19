"""Local trial app for the Reachy Bayes study.

Replaces Qualtrics for the trial phase. Runs on the same machine as the
conversation app so it can share state directly — no API, no tunnel.

    python trial_app.py

Then open http://127.0.0.1:5000 on the participant's screen.
"""

import os
from flask import Flask, request, redirect, url_for, render_template_string

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__),
                                "src", "reachy_mini_conversation_app", "tools"))

from bayes_algorithm import (
    new_state, load_state, save_state, open_question, update_mastery,
    export_log_csv, question_bank, question_order, STATE_PATH,
)
#from recorder import SessionRecorder

app = Flask(__name__)

_recorder = None          # one per session

SECONDS_PER_QUESTION = 120
SOFT_WARNING_AT = 105          # 1:45

BASE = """
<!doctype html>
<title>Study</title>
<style>
  body { font-family: -apple-system, system-ui, sans-serif; max-width: 40rem;
         margin: 4rem auto; padding: 0 1.5rem; line-height: 1.6; color: #1a1a1a; }
  .q { font-size: 1.25rem; background: #f4f4f5; padding: 1.5rem;
       border-radius: 8px; margin: 2rem 0; }
  button { font-size: 1rem; padding: 0.75rem 1.5rem; border-radius: 6px;
           border: 1px solid #1a1a1a; background: #1a1a1a; color: white;
           cursor: pointer; margin-right: 0.5rem; }
  button.ghost { background: white; color: #1a1a1a; }
  #timer { font-size: 3rem; font-variant-numeric: tabular-nums; margin: 2rem 0; }
  #timer.warn { color: #b45309; }
  .muted { color: #71717a; font-size: 0.9rem; }
  input { font-size: 1rem; padding: 0.5rem; }
</style>
{{ body|safe }}
"""


def page(body, **kw):
    return render_template_string(BASE, body=render_template_string(body, **kw))


@app.route("/", methods=["GET", "POST"])
def start():
    global _recorder
    if request.method == "POST":
        pid = request.form["pid"].strip()
        state = new_state(pid, request.form["condition"])
        #_recorder = SessionRecorder(pid)
        #state["audio_path"] = _recorder.start()
        #state["audio_started_at"] = _recorder.started_at
        save_state(state)
        return redirect(url_for("progress"))
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
      <p class="muted">Restart the Reachy conversation app before each participant.</p>
    """)


@app.route("/progress")
def progress():
    state = load_state()
    i = state["index"]

    if i >= len(question_order):
        #global _recorder
        #if _recorder is not None:
        #    _recorder.stop()
        #    _recorder = None
        out = os.path.join(os.path.dirname(STATE_PATH),
                           f"log_{state['participant_id']}.csv")
        export_log_csv(state, out)
        return page("""
          <h1>All done</h1>
          <p>Thank you — that's the end of the session.</p>
          <p class="muted">Log saved to {{ out }}</p>
        """, out=out)

    return page("""
      <p class="muted">Question {{ n }} of {{ total }}</p>
      <h1>Ready for the next question?</h1>
      <form method="post" action="{{ url_for('show') }}">
        <button type="submit">Show me question {{ n }}</button>
      </form>
    """, n=i + 1, total=len(question_order))


@app.route("/show", methods=["POST"])
def show():
    state = load_state()
    qid = question_order[state["index"]]
    return page("""
      <p class="muted">Question {{ n }} of {{ total }}</p>
      <div class="q">{{ text }}</div>
      <p>Read this question aloud to the robot when you're ready.</p>
      <form method="post" action="{{ url_for('begin') }}">
        <button type="submit">I'm ready to start the conversation</button>
      </form>
    """, n=state["index"] + 1, total=len(question_order),
         text=question_bank[qid]["text"])


@app.route("/begin", methods=["POST"])
def begin():
    state = load_state()
    qid = question_order[state["index"]]
    open_question(state, qid)          # decision fixed here, robot reads it
    return redirect(url_for("timer"))


@app.route("/timer")
def timer():
    state = load_state()
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
        const el = document.getElementById('timer');
        const note = document.getElementById('note');
        const tick = setInterval(() => {
          left--;
          const m = Math.floor(left / 60), s = String(left % 60).padStart(2, '0');
          el.textContent = m + ':' + s;
          if (left === {{ secs }} - {{ warn }}) {
            el.classList.add('warn');
            note.textContent = "About fifteen seconds left — finish your thought.";
          }
          if (left <= 0) {
            clearInterval(tick);
            window.location = "{{ url_for('judge_get') }}";
          }
        }, 1000);
      </script>
    """, n=state["index"] + 1, total=len(question_order),
         text=question_bank[qid]["text"],
         secs=SECONDS_PER_QUESTION, warn=SOFT_WARNING_AT)


@app.route("/judge", methods=["GET", "POST"])
def judge():
    return judge_get()


@app.route("/judge_get")
def judge_get():
    return page("""
      <h1>Was the robot's answer correct?</h1>
      <form method="post" action="{{ url_for('record') }}">
        <button name="response" value="correct" type="submit">Yes</button>
        <button name="response" value="wrong" type="submit">No</button>
        <button name="response" value="dontknow" type="submit" class="ghost">I don't know</button>
      </form>
    """)


@app.route("/record", methods=["POST"])
def record():
    state = load_state()
    kc, before, after = update_mastery(state, request.form["response"])
    app.logger.info("%s: %s %.2f -> %.2f", state["participant_id"], kc, before, after)
    return redirect(url_for("progress"))


if __name__ == "__main__":
    app.run(port=5001, debug=False)