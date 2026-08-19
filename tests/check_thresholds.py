import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from itertools import product
from reachy_mini_conversation_app.tools.bayes_algorithm import plan_session, kc_order

scores = [0.0, 0.33, 0.67, 1.0]
counts = {}

for combo in product(scores, repeat=4):
    mastery = dict(zip(kc_order, combo))
    n = len(plan_session(mastery, condition="zpd"))
    counts[n] = counts.get(n, 0) + 1

for n in sorted(counts):
    print(f"{n} mistakes: {counts[n]} of 256 profiles ({counts[n]/256:.0%})")