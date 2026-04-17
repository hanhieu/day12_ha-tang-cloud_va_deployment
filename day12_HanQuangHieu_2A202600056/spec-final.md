# SPEC 

**Problem statement (1 câu):**  
*Người dùng trong hệ sinh thái Xanh SM (Hành khách, Tài xế Taxi, Tài xế Bike, Nhà hàng đối tác) mất nhiều thời gian tìm thông tin giá cước, khu vực phục vụ và chính sách qua website, hotline và mạng xã hội rời rạc; AI chatbot phân loại theo từng nhóm user để trả lời FAQ tức thì và thay thế hotline cho các câu hỏi thông thường.*

---

## 1. AI Product Canvas

|   | Value | Trust | Feasibility |
|---|-------|-------|-------------|
| **Câu hỏi** | User nào? Pain gì? AI giải gì? | Khi AI sai thì sao? User sửa bằng cách nào? | Cost/latency bao nhiêu? Risk chính? |
| **Trả lời** | **User:** 4 nhóm trong hệ sinh thái Xanh SM — Hành khách, Tài xế Taxi, Tài xế Bike, Nhà hàng đối tác. **Pain:** Mất thời gian tìm thông tin giá cước, khu vực hoạt động, chính sách vận hành qua nhiều kênh không phân loại theo vai trò (website, hotline 1900 2088, mạng xã hội). **AI giải:** User chọn loại tài khoản (4 nút) hoặc hỏi trực tiếp — chatbot trả lời tức thì (&lt;3s) dựa trên FAQ chính thức (ưu tiên) kết hợp kinh nghiệm cộng đồng (bổ trợ), thay thế việc gọi hotline cho câu hỏi thông thường. | **Khi AI sai:** AI báo sai giá, khu vực hoặc chính sách → user đặt xe/hoạt động sai → bị tính phí sai hoặc vi phạm chính sách. **User biết sai:** Nguồn gắn nhãn [Chính thức] / [Cộng đồng] trong mỗi câu trả lời. **User sửa:** Nút 👎 Dislike (Chainlit native) → correction log → content team review → cập nhật knowledge base. **Khi AI không giải quyết được:** Intent classifier phát hiện `human_escalation` (user thất vọng, hỏi mãi không được) → bot hard-route sang hotline 1900 2088, nhân viên người thật tiếp nhận. | **Cost:** ~$0.002–0.005/query (GPT‑4o). **Latency:** &lt;3s (streaming). **Stack:** ChromaDB (local), `keepitreal/vietnamese-sbert`, RAG dual-search + dedup, query rewriter (LLM). **Risk chính:** Thông tin giá/khuyến mãi và chính sách thay đổi nhanh làm knowledge base bị stale trong khi AI trả lời tự tin. **Mitigation:** Timestamp mỗi FAQ, auto‑disclaimer nếu &gt;7 ngày chưa verify, pipeline crawl website Xanh SM hằng ngày. |

**Automation hay augmentation?** ☐ Automation · ☑ Augmentation  
Justify: *AI gợi ý và trả lời, user quyết định cuối cùng. Với câu hỏi phức tạp (khiếu nại nghiêm trọng, tai nạn), AI hard‑route sang agent người thật — không tự xử lý.*

**Learning signal:**

1. **User correction đi vào đâu?** Nút “Báo sai” → correction log → content team review hàng tuần → cập nhật `data/qa.json` → re‑ingest ChromaDB → fine‑tune định kỳ 2 tuần  
2. **Product thu signal gì?** Implicit: conversion sau chatbot. Explicit: thumbs up/down. Correction: “Báo sai”. Alert khi acceptance rate giảm &gt;10%/tuần hoặc escalation rate tăng &gt;5%.  
3. **Data thuộc loại nào?** ☐ User‑specific · ☑ Domain‑specific · ☑ Real‑time · ☑ Human‑judgment · ☐ Khác  
   **Có marginal value không?** Có — FAQ + phản hồi cộng đồng tài xế/đối tác Xanh SM là data đặc thù, tạo competitive moat từ data.

---

## 2. User Stories — 4 paths

### Feature: Trả lời FAQ theo từng nhóm user

**Trigger:** User mở chatbot → chọn loại tài khoản (hoặc hỏi trực tiếp)

| Path | Câu hỏi thiết kế | Mô tả |
|------|-------------------|-------|
| Happy — AI đúng, tự tin | User thấy gì? Flow kết thúc ra sao? | User hỏi *”Tôi bị tai nạn rồi phải làm sao”* → bot trả lời 6 bước an toàn (sơ cứu, báo cảnh sát 113, liên hệ bảo hiểm…) kèm hotline 1900 2097 — nguồn `[Chính thức]`, user áp dụng ngay không cần gọi hotline *(Test 1)* |
| Low-confidence — AI không chắc | System báo thế nào? User quyết thế nào? | User hỏi *”Đi 20km hết bao nhiêu tiền”* — thiếu loại dịch vụ + thành phố → bot hỏi lại từng bước (loại dịch vụ? → Premium; thành phố? → Hà Nội) → tính được 313.600 VNĐ *(Test 2)* |
| Failure — AI sai | User biết AI sai bằng cách nào? Recover ra sao? | User phát hiện giá sai khi đối chiếu app thực tế → nhấn 👎 Dislike → correction log → content team review + cập nhật `data/qa.json` |
| Correction — user sửa | User sửa bằng cách nào? Data đó đi vào đâu? | 👎 Dislike → correction log → content team update KB → re-ingest ChromaDB |

---

### Feature: Tra cứu giá cước thực tế (tool calling)

**Trigger:** User hỏi giá cước kèm thông tin đủ (thành phố + loại dịch vụ) → intent không phải `driver_registration` → GPT-4o gọi tool `lookup_fare(city, service_type)`

| Path | Câu hỏi thiết kế | Mô tả |
|------|-------------------|-------|
| Happy — AI đúng, tự tin | User thấy gì? | Multi-turn: *”Đi 20km hết bao nhiêu”* → bot hỏi lại 2 lần → đủ thông tin → tool `lookup_fare(“ha_noi”, “premium”)` → trả về bảng phân tầng km + tổng 313.600 VNĐ *(Test 2)* |
| Low-confidence — AI không chắc | System báo thế nào? | Thiếu thành phố hoặc loại dịch vụ → bot hỏi lại từng bước, không đoán mò |
| Failure — AI sai | Recover ra sao? | Giá trả về lệch thực tế (data stale) → user báo sai → disclaimer “Mức cước có thể thay đổi theo thực tế” xuất hiện trong mọi câu trả lời giá |
| Correction — user sửa | Data đi vào đâu? | Correction log → team cập nhật `Dataset/pricedata.json` |

---

### Feature: Trả lời dựa trên dữ liệu cộng đồng Facebook

**Trigger:** Câu hỏi về kinh nghiệm thực tế (thu nhập, giờ chạy, BHXH…) không có trong FAQ chính thức → RAG tìm thấy posts Facebook Group tài xế

| Path | Câu hỏi thiết kế | Mô tả |
|------|-------------------|-------|
| Happy — AI đúng, tự tin | User thấy gì? | User hỏi thu nhập thực tế tài xế taxi → bot trả lời dựa trên posts cộng đồng *”tháng bèo bèo 30 triệu cầm về”*, gắn nhãn `[Cộng đồng]` rõ ràng, khuyến nghị liên hệ Xanh SM để xác nhận BHXH *(Test 3)* |
| Low-confidence — AI không chắc | System báo thế nào? | Bot hỏi thêm vai trò (taxi hay bike?) trước khi trả lời để lọc đúng nguồn cộng đồng theo `user_type` |
| Failure — AI sai | Recover ra sao? | Data cộng đồng nhiễu / lỗi thời → bot ưu tiên nguồn `[Chính thức]` khi có, chỉ dùng cộng đồng làm ngữ cảnh bổ trợ |
| Correction — user sửa | Data đi vào đâu? | 👎 Dislike → flag post Facebook để loại khỏi KB trong lần re-ingest tiếp theo |

---

### Feature: Đăng ký tài xế qua chatbot (guided form)

**Trigger:** User nhắn muốn đăng ký / ứng tuyển làm tài xế → intent classifier phát hiện `driver_registration`

| Path | Câu hỏi thiết kế | Mô tả |
|------|-------------------|-------|
| Happy — AI đúng, tự tin | User thấy gì? Flow kết thúc ra sao? | User nhắn *”Tôi muốn làm tài xế XanhSM”* → intent `driver_registration` → bot xác nhận *”Bạn có muốn đăng ký không?”* → user chọn ✅ Xác nhận → form 5 bước (họ tên, SĐT, hạng bằng, địa điểm, nhu cầu) → submit thành công *(Test 4)* |
| Low-confidence — AI không chắc | System báo thế nào? | Bot hỏi lại *”Bạn có muốn đăng ký tài xế không?”* trước khi vào flow, user có thể từ chối |
| Failure — AI sai | Recover ra sao? | User nhấn ❌ Không phải → bot quay về xử lý câu hỏi bình thường |
| Correction — user sửa | Data đi vào đâu? | Form lưu vào `data/driver_applications.jsonl` — team review thủ công |

---

## 3. Eval metrics + threshold

**Optimize precision hay recall?** ☑ Precision · ☐ Recall  
**Tại sao?** Trả lời sai giá/chính sách gây hại trực tiếp về tiền và vận hành.  
**Nếu ưu tiên recall:** AI escalate nhiều hơn nhưng không gây thiệt hại.

| Metric | Threshold | Red flag (dừng khi) |
|--------|-----------|---------------------|
| Precision theo FAQ chính thức | ≥90% | &lt;80% trong 3 ngày |
| Escalation rate | ≤20% | &gt;40% liên tục |
| Thumbs up rate | ≥75% | &lt;60% trong 1 tuần |

---

## 4. Top 3 failure modes

| # | Trigger | Hậu quả | Mitigation |
|---|---------|---------|------------|
| 1 | FAQ giá/chính sách stale | User tin AI và làm sai | Timestamp + auto‑disclaimer + crawl |
| 2 | AI trả lời vòng vòng, không giải quyết được | User thất vọng, bỏ dùng hoặc phải tự gọi hotline | Intent classifier phát hiện `human_escalation` → bot dừng, hiển thị hotline 1900 2088, hard-route sang nhân viên người thật |
| 3 | Data cộng đồng nhiễu | AI trả lời lệch | Ưu tiên nguồn chính thức |

---

## 5. ROI 3 kịch bản

|   | Conservative | Realistic | Optimistic |
|---|-------------|-----------|------------|
| **Assumption** | 500 query/ngày | 3.000 query/ngày | 10.000 query/ngày |
| **Cost** | ~$5/ngày | ~$25/ngày | ~$80/ngày |
| **Benefit** | Giảm hàng trăm cuộc hotline/tháng | Giảm hàng nghìn cuộc | Thay thế phần lớn hotline |
| **Net** | + | ++ | +++ |

**Kill criteria:** Precision &lt;80% sau 2 tuần **hoặc** escalation rate &gt;40% trong 1 tháng → dừng để audit lại KB.

---

## 6. Mini AI spec

Xanh SM AI Support Chatbot là chatbot hỗ trợ đa vai trò trong hệ sinh thái Xanh SM, phục vụ đồng thời hành khách, tài xế taxi, tài xế bike và nhà hàng đối tác. Sản phẩm tập trung giải quyết bài toán thông tin rời rạc và không phân loại theo user role — nguyên nhân chính khiến hotline quá tải.

AI hoạt động theo hướng augmentation: trả lời FAQ và gợi ý hành động, user quyết định cuối cùng. Chất lượng tối ưu theo hướng precision‑first, chấp nhận escalate thay vì trả lời sai.

**Pipeline kỹ thuật:** Query rewriter (LLM) cải thiện câu hỏi trước khi đưa vào RAG → dual-search ChromaDB (filter theo role + unfiltered fallback) → GPT-4o streaming với tool calling (tra cứu giá cước 45 tỉnh). Intent classifier (gpt-4o-mini, ~$0.0001/call) chạy song song để phát hiện 3 trường hợp đặc biệt: đăng ký tài xế (guided form 5 bước), human escalation (route sang hotline 1900 2088 khi AI bất lực), và câu hỏi thông thường.

Data flywheel đến từ 👎 dislike (correction log), feedback và hành vi click giúp model cải thiện dần, tạo moat từ data đặc thù Xanh SM.