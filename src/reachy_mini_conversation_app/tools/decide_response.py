import logging
from typing import Any, Dict
from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies
from .bayes_algorithm import kc_order, mistake_script, pick_mistake, fake_mastery_generator_progressive

logger = logging.getLogger(__name__)


class DecideResponse(Tool):
    """Decide whether to answer a Bayes' theorem study question correctly or with a scripted mistake."""

    name = "decide_response"
    description = (
        "Call this before answering any of the ten Bayes' theorem study questions (Q1 through Q10). "
        "Returns exactly what to say — either an instruction to reason it out correctly, "
        "or an exact pre-scripted line that must be said word for word, with no rephrasing."
    )
    needs_response = True
    parameters_schema = {
        "type": "object",
        "properties": {
            "question_id": {
                "type": "string",
                "description": "The current question's ID, e.g. 'Q1' through 'Q10'.",
            },
        },
        "required": ["question_id"],
    }

async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
    question_id = kwargs.get("question_id")
    logger.info("Tool call: decide_response question_id=%s", question_id)

    entry = mistake_script.get(question_id)
    question_text = entry["text"] if entry else None

    question_number = int(question_id.replace("Q", ""))
    mastery = fake_mastery_generator_progressive(kc_order, question_number=question_number)
    result = pick_mistake(mastery)

    if result is None:
        return {
            "action": "answer_correctly",
            "instruction": "Reason through this question correctly and give the right answer, explaining your steps.",
            "question_text": question_text,
        }

    chosen_kc, _ = result

    if entry and entry["kc"] == chosen_kc:
        return {
            "action": "say_exact_line",
            "instruction": "Say this line exactly, word for word, with no rephrasing:",
            "line": entry["line"],
            "question_text": question_text,
        }

    return {
        "action": "answer_correctly",
        "instruction": "Reason through this question correctly and give the right answer, explaining your steps.",
        "question_text": question_text,
    }