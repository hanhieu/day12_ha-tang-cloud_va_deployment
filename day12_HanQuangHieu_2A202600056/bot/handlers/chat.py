import json
import logging
import time

import chainlit as cl
from openai import AsyncOpenAI
from config import settings
from rag.retriever import retrieve
from bot.tools.fare_data import FARE_TOOL_DEFINITION, execute_tool as _fare_execute
from bot.tools.query_rewriter import rewrite_query
from bot.middleware.cost_guard import record_cost

logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=settings.openai_api_key)
OPENAI_MODEL = settings.openai_model
TOP_K = settings.top_k

SYSTEM_TEMPLATE = '''<persona>
Bạn là Trợ lý AI Hỗ trợ của Xanh SM.

Mục tiêu chính của bạn là cung cấp thông tin chính xác, an toàn và cập nhật nhất.
Bạn LUÔN ưu tiên sự chính xác hơn sự đầy đủ.
Nếu bạn không chắc chắn, hãy nói rõ và chuyển lên cấp trên xử lý.
</persona>

<user_profile>
Loại người dùng: {user_type_label}
</user_profile>

<rules>
- Trả lời bằng ngôn ngữ nguời dùng đã sử dụng trong câu hỏi.
- Nếu câu hỏi không rõ, hãy hỏi lại khách hàng để làm rõ câu hỏi.
- Nếu loại người dùng là "Chưa xác định" VÀ câu trả lời có sự khác biệt giữa tài xế bike và tài xế taxi (ví dụ: lương, chính sách, quyền lợi), hãy hỏi người dùng họ là tài xế bike hay tài xế taxi trước khi trả lời.
- Trả lời câu hỏi dựa trên thông tin được cung cấp trong phần <context> bên dưới. Không sử dụng kiến thức bên ngoài phần này.
- Thông tin [Chính thức] là nguồn đáng tin cậy, ưu tiên sử dụng để trả lời.
- Thông tin [Cộng đồng] là bình luận từ người dùng trên mạng xã hội, KHÔNG phải câu trả lời chính thức. Chỉ dùng để hiểu thêm ngữ cảnh, KHÔNG được trích dẫn hoặc lặp lại nội dung này như câu trả lời.
- Khi người dùng hỏi về giá cước, phí đi xe, chi phí chuyến đi tại một thành phố cụ thể, hãy sử dụng tool lookup_fare để tra cứu và trình bày kết quả rõ ràng. Tool này không phụ thuộc vào <context>.
</rules>

<feedback_policy>
QUAN TRỌNG — Chính sách phản hồi người dùng:
Người dùng có thể cung cấp phản hồi bằng tính năng "Báo sai" (👎 Dislike) hoặc "Hài lòng" (👍 Like).
Phản hồi "Báo sai" là TÍN HIỆU ĐÁNH GIÁ CỦA CON NGƯỜI CÓ GIÁ TRỊ CAO.
Bạn phải xử lý nghiêm túc và KHÔNG bao giờ tranh luận hay bác bỏ phản hồi của người dùng.
Nếu câu trả lời trước của bạn bị đánh dấu là sai, hãy:
1. Thừa nhận rằng câu trả lời trước có thể chưa chính xác.
2. Cẩn thận kiểm tra lại thông tin trong <context>.
3. Đưa ra câu trả lời được cải thiện hoặc thừa nhận giới hạn kiến thức của bạn.
4. Không bao giờ lặp lại câu trả lời sai đã bị báo cáo.
</feedback_policy>

<context>
{context}
</context>

<constraints>
- Nếu không tìm thấy thông tin liên quan trong phần context, hãy trả lời rằng bạn không tìm thấy thông tin, không bịa câu trả lời.
- Từ chối mọi câu hỏi không liên quan đến dịch vụ của XanhSM (VD: viết code, làm bài tập, tư vấn tài chính, chính trị).
</constraints>
'''

BOT_NAME = "XanhSM"

TOOLS = [FARE_TOOL_DEFINITION]


def _execute_tool(name: str, args: dict) -> str:
    if name == "lookup_fare":
        return _fare_execute(name, args)
    return f"Tool '{name}' không được hỗ trợ."


async def handle_chat(user_message: str, user_type: str):
    t0 = time.monotonic()
    logger.info("[CHAT] user_type=%s | msg=%r", user_type, user_message[:100])

    history: list[dict] = cl.user_session.get("history") or []
    rag_query = await rewrite_query(user_message, history)

    chunks = retrieve(rag_query, user_type, top_k=TOP_K)

    if chunks:
        parts = []
        for c in chunks:
            label = "[Cộng đồng]" if c["category"] == "community" else "[Chính thức]"
            parts.append(f"{label}\nQ: {c['question']}\nA: {c['answer']}")
        context = "\n\n".join(parts)
    else:
        context = "(Không tìm thấy thông tin liên quan.)"
        logger.warning("[CHAT] No RAG chunks found for query=%r", user_message[:80])

    user_type_labels = {
        "tai_xe_bike": "Tài xế Bike",
        "tai_xe_taxi": "Tài xế Taxi",
        "nguoi_dung": "Hành khách",
        "nha_hang": "Nhà hàng",
    }
    user_type_label = user_type_labels.get(user_type, "Chưa xác định")
    system_prompt = SYSTEM_TEMPLATE.format(
        context=context,
        user_type_label=user_type_label,
    )

    history.append({"role": "user", "content": user_message})
    messages = [{"role": "system", "content": system_prompt}] + history

    # Inject pending feedback signal if user disliked the previous response
    pending_feedback = cl.user_session.get("pending_feedback")
    if pending_feedback:
        feedback_note = (
            f"[FEEDBACK_SIGNAL] Câu trả lời trước của bạn (về câu hỏi: "
            f'"{pending_feedback.get("user_question", "")}") '
            f"đã bị người dùng đánh dấu là SAI (👎). "
            f"Nội dung câu trả lời sai đó là: \"{pending_feedback.get('bot_answer', '')}\"\n"
            f"Hãy trả lời câu hỏi lần này một cách thận trọng hơn, "
            f"kiểm tra kỹ thông tin trong <context> và không lặp lại thông tin sai đó."
        )
        messages = [{"role": "system", "content": feedback_note}] + messages
        cl.user_session.set("pending_feedback", None)
        logger.info("[FEEDBACK] Injected dislike signal into prompt")

    msg = cl.Message(content="", author=BOT_NAME)
    await msg.send()

    full_response = await _chat_with_tools(messages, msg)

    await msg.update()

    # Store message_id → {question, answer} mapping for feedback lookup
    msg_store: dict = cl.user_session.get("msg_store") or {}
    msg_store[msg.id] = {
        "user_question": user_message,
        "bot_answer": full_response,
    }
    cl.user_session.set("msg_store", msg_store)

    elapsed = time.monotonic() - t0
    logger.info(
        "[CHAT] done | %.2fs | history_turns=%d | response_len=%d",
        elapsed, len(history), len(full_response),
    )

    history.append({"role": "assistant", "content": full_response})
    cl.user_session.set("history", history)


async def _chat_with_tools(messages: list[dict], msg: cl.Message) -> str:
    """
    Gọi OpenAI với tool support (streaming).
    - Lượt 1: stream và thu thập tool calls nếu có.
    - Nếu model gọi tool: thực thi → lượt 2 stream câu trả lời cuối.
    - Nếu không có tool call: trả về nội dung lượt 1.
    """
    # --- Lượt 1 ---
    stream = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=messages,
        tools=TOOLS,
        tool_choice="auto",
        stream=True,
    )

    tool_calls_acc: dict[int, dict] = {}  # index → {"id", "name", "arguments"}
    first_response_content = ""
    finish_reason = None
    assistant_message_dict: dict = {"role": "assistant", "content": None, "tool_calls": []}

    async for chunk in stream:
        choice = chunk.choices[0]
        if choice.finish_reason:
            finish_reason = choice.finish_reason
        delta = choice.delta

        # Stream văn bản bình thường
        if delta.content:
            first_response_content += delta.content
            await msg.stream_token(delta.content)

        # Thu thập tool call chunks
        if delta.tool_calls:
            for tc_chunk in delta.tool_calls:
                idx = tc_chunk.index
                if idx not in tool_calls_acc:
                    tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                if tc_chunk.id:
                    tool_calls_acc[idx]["id"] += tc_chunk.id
                if tc_chunk.function and tc_chunk.function.name:
                    tool_calls_acc[idx]["name"] += tc_chunk.function.name
                if tc_chunk.function and tc_chunk.function.arguments:
                    tool_calls_acc[idx]["arguments"] += tc_chunk.function.arguments

    # Không có tool call → record cost estimate and return
    if finish_reason != "tool_calls" or not tool_calls_acc:
        # Estimate: 4 chars ≈ 1 token
        est_input = sum(len(str(m.get("content", ""))) for m in messages) // 4
        est_output = len(first_response_content) // 4
        record_cost(est_input, est_output, model=OPENAI_MODEL)
        return first_response_content

    # --- Thực thi tool calls ---
    tool_calls_list = []
    tool_result_messages = []

    for idx in sorted(tool_calls_acc):
        tc = tool_calls_acc[idx]
        tool_calls_list.append({
            "id": tc["id"],
            "type": "function",
            "function": {"name": tc["name"], "arguments": tc["arguments"]},
        })
        try:
            args = json.loads(tc["arguments"])
        except json.JSONDecodeError:
            args = {}

        logger.info("[TOOL] calling %s args=%r", tc["name"], args)
        result = _execute_tool(tc["name"], args)

        tool_result_messages.append({
            "role": "tool",
            "tool_call_id": tc["id"],
            "content": result,
        })

    # Lắp assistant message có tool_calls vào history
    assistant_message_dict["tool_calls"] = tool_calls_list
    if first_response_content:
        assistant_message_dict["content"] = first_response_content

    updated_messages = messages + [assistant_message_dict] + tool_result_messages

    # --- Lượt 2: stream câu trả lời cuối ---
    stream2 = await client.chat.completions.create(
        model=OPENAI_MODEL,
        messages=updated_messages,
        stream=True,
    )

    final_response = ""
    async for chunk in stream2:
        delta = chunk.choices[0].delta.content
        if delta:
            final_response += delta
            await msg.stream_token(delta)

    # Record cost for both LLM turns
    est_input = sum(len(str(m.get("content", ""))) for m in updated_messages) // 4
    est_output = len(final_response) // 4
    record_cost(est_input, est_output, model=OPENAI_MODEL)

    return final_response
