import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from reachy_mini_conversation_app.tools.bayes_algorithm import (
    mistake_script, pick_mistake, fake_mastery_for_question,
)

for i in range(1, 11):
    qid = f"Q{i}"
    entry = mistake_script[qid]
    mastery = fake_mastery_for_question(qid)
    result = pick_mistake(mastery)

    if result is not None and result[0] == entry["kc"]:
        print(f"{qid}: MISTAKE | {entry['line'][:60]}")
    else:
        print(f"{qid}: correct")