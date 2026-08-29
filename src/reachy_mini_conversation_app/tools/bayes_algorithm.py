"""ZPD-calibrated error generation — core logic.

State lives in a JSON file on disk so two processes can share it: the Flask
trial app (which serves questions and records judgements) and the Reachy
conversation app (which reads what to say). The trial app is the only writer;
the robot tool only ever reads.

Completed sessions are archived to data/<participant_id>/.

Question wording note: several items are adapted from the CPR test
(Diaz & Batanero 2009) and related sources, but have been reworded for clarity
and read-aloud flow, and multiple-choice options have been removed where they
hurt comprehension. Because of this rewording, the original published
calibration percentages are indicative only, not exact for these versions.
"""

import csv
import json
import os
import random
import shutil
from datetime import datetime

# ---------------------------------------------------------------- parameters

START_MASTERY = 0.5
UPDATE_RATE = 0.15
PREREQ_THRESHOLD = 0.45
ZPD_LOW, ZPD_HIGH = 0.3, 0.7
N_RANDOM_MISTAKES = 6      # control condition: fixed count, ~half of 12

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

STATE_PATH = os.path.join(HERE, "session_state.json")
DATA_DIR = os.path.join(REPO, "data")

# ------------------------------------------------------------------- the KCs

kc_order = [
    "KC1_foundations",
    "KC2_conditional",
    "KC3_joint",
    "KC4_total_prob",
    "KC5_updating",
]

# --------------------------------------------------------------- question bank
#
# 12 questions: KC1=2, KC2=2, KC3=3, KC4=2, KC5=3.
# Cut from the 14-item version: the tennis conjunction item (weak, barely
# taught) and the cancer transposed-conditional item (confusing options).
# Reworded for clarity; MC options kept only where they genuinely help.

question_bank = {
    # ---- KC1: probability foundations ----
    "Q1": {
        "kc": "KC1_foundations",
        "source": "Kahneman & Tversky (1973) — engineer/lawyer, 'Jack' description",
        "correct": "30% — the base rate, since the description is uninformative",
        "text": "A room contains 100 people: 30 of them are engineers and 70 are lawyers. "
                "Someone is picked from the room at random. Here is a short description of them: "
                "\"Jack is 45. He is married with four children. He is careful, ambitious, and "
                "shows little interest in politics. In his spare time he enjoys carpentry, "
                "sailing, and solving mathematical puzzles.\" "
                "What is the probability that Jack is one of the engineers?",
        "line": "He sounds just like an engineer — carpentry, sailing, mathematical puzzles. I'd say around 90%.",
        "mistake_type": "base rate neglect (judgment form)",
    },
    "Q2": {
        "kc": "KC1_foundations",
        "source": "CPR Item 15 — die, independence",
        "correct": "1/2 — each throw is independent",
        "text": "Someone rolls a fair die and writes down whether the result is odd or even. "
                "So far they have rolled eleven times, and got an odd number almost every time. "
                "They are about to roll once more. "
                "What is the probability that this next roll is odd?",
        "line": "There have already been so many odd rolls, so an even one feels overdue. I'd say the chance of odd is now lower than half.",
        "mistake_type": "gambler's fallacy",
    },

    # ---- KC2: conditional probability ----
    "Q3": {
        "kc": "KC2_conditional",
        "source": "CPR Item 9b (Falk 1986) — marbles, backward conditioning",
        "correct": "1/3",
        "text": "A bag holds two black marbles and two white marbles. "
                "You draw one marble and set it aside without looking at it. "
                "You then draw a second marble, and it is white. "
                "Given that the second marble is white, what is the probability that the first "
                "marble — the one you set aside — is also white?",
        "line": "I'd say one half. The first marble was already drawn before the second, so the second one can't tell us anything about it.",
        "mistake_type": "fallacy of the time axis",
    },
    "Q4": {
        "kc": "KC2_conditional",
        "source": "CPR Item 4 — four lamps, dependence",
        "correct": "the second lamp is more likely to be good than defective",
        "text": "A box holds four lamps. Two of them are broken and two work. "
                "You take out two lamps, one after the other, without putting the first back. "
                "The first lamp you take out turns out to be broken. "
                "Given that, is the second lamp you take out more likely to be broken, "
                "more likely to work, or equally likely either way?",
        "line": "I think it's equally likely either way — taking one lamp out doesn't change what the second one is.",
        "mistake_type": "failure to restrict the sample space",
    },

    # ---- KC3: joint probability and the product rule ----
    "Q5": {
        "kc": "KC3_joint",
        "source": "CPR Item 17 — lying, product rule (dependent)",
        "correct": "0.91 x 0.36 = about 0.33",
        "text": "In a certain city, 91% of people admit that they sometimes lie. "
                "Of the people who lie, 36% say they lie about important things. "
                "If you pick someone from the city at random, what is the probability that they "
                "are someone who lies about important things?",
        "line": "If I divide 0.36 by 0.91, I get about 0.40, so the answer is 0.40.",
        "mistake_type": "division instead of multiplication for a joint probability",
    },
    "Q6": {
        "kc": "KC3_joint",
        "source": "CPR Item 16 — maths/English, product rule (independent)",
        "correct": "0.8 x 0.7 = 0.56",
        "text": "In a school, 80% of students pass the maths test and 70% pass the English test. "
                "Whether a student passes one test has no bearing on the other. "
                "If you pick a student at random, what is the probability that they passed "
                "both tests?",
        "line": "I'd add them together — 80% plus 70% — so 150%.",
        "mistake_type": "addition rule substituted for the product rule",
    },
    "Q7": {
        "kc": "KC3_joint",
        "source": "CPR Item 10 — urn, joint probability",
        "correct": "the two events are equally likely (each 1/3)",
        "text": "A bag holds one blue marble and two red marbles. "
                "You draw two marbles, one after the other, without putting the first back. "
                "Which is more likely: that you draw two red marbles, or that you draw a red "
                "one first and then the blue one? Or are they equally likely?",
        "line": "Drawing two red seems more likely to me, since there are two red marbles and only one blue.",
        "mistake_type": "representativeness — compound probabilities not computed",
    },

    # ---- KC4: total probability ----
    "Q8": {
        "kc": "KC4_total_prob",
        "source": "CPR Item 14 — smokers by gender",
        "correct": "0.6 x 0.5 + 0.4 x 0.25 = 0.4",
        "text": "In a city, 60% of people are men and 40% are women. "
                "Half of the men smoke, and a quarter of the women smoke. "
                "If you pick one person from the city at random, what is the probability that "
                "they smoke?",
        "line": "Fifty men smoke and twenty-five women smoke, so that's seventy-five out of two hundred — about 37.5%.",
        "mistake_type": "branches not weighted by group size",
    },
    "Q9": {
        "kc": "KC4_total_prob",
        "source": "CPR Item 5 (Eddy 1982) — mammogram, adapted with explicit sensitivity/false-positive rate",
        "correct": "about 9.2%",
        "text": "1% of women have breast cancer. The mammogram correctly returns positive for "
                "90% of women who have it, but also returns a false positive for 9% of women "
                "who don't. A woman tests positive. Roughly what is the probability she "
                "actually has breast cancer?",
        "line": "If the test came back positive, I'd say it's around 90% likely she has it.",
        "mistake_type": "positive result read as the posterior, base rate ignored",
    },

    # ---- KC5: Bayesian updating ----
    "Q10": {
        "kc": "KC5_updating",
        "source": "CPR Item 2 (Tversky & Kahneman 1982) — blue taxi",
        "correct": "about 41%",
        "text": "A taxi was involved in a hit-and-run one night. "
                "In the city, 85% of taxis are green and 15% are blue. "
                "A witness says the taxi was blue. When tested, this witness correctly identifies "
                "the colour of a taxi at night 80% of the time. "
                "Given the witness said blue, what is the probability that the taxi really was blue?",
        "line": "I'd say around 80%, since that's how often the witness gets the colour right.",
        "mistake_type": "base rate fallacy",
    },
    "Q11": {
        "kc": "KC5_updating",
        "source": "CPR Item 18 (Totohasina 1992) — two machines",
        "correct": "about 0.77",
        "text": "Two machines make the same kind of ball. "
                "Machine A makes 40% of all the balls, and Machine B makes the other 60%. "
                "5% of Machine A's balls are defective, and only 1% of Machine B's are. "
                "You pick up a ball at random and find it is defective. "
                "What is the probability that it came from Machine A?",
        "line": "I'd say 5%, since that's how often Machine A makes a defective ball.",
        "mistake_type": "inverse conditional reported as the posterior",
    },
    "Q12": {
        "kc": "KC5_updating",
        "source": "Casscells et al. (1978) — rare disease (paraphrased)",
        "correct": "about 2%",
        "text": "A disease affects about 1 in every 1,000 people. "
                "There is a test for it. If you have the disease, the test is always positive. "
                "If you do not have the disease, the test is still positive 5% of the time — a "
                "false alarm. "
                "You take the test and it comes back positive. "
                "Given only that, what is the probability that you actually have the disease?",
        "line": "I'd say about 95%, since the test only gives a false positive 5% of the time.",
        "mistake_type": "base rate neglect (computational form)",
    },
}

question_order = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6",
                  "Q7", "Q8", "Q9", "Q10", "Q11", "Q12"]

PRACTICE = {
    "text": "Here's a warm-up. A bag has 3 red marbles and 1 blue marble. "
            "You take one out without looking. What is the probability that it is red?",
    "line": "I think it's a half, since the marble is either red or blue.",
}

# ------------------------------------------------------------------ state I/O

def new_state(participant_id, condition):
    state = {
        "participant_id": participant_id,
        "condition": condition,
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "index": 0,
        "mastery": {kc: START_MASTERY for kc in kc_order},
        "current": None,
        "practice_done": False,
        "log": [],
    }
    if condition == "random":
        n = min(N_RANDOM_MISTAKES, len(question_order))
        state["random_plan"] = sorted(random.sample(question_order, n),
                                      key=lambda q: question_order.index(q))
    save_state(state)
    return state


def load_state():
    with open(STATE_PATH) as f:
        return json.load(f)


def save_state(state):
    tmp = STATE_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    os.replace(tmp, STATE_PATH)


def clear_state():
    if os.path.exists(STATE_PATH):
        os.remove(STATE_PATH)


# ------------------------------------------------------------ selection logic

def should_fire(state, question_id):
    if state["condition"] == "random":
        return question_id in state.get("random_plan", [])
    mastery = state["mastery"]
    kc = question_bank[question_id]["kc"]
    idx = kc_order.index(kc)
    if not all(mastery[p] > PREREQ_THRESHOLD for p in kc_order[:idx]):
        return False
    return ZPD_LOW <= mastery[kc] <= ZPD_HIGH


def open_question(state, question_id):
    entry = question_bank[question_id]
    fires = should_fire(state, question_id)
    state["current"] = {
        "id": question_id,
        "kc": entry["kc"],
        "fires": fires,
        "line": entry["line"] if fires else None,
        "mastery_before": dict(state["mastery"]),
        "opened_at": datetime.now().isoformat(timespec="seconds"),
    }
    save_state(state)
    return state["current"]


def open_practice(state):
    state["current"] = {
        "id": "PRACTICE", "kc": None, "fires": True,
        "line": PRACTICE["line"], "mastery_before": dict(state["mastery"]),
        "opened_at": datetime.now().isoformat(timespec="seconds"), "practice": True,
    }
    save_state(state)
    return state["current"]


def end_practice(state):
    state["current"] = None
    state["practice_done"] = True
    save_state(state)


# ----------------------------------------------------------- mastery updating

def update_mastery(state, response):
    """response: 'correct' | 'wrong' | 'dontknow'. Four-cell logic."""
    current = state["current"]
    kc = current["kc"]
    before = state["mastery"][kc]

    if response == "dontknow":
        judgement = None
        after = before
    else:
        said_wrong = (response == "wrong")
        judgement = (said_wrong == current["fires"])
        after = (min(1.0, before + UPDATE_RATE) if judgement
                 else max(0.0, before - UPDATE_RATE))

    state["mastery"][kc] = round(after, 4)
    state["log"].append({
        "question_id": current["id"],
        "kc": kc,
        "mistake_fired": current["fires"],
        "response": response,
        "judgement_correct": judgement,
        "mastery_before": round(before, 4),
        "mastery_after": round(after, 4),
        "opened_at": current["opened_at"],
        "answered_at": datetime.now().isoformat(timespec="seconds"),
    })
    state["index"] += 1
    state["current"] = None
    save_state(state)
    return kc, before, after


def undo_last(state):
    if not state["log"]:
        return None
    entry = state["log"].pop()
    state["mastery"][entry["kc"]] = entry["mastery_before"]
    state["index"] = max(0, state["index"] - 1)
    state["current"] = None
    save_state(state)
    return entry


# --------------------------------------------------------------- archiving

def participant_dir(participant_id):
    d = os.path.join(DATA_DIR, participant_id)
    os.makedirs(d, exist_ok=True)
    return d


def archive_session(state, move_audio=True):
    pid = state["participant_id"]
    d = participant_dir(pid)

    csv_path = os.path.join(d, f"log_{pid}.csv")
    if state["log"]:
        fields = list(state["log"][0].keys())
        with open(csv_path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["participant_id", "condition"] + fields)
            w.writeheader()
            for row in state["log"]:
                w.writerow({"participant_id": pid,
                            "condition": state["condition"], **row})

    with open(os.path.join(d, f"state_{pid}.json"), "w") as f:
        json.dump(state, f, indent=2)

    if move_audio:
        audio = state.get("audio_path")
        if audio and os.path.exists(audio):
            dest = os.path.join(d, os.path.basename(audio))
            if os.path.abspath(audio) != os.path.abspath(dest):
                shutil.move(audio, dest)
                state["audio_path"] = dest

    return d