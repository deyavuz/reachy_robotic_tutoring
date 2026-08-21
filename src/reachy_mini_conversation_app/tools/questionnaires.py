"""Pre- and post-task questionnaire definitions, kept separate from the trial
logic so the wording can be edited without touching the flow.

Each item: (key, prompt, kind, options-or-None).
kind: "radio" (pick one), "scale5" (1-5 Likert), "text" (free text),
      "number" (short numeric/text), "yesno_text" (No / Yes+describe).
"""

PRE_ITEMS = [
    ("english_fluent", "Are you fluent in English?", "radio", ["Yes", "No"]),
    ("can_consent", "Are you able to provide informed consent for yourself?", "radio", ["Yes", "No"]),
    ("age", "Please provide your age:", "number", None),
    ("role", "Current role:", "radio", [
        "Undergraduate student", "Postgraduate student", "Academic or research staff",
        "Professional or administrative staff", "Employed outside university",
        "Not currently employed or studying", "Other", "Prefer not to say"]),
    ("education", "Highest level of education completed:", "radio", [
        "Secondary school or equivalent", "Undergraduate degree or equivalent",
        "Postgraduate degree or equivalent", "Other", "Prefer not to say"]),
    ("fam_prob", "How familiar are you with probability or statistics?", "radio", [
        "Not at all familiar", "Slightly familiar", "Moderately familiar",
        "Very familiar", "Extremely familiar"]),
    ("fam_bayes", "How familiar are you with Bayes' theorem?", "radio", [
        "Not at all familiar", "Slightly familiar", "Moderately familiar",
        "Very familiar", "Extremely familiar"]),
    ("comfort_aloud", "How comfortable are you explaining your reasoning aloud?", "radio", [
        "Not at all comfortable", "Slightly comfortable", "Moderately comfortable",
        "Very comfortable", "Extremely comfortable"]),
    ("pre_comments", "Is there anything else you would like the researcher to know before the task begins?", "text", None),
]

_SCALE5 = "1 = Strongly disagree · 5 = Strongly agree"

POST_SECTIONS = [
    ("Perceived learning and reflection", _SCALE5, [
        ("learn_familiar", "I feel more familiar with Bayes' theorem after the activity."),
        ("learn_confident", "I feel more confident explaining probability problems after the activity."),
        ("learn_explain", "Teaching the robot encouraged me to explain my thinking more carefully."),
        ("learn_noticed", "The activity helped me notice parts of the problem that I did not fully understand."),
    ]),
    ("Task experience", _SCALE5, [
        ("task_clear", "The instructions were clear."),
        ("task_understandable", "The Bayes' theorem questions were understandable."),
        ("task_manageable", "The task felt manageable."),
        ("task_difficult", "The task felt too difficult."),
        ("task_explain_helped", "Explaining my reasoning helped me think through the problems."),
        ("task_explain_clear", "I felt that I was able to explain my reasoning clearly."),
        ("task_confident", "I felt confident during the task."),
    ]),
    ("Robot interaction", _SCALE5, [
        ("robot_comfortable", "I felt comfortable interacting with the robot."),
        ("robot_prompts_clear", "The robot's prompts were clear."),
        ("robot_prompts_helped", "The robot's prompts helped me explain my reasoning."),
        ("robot_engaging", "The robot made the task more engaging."),
        ("robot_natural", "I found it natural to speak to the robot."),
        ("robot_selfconscious", "I felt self-conscious while speaking to the robot."),
        ("robot_again", "I would be comfortable doing a similar learning activity with a robot again."),
    ]),
    ("Robot errors and correction", _SCALE5, [
        ("err_noticed", "I noticed at least one moment where the robot's response seemed incorrect or incomplete."),
        ("err_identified", "When the robot made an error, I felt able to identify what was wrong."),
        ("err_clarified", "Correcting the robot helped me clarify my own understanding."),
        ("err_confident_explain", "I felt confident explaining the correct answer to the robot after it made a mistake."),
        ("err_think_carefully", "The robot's errors made me think more carefully about the problem."),
        ("err_useful", "I found it useful to have to correct the robot."),
        ("err_confusing", "The robot's errors felt confusing rather than helpful."),
        ("err_appropriate_level", "I felt that the robot's errors were at an appropriate level of difficulty."),
    ]),
    ("Recording and comfort", _SCALE5, [
        ("rec_comfortable", "I felt comfortable with audio being recorded."),
        ("rec_understood", "I understood what data was being collected during the study."),
        ("rec_privacy", "I felt that my privacy was respected during the study."),
    ]),
]

POST_OPEN = [
    ("open_useful", "What did you find most useful or interesting about the activity?", "text"),
    ("open_difficult", "What did you find difficult or confusing?", "text"),
    ("open_approach", "How did interacting with the robot affect the way you approached the task?", "text"),
    ("open_error_response", "When the robot gave an incorrect or incomplete response, how did you respond and how did that feel?", "text"),
    ("open_uncomfortable", "Did any part of the study make you feel uncomfortable?", "yesno_text"),
    ("open_improve", "Do you have any suggestions for improving the study?", "text"),
    ("open_anything", "Is there anything else you would like to add?", "text"),
]
