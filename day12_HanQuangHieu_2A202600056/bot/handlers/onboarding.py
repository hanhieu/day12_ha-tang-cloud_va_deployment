import chainlit as cl

USER_TYPE_LABELS = {
    "nguoi_dung": "👤 Hành khách",
    "tai_xe_taxi": "🚖 Tài xế Taxi",
    "tai_xe_bike": "🛵 Tài xế Bike",
    "nha_hang": "🍜 Nhà hàng",
}

SUGGESTED_QUESTIONS = [
    ("Làm thế nào để đặt chuyến xe di chuyển trên ứng dụng?", "🚗 Đặt chuyến xe"),
    ("Giá cước các dịch vụ Xanh SM hiện tại là bao nhiêu?", "💰 Giá cước dịch vụ"),
    ("Tôi muốn đăng ký làm tài xế Xanh SM", "📋 Đăng ký tài xế"),
    ("Tôi gặp tai nạn", "🆘 Tôi gặp tai nạn"),
]

BOT_NAME = "XanhSM"


async def ask_user_type():
    actions = [
        cl.Action(
            name="set_type",
            value=key,
            label=label,
            payload={"value": key}
        )
        for key, label in USER_TYPE_LABELS.items()
    ]

    await cl.Message(
        content="Xin chào! Trợ lý ảo XanhSM đã sẵn sàng hỗ trợ bạn!\nVui lòng mô tả vai trò của bạn:",
        actions=actions,
        author=BOT_NAME
    ).send()

    suggestion_actions = [
        cl.Action(
            name="suggest_question",
            value=question,
            label=label,
            payload={"question": question}
        )
        for question, label in SUGGESTED_QUESTIONS
    ]

    await cl.Message(
        content="Câu hỏi gợi ý:",
        actions=suggestion_actions,
        author=BOT_NAME
    ).send()


@cl.action_callback("set_type")
async def on_set_type(action: cl.Action):
    user_type = action.payload["value"]
    label = USER_TYPE_LABELS.get(user_type, user_type)

    cl.user_session.set("user_type", user_type)
    cl.user_session.set("history", [])

    await cl.Message(
        content=f"Đã xác nhận: **{label}**. Bạn có thể đặt câu hỏi ngay bây giờ!",
        author=BOT_NAME
    ).send()


@cl.action_callback("suggest_question")
async def on_suggest_question(action: cl.Action):
    from bot.router import route

    question = action.payload["question"]
    await cl.Message(content=question, author="Bạn").send()
    fake_msg = cl.Message(content=question)
    await route(fake_msg)