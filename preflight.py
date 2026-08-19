"""Preflight check. Run before every session.

    python preflight.py

Verifies that the algorithm and the robot tool both load and behave, without
needing the robot or the conversation app. If this passes, the tool will at
least load; if it fails, the profile will time out when applied.
"""

import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
TOOLS = os.path.join(HERE, "src", "reachy_mini_conversation_app", "tools")
sys.path.insert(0, TOOLS)

ok = True


def check(label, fn):
    global ok
    try:
        result = fn()
        print(f"  PASS  {label}" + (f" — {result}" if result else ""))
        return True
    except Exception as e:
        ok = False
        print(f"  FAIL  {label}")
        print("        " + "".join(traceback.format_exception_only(type(e), e)).strip())
        return False


print("\n1. Core algorithm")

import bayes_algorithm as ba  # noqa: E402


def _bank():
    n = len(ba.question_bank)
    missing = [q for q in ba.question_order if q not in ba.question_bank]
    if missing:
        raise KeyError(f"question_order references missing questions: {missing}")
    return f"{n} questions, {len(ba.question_order)} in order"


def _kcs():
    from collections import Counter
    c = Counter(v["kc"] for v in ba.question_bank.values())
    unknown = set(c) - set(ba.kc_order)
    if unknown:
        raise KeyError(f"questions reference unknown KCs: {unknown}")
    return ", ".join(f"{k.split('_')[0]}={c[k]}" for k in ba.kc_order)


def _fields():
    for qid, e in ba.question_bank.items():
        for f in ("kc", "text", "line"):
            if not e.get(f):
                raise KeyError(f"{qid} is missing '{f}'")
    return "all questions have kc, text and line"


check("question bank loads", _bank)
check("KC assignments valid", _kcs)
check("no empty fields", _fields)


print("\n2. Robot tool")


def _tool_imports():
    import decide_response
    return decide_response.DecideResponse.name


def _schema():
    from decide_response import DecideResponse
    props = DecideResponse.parameters_schema.get("properties")
    if not props:
        raise ValueError("parameters_schema has empty 'properties' — "
                         "the realtime API may reject this tool")
    return f"{len(props)} parameter(s)"


check("decide_response imports", _tool_imports)
check("schema is non-empty", _schema)


print("\n3. Dry run (zpd condition, simulated participant)")


def _dry():
    import random
    random.seed(0)
    state = ba.new_state("PREFLIGHT", "zpd")
    fired = 0
    for qid in ba.question_order:
        cur = ba.open_question(state, qid)
        if cur["fires"]:
            fired += 1
            if not cur["line"]:
                raise ValueError(f"{qid} fires but has no line")
        resp = "wrong" if cur["fires"] else "correct"
        ba.update_mastery(state, resp)
    if len(state["log"]) != len(ba.question_order):
        raise ValueError("log length does not match question count")
    os.remove(ba.STATE_PATH)
    return f"{fired}/{len(ba.question_order)} mistakes, log complete"


def _dry_random():
    state = ba.new_state("PREFLIGHT", "random")
    n = len(state["random_plan"])
    os.remove(ba.STATE_PATH)
    if n != ba.N_RANDOM_MISTAKES:
        raise ValueError(f"random plan has {n}, expected {ba.N_RANDOM_MISTAKES}")
    return f"random plan has {n} questions"


check("zpd condition runs end to end", _dry)
check("random condition builds a plan", _dry_random)


print("\n4. Settings")
print(f"       random mistakes   : {ba.N_RANDOM_MISTAKES}")
print(f"       start mastery     : {ba.START_MASTERY}")
print(f"       update rate       : {ba.UPDATE_RATE}")
print(f"       prereq threshold  : {ba.PREREQ_THRESHOLD}")
print(f"       ZPD band          : {ba.ZPD_LOW}–{ba.ZPD_HIGH}")

leftover = os.path.exists(ba.STATE_PATH)
print(f"       stale state file  : {'YES — delete before session' if leftover else 'none'}")

print("\n" + ("ALL CHECKS PASSED" if ok else "SOMETHING FAILED — see above") + "\n")
sys.exit(0 if ok else 1)