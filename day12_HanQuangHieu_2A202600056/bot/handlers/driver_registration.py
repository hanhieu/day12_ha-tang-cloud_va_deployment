"""
Luồng thu thập form đăng ký tài xế xe máy điện Xanh SM.
Dùng Chainlit AskUserMessage / AskActionMessage để hỏi từng bước.
"""

import chainlit as cl
from bot.tools.driver_application import submit_driver_application, VALID_LOCATIONS

BOT_NAME = "XanhSM"

_LOCATION_LIST = "\n".join(f"{i+1}. {loc}" for i, loc in enumerate(VALID_LOCATIONS))


async def run_driver_registration_flow():
    # --- Bước 1: Họ và tên ---
    res = await cl.AskUserMessage(
        content=(
            "Mình sẽ hỗ trợ bạn đăng ký **vị trí tài xế xe máy điện Xanh SM**!\n\n"
            "**Bước 1/5 — Họ và tên đầy đủ của bạn?**"
        ),
        author=BOT_NAME,
        timeout=180,
    ).send()
    if not res:
        await cl.Message(content="Đăng ký đã bị huỷ do hết thời gian.", author=BOT_NAME).send()
        return
    full_name = res["output"].strip()

    # --- Bước 2: SĐT ---
    res = await cl.AskUserMessage(
        content="**Bước 2/5 — Số điện thoại liên hệ?**",
        author=BOT_NAME,
        timeout=180,
    ).send()
    if not res:
        await cl.Message(content="Đăng ký đã bị huỷ do hết thời gian.", author=BOT_NAME).send()
        return
    phone = res["output"].strip()

    # --- Bước 3: Hạng bằng lái ---
    res = await cl.AskActionMessage(
        content="**Bước 3/5 — Hạng bằng lái xe máy của bạn?**",
        author=BOT_NAME,
        actions=[
            cl.Action(name="license", value="A1", label="Hạng A1", payload={"value": "A1"}),
            cl.Action(name="license", value="A2", label="Hạng A2", payload={"value": "A2"}),
        ],
        timeout=180,
    ).send()
    if not res:
        await cl.Message(content="Đăng ký đã bị huỷ do hết thời gian.", author=BOT_NAME).send()
        return
    license_type = res.get("payload", {}).get("value") or res.get("value", "")

    # --- Bước 4: Địa điểm ứng tuyển ---
    res = await cl.AskUserMessage(
        content=(
            f"**Bước 4/5 — Địa điểm ứng tuyển?**\n\n"
            f"Nhập số thứ tự hoặc tên thành phố:\n{_LOCATION_LIST}"
        ),
        author=BOT_NAME,
        timeout=180,
    ).send()
    if not res:
        await cl.Message(content="Đăng ký đã bị huỷ do hết thời gian.", author=BOT_NAME).send()
        return

    location = _resolve_location(res["output"].strip())
    if not location:
        await cl.Message(
            content=(
                "Địa điểm không hợp lệ. Vui lòng thử lại từ đầu và chọn trong danh sách.\n"
                f"{_LOCATION_LIST}"
            ),
            author=BOT_NAME,
        ).send()
        return

    # --- Bước 5: Nhu cầu hiện tại (optional) ---
    res = await cl.AskUserMessage(
        content=(
            "**Bước 5/5 — Nhu cầu hiện tại của bạn?** *(không bắt buộc)*\n"
            "Nhập nội dung hoặc gõ **bỏ qua** để tiếp tục."
        ),
        author=BOT_NAME,
        timeout=180,
    ).send()
    current_need = ""
    if res:
        val = res["output"].strip()
        if val.lower() not in ("bỏ qua", "skip", "-", ""):
            current_need = val

    # --- Submit ---
    result = submit_driver_application(
        full_name=full_name,
        phone=phone,
        license_type=license_type,
        location=location,
        current_need=current_need,
    )
    await cl.Message(content=result, author=BOT_NAME).send()


def _resolve_location(raw: str) -> str | None:
    """Chấp nhận số thứ tự (1-17) hoặc tên thành phố (fuzzy prefix)."""
    # Số thứ tự
    if raw.isdigit():
        idx = int(raw) - 1
        if 0 <= idx < len(VALID_LOCATIONS):
            return VALID_LOCATIONS[idx]
        return None

    # Khớp tên chính xác hoặc prefix
    raw_lower = raw.lower()
    for loc in VALID_LOCATIONS:
        if loc.lower() == raw_lower or loc.lower().startswith(raw_lower):
            return loc

    return None
