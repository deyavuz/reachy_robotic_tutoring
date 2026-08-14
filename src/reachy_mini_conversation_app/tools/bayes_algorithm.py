import random

# The 5 knowledge components, in prerequisite order
kc_order = ["KC1_foundations", "KC2_conditional", "KC3_joint",
            "KC4_total_prob", "KC5_updating"]

# Your finalized scripted wrong answers, one per question, from the spreadsheet
mistake_script = {
    "Q1": {"kc": "KC1_foundations",
           "text": "Out of 100 people, 30 are engineers and 70 are lawyers. Here's a description of one of them, Dick: he's married, has no children, is good at his job, and is well-liked by colleagues. What's the chance Dick is one of the engineers?",
           "line": "Since I don't have any information about Dick's background, he could be either a lawyer or an engineer, so I will go with 50%"},

    "Q2": {"kc": "KC1_foundations",
           "text": "A tennis player is in a final. Which is more likely: that he wins the first set, or that he wins the first set but then loses the whole match?",
           "line": "I think the story about winning the first set and losing the second seems more likely."},

    "Q3": {"kc": "KC2_conditional",
           "text": "Compare these two things: the chance you have cancer, given that you tested positive, versus the chance you'd test positive, given that you have cancer. Are these the same number, or different?",
           "line": "I think those two probabilities are actually the same, since they're based on the same test results."},

    "Q4": {"kc": "KC2_conditional",
           "text": "There are two black and two white marbles in a bag. You draw one without looking and set it aside. You draw a second one, and it's white. What's the chance the first marble you drew, still unseen, was also white?",
           "line": "I guess it's 1/2, since you can't go back in time and change the probability. It will always be 50/50 for the first draw, even if we know the second draw is white."},

    "Q5": {"kc": "KC3_joint",
           "text": "91% of people in a city admit to lying sometimes. Of those liars, 36% say they lie about important things. What fraction of the whole city lies about important things?",
           "line": "If I divide 0.36 by 0.91, I get 0.40, so the answer is 0.40!"},

    "Q6": {"kc": "KC4_total_prob",
           "text": "In a city, 60% of people are men and 40% are women. 50% of men smoke, and 25% of women smoke. What fraction of the whole city smokes?",
           "line": "I think it's 50%, since that's the smoking rate for men."},

    "Q7": {"kc": "KC5_updating",
           "text": "A disease affects 1 in 1000 people. A test always catches it when someone has the disease, but also gives a false positive 5% of the time on healthy people. You test positive. What's the real chance you have the disease?",
           "line": "I think the answer is 95%, since the test only gives false positives 5% of the time."},

    "Q8": {"kc": "KC5_updating",
           "text": "Machine 1 makes 40% of all balls produced, Machine 2 makes 60%. Machine 1's balls are defective 5% of the time, Machine 2's only 1% of the time. You pick a random defective ball. What's the chance it came from Machine 1?",
           "line": "I think it's about 83%, since Machine 1's defect rate is five times higher than Machine 2's. That's 5% vs. 1%."},

    "Q9": {"kc": "KC5_updating",
           "text": "A witness says the taxi involved in an incident was blue. Witnesses like this are right about the colour 80% of the time. Only 15% of taxis in the city are actually blue. What's the real chance the taxi was blue?",
           "line": "I think it's about 80%, that's how reliable the driver said they were"},

    "Q10": {"kc": "KC5_updating",
            "text": "1% of women this age have breast cancer. If a woman has cancer, the test catches it 80% of the time. If she doesn't have cancer, the test still falsely says positive 9.6% of the time. A woman tests positive. What's the real chance she has cancer?",
            "line": "I think it's 80%, since that's the test's accuracy rate."},
}

def pick_mistake(mastery):
    eligible = []
    for i, kc in enumerate(kc_order):
        prereqs = kc_order[:i]
        if all(mastery[p] > 0.7 for p in prereqs):
            eligible.append(kc)

    zpd_candidates = [kc for kc in eligible if 0.4 <= mastery[kc] <= 0.7]

    if not zpd_candidates:
        return None

    chosen = next(kc for kc in kc_order if kc in zpd_candidates)
    return (chosen, None)

def fake_mastery_generator_progressive(kc_order, question_number, total_questions=10):
    progress = question_number / total_questions
    mastery = {}
    for kc in kc_order:
        base = progress + random.uniform(-0.15, 0.15)
        mastery[kc] = round(min(max(base, 0), 1), 2)
    return mastery