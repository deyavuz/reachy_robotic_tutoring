"""ZPD-calibrated error generation — core logic.

State is held in a JSON file on disk so that two processes can share it:
the Flask trial app (which serves questions and collects judgements) and
the Reachy conversation app (which reads what to say). The trial app is
the only writer; the robot tool only reads.
"""

import json
import os
import random
from datetime import datetime

# ---------------------------------------------------------------- parameters

START_MASTERY = 0.5        # no pretest: everyone starts neutral
UPDATE_RATE = 0.15         # hand-set, not fitted
PREREQ_THRESHOLD = 0.45    # below start, so the gate opens and closes on evidence
ZPD_LOW, ZPD_HIGH = 0.3, 0.7
N_RANDOM_MISTAKES = 7      # control condition: fixed count, ~half of 15

STATE_PATH = os.path.join(os.path.dirname(__file__), "session_state.json")

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
# Target layout is 3 questions per KC = 15 total.
# Five slots still need authoring — marked TODO below.
# Each entry needs: kc, text (read aloud by the participant), line (the
# robot's scripted wrong answer, said verbatim when a mistake fires).

question_bank = {
    "Q1": {
        "kc": "KC1_foundations",
        "text": "Out of 100 people, 30 are engineers and 70 are lawyers. Here's a description of one of them, Dick: he's married, has no children, is good at his job, and is well-liked by colleagues. What's the chance Dick is one of the engineers?",
        "line": "Since I don't have any information about Dick's background, he could be either a lawyer or an engineer, so I will go with 50%.",
    },
    "Q2": {
        "kc": "KC1_foundations",
        "text": "A tennis player is in a final. Which is more likely: that he wins the first set, or that he wins the first set but then loses the whole match?",
        "line": "I think the story about winning the first set and losing the second seems more likely.",
    },
    "Q3": {
        "kc": "KC1_foundations",
        "text": "Sam is 34, studied environmental science at university, and volunteers at weekends. Which is more likely: that Sam works for a company, or that Sam works for a company and cycles to work?",
        "line": "I think the second one is more likely — working for a company and cycling to work fits the description of Sam much better.",
    },

    "Q4": {
        "kc": "KC2_conditional",
        "text": "Compare these two things: the chance you have cancer, given that you tested positive, versus the chance you'd test positive, given that you have cancer. Are these the same number, or different?",
        "line": "I think those two probabilities are actually the same, since they're based on the same test results.",
    },
    "Q5": {
        "kc": "KC2_conditional",
        "text": "There are two black and two white marbles in a bag. You draw one without looking and set it aside. You draw a second one, and it's white. What's the chance the first marble you drew, still unseen, was also white?",
        "line": "I guess it's 1/2, since you can't go back in time and change the probability. It will always be 50/50 for the first draw, even if we know the second draw is white.",
    },
    "Q6": {
        "kc": "KC2_conditional",
        "text": "In a school, 80% of the students who play an instrument also sing in the choir. Does that mean 80% of the choir members play an instrument?",
        "line": "Yes, it should be 80% either way, since it's the same two groups being compared.",
    },

    "Q7": {
        "kc": "KC3_joint",
        "text": "91% of people in a city admit to lying sometimes. Of those liars, 36% say they lie about important things. What fraction of the whole city lies about important things?",
        "line": "If I divide 0.36 by 0.91, I get 0.40, so the answer is 0.40.",
    },
    "Q8": {
        "kc": "KC3_joint",
        "text": "70% of commuters in a city use public transport. Of those who use public transport, 40% take the train. What fraction of all commuters take the train?",
        "line": "If I divide 0.40 by 0.70, I get about 0.57, so roughly 57%.",
    },
    "Q9": {
        "kc": "KC3_joint",
        "text": "A factory runs two quality checks in sequence. 90% of items pass the first check. Of the items that pass the first check, 80% then pass the second. What fraction of items pass both checks?",
        "line": "I think it's 80%, since that's the pass rate for the second check.",
    },

    "Q10": {
        "kc": "KC4_total_prob",
        "text": "In a city, 60% of people are men and 40% are women. 50% of men smoke, and 25% of women smoke. What fraction of the whole city smokes?",
        "line": "I think it's 50%, since that's the smoking rate for men.",
    },
    "Q11": {
        "kc": "KC4_total_prob",
        "text": "A university has 70% undergraduates and 30% postgraduates. 20% of the undergraduates live on campus, and 60% of the postgraduates do. What fraction of all students live on campus?",
        "line": "I think it's 40%, since that's halfway between 20% and 60%.",
    },
    "Q12": {
        "kc": "KC4_total_prob",
        "text": "A shop sells two brands of battery. Brand A is 80% of the stock and fails 2% of the time. Brand B is 20% of the stock and fails 10% of the time. What fraction of all batteries sold fail?",
        "line": "I think it's 2%, since that's Brand A's failure rate and most of the batteries are Brand A.",
    },

    "Q13": {
        "kc": "KC5_updating",
        "text": "A disease affects 1 in 1000 people. A test always catches it when someone has the disease, but also gives a false positive 5% of the time on healthy people. You test positive. What's the real chance you have the disease?",
        "line": "I think the answer is 95%, since the test only gives false positives 5% of the time.",
    },
    "Q14": {
        "kc": "KC5_updating",
        "text": "A witness says the taxi involved in an incident was blue. Witnesses like this are right about the colour 80% of the time. Only 15% of taxis in the city are actually blue. What's the real chance the taxi was blue?",
        "line": "I think it's about 80%, since that's how reliable the witness is.",
    },
    "Q15": {
        "kc": "KC5_updating",
        "text": "1% of women this age have breast cancer. If a woman has cancer, the test catches it 80% of the time. If she doesn't have cancer, the test still falsely says positive 9.6% of the time. A woman tests positive. What's the real chance she has cancer?",
        "line": "I think it's 80%, since that's the test's accuracy rate.",
    },
}

# Presentation order. Edit here if you want KCs interleaved rather than blocked.
question_order = [q for q in sorted(question_bank, key=lambda x: int(x[1:]))]


# ------------------------------------------------------------------ state I/O

def new_state(participant_id, condition):
    state = {
        "participant_id": participant_id,
        "condition": condition,               # "zpd" or "random"
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "index": 0,                            # how many questions completed
        "mastery": {kc: START_MASTERY for kc in kc_order},
        "current": None,                       # the live question, or None
        "log": [],
    }
    if condition == "random":
        n = min(N_RANDOM_MISTAKES, len(question_order))
        state["random_plan"] = sorted(random.sample(question_order, n))
    save_state(state)
    return state


def load_state():
    with open(STATE_PATH) as f:
        return json.load(f)


def save_state(state):
    with open(STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)


# ------------------------------------------------------------ selection logic

def should_fire(state, question_id):
    """Decide whether this question gets a scripted mistake."""
    if state["condition"] == "random":
        return question_id in state["random_plan"]

    mastery = state["mastery"]
    kc = question_bank[question_id]["kc"]
    idx = kc_order.index(kc)

    # prerequisite gate: every earlier KC must be above threshold
    if not all(mastery[p] > PREREQ_THRESHOLD for p in kc_order[:idx]):
        return False

    # ZPD band
    return ZPD_LOW <= mastery[kc] <= ZPD_HIGH


def open_question(state, question_id):
    """Called when the participant is about to start the conversation.

    Fixes the decision now and writes it to state, so the robot tool only
    ever reads — no counter, no chance of the two drifting apart.
    """
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


# ----------------------------------------------------------- mastery updating

def update_mastery(state, response):
    """Apply the participant's judgement.

    response is one of: "correct", "wrong", "dontknow".

    Four-cell logic — mastery reflects whether they can tell sound reasoning
    from unsound, so every question yields evidence, not only the ones where
    a mistake fired:

        robot wrong  + said wrong    -> up      (caught it)
        robot wrong  + said correct  -> down    (missed it)
        robot right  + said correct  -> up      (recognised sound reasoning)
        robot right  + said wrong    -> down    (false alarm)

    "dontknow" is neutral: no change.
    """
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


def export_log_csv(state, path):
    import csv
    if not state["log"]:
        return
    fields = list(state["log"][0].keys())
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["participant_id", "condition"] + fields)
        w.writeheader()
        for row in state["log"]:
            w.writerow({"participant_id": state["participant_id"],
                        "condition": state["condition"], **row})