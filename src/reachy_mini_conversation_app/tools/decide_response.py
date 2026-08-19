"""Reachy tool: tells the robot how to answer the current question.

Design notes, because two of these are deliberate and non-obvious:

1. The import of bayes_algorithm is DEFERRED into the function body. If it
   happened at module level and anything in bayes_algorithm were broken, this
   tool would fail to import, the app would not register it, and applying a
   profile that lists it would time out. Deferring means the tool always loads;
   a broken algorithm degrades to "answer correctly" instead of killing the
   whole profile.

2. The tool BLOCKS while no question is open. The robot cannot speak while
   waiting for a tool result, so this enforces silence between questions
   without relying on the model to follow an instruction.
"""

import asyncio
import logging
import time
from typing import Any, Dict

from reachy_mini_conversation_app.tools.core_tools import Tool, ToolDependencies

logger = logging.getLogger(__name__)

WAIT_TIMEOUT = 12.0        # seconds to wait for a question to open
POLL_INTERVAL = 0.4

ANSWER_CORRECTLY = {
    "action": "answer_correctly",
    "instruction": ("Reason through this question correctly and give the right "
                    "answer, explaining your steps aloud."),
}

STAY_SILENT = {
    "action": "wait",
    "instruction": ("No question is open yet. Say nothing at all. Do not speak, "
                    "do not ask anything, do not fill the silence. Wait for me "
                    "to read the next question aloud."),
}


class DecideResponse(Tool):
    """Decide whether to answer the current question correctly or with a scripted mistake."""

    name = "decide_response"
    description = (
        "Call this immediately after the participant finishes reading a question "
        "aloud, and before giving any answer. Returns either an instruction to "
        "reason the answer out correctly, or an exact pre-scripted line that must "
        "be said word for word with no rephrasing. Never pose questions yourself."
    )
    needs_response = True
    parameters_schema = {
        "type": "object",
        "properties": {
            "spoken_question_number": {
                "type": "integer",
                "description": ("The question number the participant said aloud, "
                                "if you heard one. Used for logging only; pass 0 "
                                "if you did not hear a number."),
            },
        },
        "required": [],
    }

    async def __call__(self, deps: ToolDependencies, **kwargs: Any) -> Dict[str, Any]:
        spoken = kwargs.get("spoken_question_number")

        try:
            from .bayes_algorithm import load_state
        except Exception:
            logger.exception("decide_response: cannot import bayes_algorithm")
            return ANSWER_CORRECTLY

        deadline = time.time() + WAIT_TIMEOUT
        current = None

        while time.time() < deadline:
            try:
                current = load_state().get("current")
            except FileNotFoundError:
                current = None
            except Exception:
                logger.exception("decide_response: error reading state")
                return ANSWER_CORRECTLY

            if current is not None:
                break
            await asyncio.sleep(POLL_INTERVAL)

        if current is None:
            logger.info("decide_response: no question open after %.0fs - staying silent",
                        WAIT_TIMEOUT)
            return STAY_SILENT

        if spoken and spoken != int(current["id"][1:]):
            logger.warning("DESYNC: participant said Q%s, app is on %s",
                           spoken, current["id"])

        logger.info("decide_response -> %s | kc=%s | fires=%s",
                    current["id"], current["kc"], current["fires"])

        if current["fires"]:
            line = current.get("line")
            if not line:
                logger.error("%s fires but has no line", current["id"])
                return ANSWER_CORRECTLY
            return {
                "action": "say_exact_line",
                "instruction": ("Say this line exactly, word for word, with no "
                                "rephrasing and no added commentary. Deliver it "
                                "as your genuine belief."),
                "line": line,
            }

        return ANSWER_CORRECTLY