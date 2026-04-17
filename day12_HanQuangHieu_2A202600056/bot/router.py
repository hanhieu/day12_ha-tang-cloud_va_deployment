import chainlit as cl
from bot.handlers.chat import handle_chat
from bot.handlers.driver_registration import run_driver_registration_flow
from bot.tools.intent_detector import detect_intent

BOT_NAME = "XanhSM"

HOTLINE_NUMBER = "1900 2088"


async def route(message: cl.Message):
    intent = await detect_intent(message.content)

    if intent == "driver_registration":
        confirm = await cl.AskActionMessage(
            content=(
                "Bạn muốn **đăng ký làm tài xế xe máy điện Xanh SM**?\n"
                "Mình sẽ hỗ trợ bạn điền form đăng ký ngay bây giờ."
            ),
            author=BOT_NAME,
            actions=[
                cl.Action(name="confirm", value="yes", label="✅ Xác nhận", payload={"value": "yes"}),
                cl.Action(name="confirm", value="no",  label="❌ Không phải", payload={"value": "no"}),
            ],
            timeout=60,
        ).send()

        if confirm and confirm.get("payload", {}).get("value") == "yes":
            await run_driver_registration_flow()
            return

        # Người dùng từ chối hoặc timeout → xử lý như câu hỏi thông thường
        user_type = cl.user_session.get("user_type")
        await handle_chat(message.content, user_type)
        return

    if intent == "human_escalation":
        await cl.Message(
            content=(
                "Mình hiểu rằng chatbot chưa giải quyết được vấn đề của bạn. "
                "Hãy liên hệ trực tiếp với tổng đài Xanh SM để được hỗ trợ ngay:\n\n"
                f"📞 **Hotline: {HOTLINE_NUMBER}**\n\n"
                "Tổng đài hoạt động **24/7**, nhân viên sẽ hỗ trợ bạn trực tiếp."
            ),
            author=BOT_NAME,
        ).send()
        return

    user_type = cl.user_session.get("user_type")
    await handle_chat(message.content, user_type)
