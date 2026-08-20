"""ZPD-calibrated error generation — core logic.

State lives in a JSON file on disk so two processes can share it: the Flask
trial app (which serves questions and records judgements) and the Reachy
conversation app (which reads what to say). The trial app is the only writer;
the robot tool only ever reads.

Completed sessions are archived to data/<participant_id>/.
"""

import csv
import json
import os
import random
import shutil
from datetime import datetime

# ---------------------------------------------------------------- parameters

START_MASTERY = 0.5        # no pretest: everyone starts neutral
UPDATE_RATE = 0.15         # hand-set, not fitted
PREREQ_THRESHOLD = 0.45    # below start, so the gate opens and closes on evidence
ZPD_LOW, ZPD_HIGH = 0.3, 0.7
N_RANDOM_MISTAKES = 7      # control condition: fixed count, roughly half

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))

STATE_PATH = os.path.join(HERE, "session_state.json")   # live, shared
DATA_DIR = os.path.join(REPO, "data")                    # archived sessions

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
# All items are from published instruments. Copy the exact wording into "text"
# from the cited source — do not paraphrase, because the calibration figures
# only hold for the original phrasing.
#
# CPR = Diaz & Batanero (2009), Appendix A:
#   https://www.iejme.com/download/university-students-knowledge-and-biases-in-
#   conditional-probability-reasoning.pdf
#
# preflight.py will list any question still missing its text.

question_bank = {
    # ---- KC1: probability foundations ----
    "Q1": {
        "kc": "KC1_foundations",
        "source": "Kahneman & Tversky (1973) — engineer/lawyer",
        "calibration": "responses cluster near 90% despite the 30% base rate",
        "correct": "30% (the base rate)",
        "text": "A panel of psychologists interviewed 30 engineers and 70 lawyers, all successful in their fields, and wrote a short description of each one. Here is one of those 100 descriptions, chosen at random. Jack is a 45-year-old man. He is married and has four children. He is generally conservative, careful, and ambitious. He shows no interest in political and social issues and spends most of his free time on his many hobbies, which include home carpentry, sailing, and mathematical puzzles. What is the probability that Jack is one of the 30 engineers?",
        "line": "He sounds just like an engineer — home carpentry, sailing, mathematical puzzles. I'd say around 90%.",
        "mistake_type": "base rate neglect (judgment form)",
    },
    "Q2": {
        "kc": "KC1_foundations",
        "source": "CPR Item 6 — tennis conjunction",
        "calibration": "21% correct without instruction, 24% after",
        "correct": "(a) winning the first set is more likely",
        "text": "Suppose a tennis player reaches the Roland Garros final in 2005. He has to win 3 out of 5 sets to win the final. Which of the following two events is more likely or are they all equally likely? a. The player will win the first set. b. The player will win the first set but lose the match. c. Both events a. and b. are equally likely.",
        "line": "I think the second one is more likely — winning the first set but then losing the match.",
        "mistake_type": "conjunction fallacy",
    },
    "Q3": {
        "kc": "KC1_foundations",
        "source": "CPR Item 15 — die, independence",
        "calibration": "35% correct without instruction, 60% after",
        "correct": "1/2",
        "text": "A person throws a die and writes down the result (odd or even). It is a fair die (that is, all the numbers are equally likely). These are the results after 15 throws: Odd, even, even, odd, odd, even, odd, odd, odd, odd, even, even, odd, odd, odd. The person throws once more. What is the probability of getting an odd number this time?", 
        "line": "There have been a lot of odd results already, so an even number is due. I'd say the chance of an odd number is lower now — maybe 5 out of 15.",
        "mistake_type": "gambler's fallacy",
    },

    # ---- KC2: conditional probability ----
    "Q4": {
        "kc": "KC2_conditional",
        "source": "CPR Item 7 (Pollatsek et al. 1987) — cancer test",
        "calibration": "35% correct without instruction, 35% after (no improvement)",
        "correct": "(b) a positive test given the person has cancer",
        "text": "A cancer test is administered to all the residents in a large city. A positive result is indicative of cancer and a negative result of no cancer. Which of the following results is more likely or are they all equally likely? a. A person has in fact cancer supposed that he got a positive result. b. To have a positive test supposed that the person has cancer. c. The two events are equally likely." ,   
        "line": "I think those two are equally likely, since they're both about the same test and the same disease.",
        "mistake_type": "fallacy of the transposed conditional",
    },
    "Q5": {
        "kc": "KC2_conditional",
        "source": "CPR Item 9b (Falk 1986) — marbles, backward",
        "calibration": "37% correct without instruction, 25% after (worse after teaching)",
        "correct": "1/3",
        "text": "Two black and two white marbles are put in an urn. We pick a marble from the urn. Then, without putting it back into the urn, we pick a second marble at random. If the second marble is white, what is the probability that the first marble is white? i. 1/3 ii. Cannot be computed iii. 1/6 iv. 1/2" ,
        "line": "I'd say 1/2. The first marble was already drawn before we knew anything about the second, so the second draw can't change it.",
        "mistake_type": "fallacy of the time axis",
    },
    "Q6": {
        "kc": "KC2_conditional",
        "source": "CPR Item 4 — four lamps, dependence",
        "calibration": "77% correct without instruction, 89% after",
        "correct": "(b) the second lamp is most likely to be correct",
        "text": "There are four lamps in a box, two of which are defective. We pick up two lamps at random from the box, one after the other, without replacement. Given that the first lamp is defective, which answer is true? a. The second lamp is more likely to be defective. b. The second lamp is most likely to be correct. c. The probabilities for the second lamp being either correct or defective are the same.", 
        "line": "I think the probabilities are the same either way — taking one lamp out doesn't change what the second one is.",
        "mistake_type": "failure to restrict the sample space",
    },

    # ---- KC3: joint probability and the product rule ----
    "Q7": {
        "kc": "KC3_joint",
        "source": "CPR Item 17 — lying, product rule (dependent)",
        "calibration": "24% correct without instruction, 62% after",
        "correct": "0.91 x 0.36 = 0.3276",
        "text": "According to a recent survey, 91% of the population in a city do lie and 36% of those lie about important matters. If we pick a person at random from this city, what is the probability that the person lies about important matters? ",
        "line": "If I divide 0.36 by 0.91, I get about 0.40, so the answer is 0.40.",
        "mistake_type": "conditional computed where a joint is required",
    },
    "Q8": {
        "kc": "KC3_joint",
        "source": "CPR Item 16 — maths/English, product rule (independent)",
        "calibration": "26% correct without instruction, 49% after",
        "correct": "0.8 x 0.7 = 0.56",
        "text": "A group of students in a school take a test in mathematics and one in English. 80% of the students pass the mathematics test and 70% of the students pass the English test. Assuming that students’ scores on the two tests are independent, what is the probability that a student passes both tests (mathematics and English)?",
        "line": "I'd add them together — 80 out of 100 plus 70 out of 100, so 150 out of 100.",
        "mistake_type": "addition rule substituted for the product rule",
    },
    "Q9": {
        "kc": "KC3_joint",
        "source": "CPR Item 10 — urn, joint probability in a diachronic setting",
        "calibration": "62% correct without instruction, 76% after",
        "correct": "(c) the two events are equally likely",
        "text": "An urn contains one blue and two red marbles. We pick two marbles at random, one after the other without replacement. Which of the events below is more likely or are they equally likely? a. Getting two red marbles. b. The first marble is red and the second is blue c. The two events a) and b) are equally likely.", 
        "line": "I think getting two red is more likely, since there are two red marbles and only one blue.",
        "mistake_type": "equiprobability bias",
    },

    # ---- KC4: total probability ----
    "Q10": {
        "kc": "KC4_total_prob",
        "source": "CPR Item 14 — smokers by gender",
        "calibration": "18% correct without instruction, 69% after (largest instructional gain)",
        "correct": "0.6 x 0.5 + 0.4 x 0.25 = 0.4",
        "text": "60% of the population in a city are men, 40% women. 50% of the men and 25% of the women smoke. We select a person from the city at random; what is the probability that this person is a smoker?",
        "line": "So 50 men smoke and 25 women smoke, that's 75 out of 200 people, so about 37.5%.",
        "mistake_type": "denominator neglect — branches unweighted",
    },
    "Q11": {
        "kc": "KC4_total_prob",
        "source": "CPR Item 5 (Eddy 1982) — mammogram, conditional from joint and marginal",
        "calibration": "37% correct without instruction, 48% after",
        "correct": "0.8 / 10.3 = 7.77%",
        "text": "10.3 % of women in a given city have a positive mammogram. The probability that a woman in this city has both positive mammogram and breast cancer is 0.8%. A mammogram given to a woman taken at random in this population was positive. What is the probability that she actually has breast cancer? a. 7.77%, from 0.8 divided by 10.3 b. 8.24%, from 10.3 times 0.8 c. 0.8%",
        "line": "I'd multiply them — 10.3 times 0.8 gives 8.24%.",
        "mistake_type": "product substituted for the ratio",
    },

    # ---- KC5: Bayesian updating ----
    "Q12": {
        "kc": "KC5_updating",
        "source": "CPR Item 2 (Tversky & Kahneman 1982) — blue taxi",
        "calibration": "33% correct without instruction, 53% after",
        "correct": "(d) — approximately 41%",
        "text": "A witness sees a crime involving a taxi in a city. The witness says that the taxi is blue. It is known from previous research that witnesses are correct 80% of the time when making such statements. The police also know that 15% of the taxis in the city are blue, the other 85% being green. What is the probability that a blue taxi was involved in the crime? a. 80 out of 100 b. 15 out of 100 c. 15 out of 100, times 80 out of 100 d. a calculation combining the base rate with the witness reliability",
        "line": "I think it's 80 out of 100, since that's how often the witness gets the colour right.",
        "mistake_type": "base rate fallacy",
    },
    "Q13": {
        "kc": "KC5_updating",
        "source": "CPR Item 18 (Totohasina 1992) — two machines",
        "calibration": "4% correct without instruction, 50% after (most discriminating item)",
        "correct": "0.769",
        "text": "Two machines M1 and M2 produce balls. Machine M1 produces 40 % and M2 60% of balls. 5% of the balls produced by M1 and 1% of those produced by M2 are defective. We take a ball at random and it is defective. What is the probability that that ball was produced by machine M1?",  
        "line": "I think it's 5%, since that's how often machine M1 produces a defective ball.",
        "mistake_type": "inverse conditional reported as the posterior",
    },
    "Q14": {
        "kc": "KC5_updating",
        "source": "Casscells, Schoenberger & Grayboys (1978) — rare disease",
        "calibration": "Casscells et al. report ~18% correct among physicians on the original item; wording here is paraphrased",
        "correct": "~2%",
        "text": "If a disease has a prevalence of 1 in 1000, and a particular test for it has a false positive rate of 5%, and one random person tests positive for the disease, what is the likelihood that they have the disease?",
        "line": "I think the answer is 95%, since the test only gives a false positive 5% of the time.",
        "mistake_type": "base rate neglect (computational form)",
    },
}

question_order = ["Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7",
                  "Q8", "Q9", "Q10", "Q11", "Q12", "Q13", "Q14"]


# ------------------------------------------------------------------ state I/O

def new_state(participant_id, condition):
    state = {
        "participant_id": participant_id,
        "condition": condition,               # "zpd" or "random"
        "started_at": datetime.now().isoformat(timespec="seconds"),
        "index": 0,
        "mastery": {kc: START_MASTERY for kc in kc_order},
        "current": None,
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
    os.replace(tmp, STATE_PATH)      # atomic: the reader never sees a half file


def clear_state():
    if os.path.exists(STATE_PATH):
        os.remove(STATE_PATH)


# ------------------------------------------------------------ selection logic

def should_fire(state, question_id):
    """Decide whether this question gets a scripted mistake."""
    if state["condition"] == "random":
        return question_id in state.get("random_plan", [])

    mastery = state["mastery"]
    kc = question_bank[question_id]["kc"]
    idx = kc_order.index(kc)

    if not all(mastery[p] > PREREQ_THRESHOLD for p in kc_order[:idx]):
        return False
    return ZPD_LOW <= mastery[kc] <= ZPD_HIGH


def open_question(state, question_id):
    """Fix the decision now and write it, so the robot tool only reads."""
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

    response: "correct" | "wrong" | "dontknow"

    Four-cell logic — mastery reflects whether they can tell sound reasoning
    from unsound, so every question yields evidence, not only the ones where a
    mistake fired:

        robot wrong  + said wrong    -> up      (caught it)
        robot wrong  + said correct  -> down    (missed it)
        robot right  + said correct  -> up      (recognised sound reasoning)
        robot right  + said wrong    -> down    (false alarm)

    "dontknow" is neutral.
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


def undo_last(state):
    """Roll back the most recent answered question. Operator use only."""
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


def archive_session(state):
    """Write the CSV, snapshot the state, move any audio into data/<pid>/."""
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

    audio = state.get("audio_path")
    if audio and os.path.exists(audio):
        dest = os.path.join(d, os.path.basename(audio))
        if os.path.abspath(audio) != os.path.abspath(dest):
            shutil.move(audio, dest)
            state["audio_path"] = dest

    return d