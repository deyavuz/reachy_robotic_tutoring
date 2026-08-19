import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from itertools import product
from reachy_mini_conversation_app.tools import bayes_algorithm as ba

scores = [0.0, 0.25, 0.5, 0.75, 1.0]
total = len(scores) ** 4

for prereq in [0.6, 0.3, 0.2]:
    for low, high in [(0.3, 0.7), (0.2, 0.8), (0.25, 0.75)]:
        ba.PREREQ_THRESHOLD = prereq
        ba.ZPD_LOW, ba.ZPD_HIGH = low, high

        zero = 0
        kc4_fires = 0
        for combo in product(scores, repeat=4):
            mastery = dict(zip(ba.kc_order, combo))
            fires = ba.plan_session(mastery, condition="zpd")
            if not fires:
                zero += 1
            if "Q7" in fires:
                kc4_fires += 1

        print(f"prereq>{prereq}, band {low}-{high}: "
              f"{zero/total:.0%} get nothing, {kc4_fires/total:.0%} reach Q7-Q10")