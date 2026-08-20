"""Preflight check. Run before every session.

    python preflight.py

Verifies the algorithm and the robot tool both load and behave, without needing
the robot or the conversation app. If the tool check fails, applying the
profile will time out.
"""

import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "src", "reachy_mini_conversation_app", "tools"))

ok = True


def check(label, fn):
    global ok
    try:
        r = fn()
        print(f"  PASS  {label}" + (f" — {r}" if r else ""))
    except Exception as e:
        ok = False
        print(f"  FAIL  {label}")
        print("        " + "".join(
            traceback.format_exception_only(type(e), e)).strip())


print("\n1. Core algorithm")
import bayes_algorithm as ba  # noqa: E402


def _bank():
    missing = [q for q in ba.question_order if q not in ba.question_bank]
    if missing:
        raise KeyError(f"question_order references missing: {missing}")
    extra = set(ba.question_bank) - set(ba.question_order)
    if extra:
        raise KeyError(f"questions never shown: {sorted(extra)}")
    return f"{len(ba.question_bank)} questions"


def _kcs():
    from collections import Counter
    c = Counter(v["kc"] for v in ba.question_bank.values())
    unknown = set(c) - set(ba.kc_order)
    if unknown:
        raise KeyError(f"unknown KCs: {unknown}")
    empty = [k for k in ba.kc_order if c[k] == 0]
    if empty:
        raise ValueError(f"KCs with no questions: {empty}")
    return ", ".join(f"{k.split('_')[0]}={c[k]}" for k in ba.kc_order)


def _lines():
    for qid, e in ba.question_bank.items():
        if not e.get("line"):
            raise KeyError(f"{qid} has no scripted mistake line")
    return "every question has a scripted line"


def _texts():
    missing = [q for q, e in ba.question_bank.items() if not e.get("text")]
    if missing:
        raise ValueError(f"{len(missing)} need text pasted: {', '.join(missing)}")
    return "all question text present"


check("question bank consistent", _bank)
check("KC assignments valid", _kcs)
check("scripted lines present", _lines)
check("question text present", _texts)


print("\n2. Robot tool")


def _imports():
    import decide_response
    return decide_response.DecideResponse.name


def _schema():
    from decide_response import DecideResponse
    props = DecideResponse.parameters_schema.get("properties")
    if not props:
        raise ValueError("empty 'properties' — the realtime API may reject this")
    return f"{len(props)} parameter(s)"


check("decide_response imports", _imports)
check("schema is non-empty", _schema)


print("\n3. Dry run")


def _zpd():
    import random
    random.seed(0)
    s = ba.new_state("PREFLIGHT", "zpd")
    fired = 0
    for qid in ba.question_order:
        cur = ba.open_question(s, qid)
        if cur["fires"]:
            fired += 1
            if not cur["line"]:
                raise ValueError(f"{qid} fires with no line")
        ba.update_mastery(s, "wrong" if cur["fires"] else "correct")
    if len(s["log"]) != len(ba.question_order):
        raise ValueError("log length mismatch")
    ba.clear_state()
    return f"{fired}/{len(ba.question_order)} mistakes"


def _random():
    s = ba.new_state("PREFLIGHT", "random")
    n = len(s["random_plan"])
    ba.clear_state()
    if n != ba.N_RANDOM_MISTAKES:
        raise ValueError(f"plan has {n}, expected {ba.N_RANDOM_MISTAKES}")
    return f"{n} questions in plan"


def _undo():
    s = ba.new_state("PREFLIGHT", "zpd")
    qid = ba.question_order[0]
    ba.open_question(s, qid)
    kc = ba.question_bank[qid]["kc"]
    before = s["mastery"][kc]
    ba.update_mastery(s, "wrong")
    ba.undo_last(s)
    if s["mastery"][kc] != before or s["index"] != 0:
        raise ValueError("undo did not restore state")
    ba.clear_state()
    return "rolls back cleanly"


check("zpd condition end to end", _zpd)
check("random condition builds a plan", _random)
check("undo restores mastery", _undo)


print("\n4. Environment")
try:
    from recorder import BACKEND
    print(f"       audio backend     : {BACKEND or 'NONE — use a phone'}")
except Exception as e:
    print(f"       audio backend     : recorder.py failed to load ({e})")

print(f"       random mistakes   : {ba.N_RANDOM_MISTAKES}")
print(f"       start mastery     : {ba.START_MASTERY}")
print(f"       update rate       : {ba.UPDATE_RATE}")
print(f"       prereq threshold  : {ba.PREREQ_THRESHOLD}")
print(f"       ZPD band          : {ba.ZPD_LOW}-{ba.ZPD_HIGH}")
print(f"       data directory    : {ba.DATA_DIR}")

stale = os.path.exists(ba.STATE_PATH)
print(f"       stale state file  : {'YES — clear it before starting' if stale else 'none'}")

print("\n" + ("ALL CHECKS PASSED" if ok else "SOMETHING FAILED — see above") + "\n")
sys.exit(0 if ok else 1)