# Session checklist

## Night before

- [ ] `python preflight.py` → ALL CHECKS PASSED
- [ ] Phone charged as backup recorder
- [ ] Consent forms printed

---

## 45 minutes before

**1. Robot**
- [ ] Powered on, `lsof -i :8000` shows a listener

**2. Reinstall — do this every time, it has broken four times**
```
cd ~/Desktop/Dissertation/reachy_robotic_tutoring
conda deactivate
source .venv/bin/activate
uv pip install -e . --reinstall
```

**3. Preflight**
```
python preflight.py
```
- [ ] ALL CHECKS PASSED
- [ ] No stale state file

**4. Terminal 1 — Flask**
```
python trial_app.py
```
- [ ] Participant screen loads at `http://127.0.0.1:5001`
- [ ] Operator panel loads at `http://127.0.0.1:5001/admin`

**5. Terminal 2 — conversation app**
```
reachy-mini-conversation-app --ui
```
- [ ] Starts (can take 2 minutes)
- [ ] `bayes_tutee` profile applies without timing out
- [ ] `decide_response` enabled for it

**6. Dry run one question as `SETUP`**
- [ ] Robot greets, then goes quiet
- [ ] Read Q1 aloud → robot answers
- [ ] Answer matches the `line` in the operator panel
- [ ] Archive & end session, delete the SETUP folder from `data/`

---

## Participant arrives

- [ ] Consent signed
- [ ] Phone recording started, wall-clock time noted
- [ ] Operator panel open on **your** screen, participant screen on theirs
- [ ] Fresh session: real ID, correct condition
- [ ] Condition alternates or is randomised — check your allocation sheet

---

## During

Watch the operator panel between questions. Green bars are KCs in the ZPD band.

- **Robot silent after a question** — it may not have called the tool. Ask them
  to read the question again.
- **Robot paraphrases the scripted line** — note it, keep going, fix later.
- **Wrong question opened** — Undo last answer in the panel.
- **Something unrecoverable** — Archive & end. Partial data beats no data.

---

## After

- [ ] Session archived to `data/<ID>/` (the app does this)
- [ ] Audio backed up off the phone
- [ ] **Restart both apps** before the next participant
- [ ] Decision-log note while it's fresh

---

## Known gotchas

| Symptom | Cause |
|---|---|
| Flask 403 | AirPlay owns port 5000 — you should be on 5001 |
| `No module named reachy_mini_conversation_app` | Editable install broke — reinstall |
| Profile times out | Almost always the same broken install |
| `🅒 base` in the prompt | conda is shadowing `.venv` — `conda deactivate` |
| Robot answers before you finish reading | Tool called early; it waits 12s, then goes silent |