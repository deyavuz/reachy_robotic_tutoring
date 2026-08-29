# Reachy robotic tutoring

A dissertation study built on [Reachy Mini](https://github.com/pollen-robotics/reachy_mini) and its [conversation app](https://github.com/pollen-robotics/reachy_mini_conversation_app). Reachy plays a **tutee**: a robot still learning probability. A participant teaches it by reading probability questions aloud; the robot answers correctly or with a scripted mistake, and the participant judges and discusses the answer with it.

Which mistake (if any) Reachy makes is chosen by a Bayesian mastery model calibrated to the participant's zone of proximal development (ZPD), so the "wrongness" of the robot adapts as the session goes on.

This is a fork of pollen-robotics' app — see that repo for the general Reachy Mini SDK, daemon setup, and the full conversation-app tool/profile system. This README only covers what's specific to running the study.

## How a session works

Two apps run side by side:

- **`trial_app.py`** (Flask, `http://127.0.0.1:5001`) is the experimenter/participant-facing control panel. It owns all session state (`session_state.json`) — participant ID, condition, mastery per knowledge component, which question is "open," and the answer log. **It is the only thing that writes that state.**
- **`reachy-mini-conversation-app`**, running the `bayes_tutee` profile, is the robot's voice and personality. Its `decide_response` tool only *reads* that state: when a question is marked open, it returns either the exact scripted wrong line or an instruction to reason the answer out correctly; when nothing is open, it stays silent.

Because of that split, the robot will only respond to a question once you've stepped it forward in the trial app's flow (`/practice/begin`, `/begin`, …) — reading a question aloud with nothing opened yet just gets silence.

## Study-specific files

| File | Purpose |
|------|---------|
| [`profiles/bayes_tutee/profile.md`](profiles/bayes_tutee/profile.md) | The tutee persona, response protocol, and the private question-recognition reference. |
| [`src/reachy_mini_conversation_app/tools/bayes_algorithm.py`](src/reachy_mini_conversation_app/tools/bayes_algorithm.py) | The ZPD/Bayesian mastery model, the 12-item question bank, and session state I/O. |
| [`src/reachy_mini_conversation_app/tools/decide_response.py`](src/reachy_mini_conversation_app/tools/decide_response.py) | The tool bridging the conversation to that state — the only thing the robot calls per question. |
| [`src/reachy_mini_conversation_app/tools/recorder.py`](src/reachy_mini_conversation_app/tools/recorder.py) | Continuous session audio recording, resolved by microphone name (see its module docstring for backend/device notes). |
| [`trial_app.py`](trial_app.py) | The experimenter/participant Flask app described above. |
| [`preflight.py`](preflight.py) | Sanity-checks the algorithm and the `decide_response` tool load correctly, without needing the robot. Run before every session. |
| [`QUESTION_SOURCES.md`](QUESTION_SOURCES.md) | Citations and provenance for each question, plus notes on items dropped or adapted from the source instrument. |
| [`SESSION_CHECKLIST.md`](SESSION_CHECKLIST.md) | The printable run-of-show checklist for a live session. |
| [`launch_conv_app.py`](launch_conv_app.py) | macOS launch wrapper working around a local environment quirk (Python `.pth` files periodically going iCloud-hidden), bypassing `.pth` loading entirely. Use this instead of the `reachy-mini-conversation-app` entry point if that quirk resurfaces. |
| `data/<participant_id>/` | Archived per-participant output: an answer-judgement CSV, the full session-state JSON, and the session audio recording. |

## Running a session

1. Install the [Reachy Mini SDK](https://github.com/pollen-robotics/reachy_mini/) and set up `uv sync` per the upstream repo's instructions.
2. Have [Reachy Mini Control.app](https://github.com/pollen-robotics/reachy_mini) (or the daemon) running as the robot bridge.
3. Run `python preflight.py` — confirm `ALL CHECKS PASSED` before continuing.
4. Terminal 1 — the trial app:
   ```bash
   python trial_app.py
   ```
   Participant screen: `http://127.0.0.1:5001`. Operator panel: `http://127.0.0.1:5001/admin?key=<ADMIN_TOKEN>`.
5. Terminal 2 — the conversation app, locked to the study profile:
   ```bash
   REACHY_MINI_CUSTOM_PROFILE=bayes_tutee reachy-mini-conversation-app --ui --media-backend webrtc
   ```
   `--media-backend webrtc` is required when Control.app bridges to a physical robot from this machine — without it, audio plays through the laptop instead of the robot.
6. Dry-run one practice question as a throwaway `SETUP` participant, then archive and delete that session before the real one begins.

Full step-by-step, including what to do when things go wrong mid-session, is in [`SESSION_CHECKLIST.md`](SESSION_CHECKLIST.md).

## License

Apache 2.0, inherited from [pollen-robotics/reachy_mini_conversation_app](https://github.com/pollen-robotics/reachy_mini_conversation_app).
