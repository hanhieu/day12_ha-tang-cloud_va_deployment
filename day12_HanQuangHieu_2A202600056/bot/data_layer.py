"""
Custom Chainlit data layer.

Implementing BaseDataLayer is the only way to make Chainlit show the
like / dislike (👍 👎) buttons on assistant messages.

We only override the methods needed for feedback; everything else is a
no-op so the rest of the app behaviour is unchanged.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import chainlit as cl
from chainlit.data import BaseDataLayer
from chainlit.data.utils import queue_until_user_message
from chainlit.types import Feedback

from config import settings

logger = logging.getLogger(__name__)

FEEDBACK_FILE = Path(settings.feedback_path)
FEEDBACK_FILE.parent.mkdir(parents=True, exist_ok=True)


class LocalFeedbackDataLayer(BaseDataLayer):
    """Minimal data layer that persists user feedback locally."""

    # ------------------------------------------------------------------ #
    # Feedback                                                             #
    # ------------------------------------------------------------------ #

    async def upsert_feedback(self, feedback: Feedback) -> str:
        """Called by Chainlit when a user clicks 👍 or 👎."""
        is_like = feedback.value == 1
        value_label = "👍 like" if is_like else "👎 dislike"
        logger.info("[FEEDBACK] %s | forId=%s", value_label, feedback.forId)

        # Pull the original Q&A from the user session if available.
        # Note: upsert_feedback runs inside the user's request context,
        # so cl.user_session is accessible here.
        try:
            msg_store: dict = cl.user_session.get("msg_store") or {}
            original = msg_store.get(feedback.forId, {})
            user_question = original.get("user_question", "")
            bot_answer = original.get("bot_answer", "")
        except Exception:
            user_question = ""
            bot_answer = ""

        record = {
            "timestamp": datetime.now().isoformat(),
            "message_id": feedback.forId,
            "value": feedback.value,        # 1 = like, 0 = dislike
            "comment": feedback.comment or "",
            "user_question": user_question,
            "bot_answer": bot_answer,
        }

        with open(FEEDBACK_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        # For DISLIKE: store a correction signal for the next LLM call.
        if not is_like and user_question:
            try:
                cl.user_session.set("pending_feedback", {
                    "user_question": user_question,
                    "bot_answer": bot_answer,
                })
            except Exception:
                pass

        # Send a friendly acknowledgment.
        if is_like:
            ack = "Cảm ơn bạn đã đánh giá tích cực! 😊 Mình rất vui vì đã giúp ích được cho bạn."
        else:
            ack = (
                "Cảm ơn bạn đã báo sai! 🙏\n"
                "Mình đã ghi nhận phản hồi và sẽ cố gắng trả lời chính xác hơn.\n"
                "Bạn có thể đặt lại câu hỏi để mình thử lại nhé."
            )

        try:
            await cl.Message(content=ack, author="XanhSM").send()
        except Exception as exc:
            logger.warning("[FEEDBACK] Could not send ack message: %s", exc)

        return feedback.forId or "local"

    # ------------------------------------------------------------------ #
    # Stubs — required by the ABC but not needed for our use-case.        #
    # ------------------------------------------------------------------ #

    async def get_user(self, identifier: str):
        from datetime import timezone
        try:
            from chainlit.user import PersistedUser
        except ImportError:
            from chainlit.types import PersistedUser
        return PersistedUser(
            id=identifier,
            identifier=identifier,
            createdAt=datetime.now(timezone.utc).isoformat(),
            metadata={},
        )

    async def create_user(self, user):
        return await self.get_user(user.identifier)

    async def update_thread(self, thread_id: str, **kwargs):
        pass

    async def get_thread_author(self, thread_id: str) -> str:
        return ""

    async def delete_thread(self, thread_id: str):
        pass

    async def list_threads(self, pagination, filters):
        from chainlit.types import PaginatedResponse
        return PaginatedResponse(data=[], pageInfo={"hasNextPage": False, "startCursor": None, "endCursor": None})

    async def get_thread(self, thread_id: str):
        return None

    async def delete_feedback(self, feedback_id: str) -> bool:
        return True

    async def create_element(self, element):
        pass

    async def get_element(self, thread_id, element_id):
        return None

    async def delete_element(self, element_id, thread_id=None):
        pass

    async def create_step(self, step_dict: dict):
        pass

    async def update_step(self, step_dict: dict):
        pass

    async def delete_step(self, step_id: str):
        pass

    async def get_all_user_threads(self, user_id, thread_id):
        return None

    async def get_elements(self, thread_id: str):
        return []

    async def build_debug_url(self) -> str:
        return ""

    async def close(self):
        pass

    async def get_favorite_steps(self):
        return []
