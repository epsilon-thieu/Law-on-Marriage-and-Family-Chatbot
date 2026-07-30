"""
GIAI ĐOẠN: generation/legal_answer_generator.py trong LangGraph Agent — HN&GD-RAG.

Nhận vào: câu hỏi gốc + danh sách chunk đã lấy từ HybridRetriever.
Trả về: câu trả lời tiếng Việt, CĂN CỨ ĐÚNG context được cung cấp, kèm trích dẫn
tới cấp Điều-Khoản-Điểm, và đã lọc bỏ mọi trích dẫn bịa không có trong context.

3 LỚP CHỐNG BỊA :
    1. SYSTEM_PROMPT với quy tắc cứng: chỉ dùng đúng context, không suy luận
       thêm, mọi quyền lợi/nghĩa vụ phải kèm trích dẫn, thiếu thì từ chối
    2. Ép model trả lời theo khuôn JSON có field "citations" TÁCH RIÊNG khỏi
       văn bản trả lời (không để model viết văn xuôi tự do rồi mình đi mò
       trích dẫn lẫn trong đó)
    3. Lọc lại lần cuối: đối chiếu từng citation model đưa ra với danh sách
       chunk THỰC SỰ có trong context -> citation nào không khớp thì cắt bỏ
       trước khi trả về cho người dùng

Cách dùng (test độc lập với context giả lập, chưa cần ráp HybridRetriever):
    python generation/legal_answer_generator.py
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent

MODEL_NAME = "gemini-3.1-flash-lite"

SYSTEM_PROMPT = """Bạn là trợ lý pháp lý trả lời câu hỏi về Luật Hôn nhân và Gia đình Việt Nam.

Bạn sẽ được cung cấp một danh sách các đoạn văn bản luật đã đánh số [1], [2], [3]...
Mỗi đoạn có thể kèm theo thông tin Điều/Khoản/Điểm và tên văn bản nguồn.

QUY TẮC BẮT BUỘC (tuân thủ TUYỆT ĐỐI, vi phạm là lỗi nghiêm trọng):
1. CHỈ được dùng thông tin có trong các đoạn văn bản được cung cấp. TUYỆT ĐỐI
   không dùng kiến thức luật bạn đã học từ trước nếu nó không xuất hiện trong context.
2. KHÔNG được suy luận, ngoại suy, hay "đoán" quy định không có trong context,
   kể cả khi bạn nghĩ mình biết quy định thật là gì.
3. Mọi quyền lợi, nghĩa vụ, điều kiện, mức tiền, hay thủ tục nêu trong câu trả
   lời PHẢI đi kèm số thứ tự đoạn trích dẫn tương ứng (VD: "... theo [2]").
4. Nếu context KHÔNG đủ thông tin để trả lời đầy đủ câu hỏi, phải nói rõ phần
   nào không có căn cứ, KHÔNG được tự bịa ra để câu trả lời "nghe đầy đủ".
5. Nếu không có đoạn nào liên quan tới câu hỏi, trả lời rằng không tìm thấy
   căn cứ, KHÔNG trả lời chung chung theo kiến thức nền.
6. Không dùng các cụm khẳng định tuyệt đối như "chắc chắn", "luôn luôn" nếu
   luật có ngoại lệ được nêu trong context.
7. Trả lời bằng tiếng Việt, ngắn gọn, rõ ràng, đúng trọng tâm câu hỏi.
8. Không đưa ra lời khuyên mang tính cá nhân hóa vượt quá phạm vi văn bản luật
   (VD: không tự quyết định ai đúng ai sai trong 1 vụ việc cụ thể).
9. Nếu câu hỏi có nhiều khía cạnh, trả lời đủ từng khía cạnh, mỗi khía cạnh
   có trích dẫn riêng của nó.
10. KHÔNG bịa số thứ tự trích dẫn không tồn tại trong danh sách đoạn được cung cấp.
11. Trường "citations" trong JSON trả về PHẢI liệt kê ĐẦY ĐỦ và CHỈ những số thứ tự
    đoạn thực sự được dùng để trả lời, không thừa không thiếu.
12. Nếu 2 đoạn context mâu thuẫn nhau (VD: văn bản cũ vs mới), ưu tiên văn bản
    còn hiệu lực nếu metadata có nêu rõ, và nói rõ trong câu trả lời.
13. Không thêm lời chào, lời dẫn dắt dài dòng ở đầu/cuối câu trả lời.
14. answerable = false CHỈ khi hoàn toàn không có đoạn nào liên quan; nếu có
    liên quan một phần thì answerable = true và nêu rõ phần còn thiếu ở đâu.

ĐỊNH DẠNG OUTPUT — CHỈ trả về CHÍNH XÁC 1 object JSON, không thêm chữ nào khác,
không bọc ```json:

{
  "answerable": true hoặc false,
  "answer": "<câu trả lời đầy đủ, có chèn [số thứ tự] ngay sau mỗi ý được trích dẫn>",
  "citations": [<danh sách số thứ tự đoạn thực sự được dùng, VD: [1, 3]>],
  "missing_info": "<mô tả ngắn phần câu hỏi không có căn cứ trong context, để rỗng nếu trả lời đủ>"
}
"""


@dataclass
class ContextChunk:
    """Retrieved context chunk."""
    page_content: str
    metadata: dict


@dataclass
class GeneratedAnswer:
    answerable: bool
    answer: str
    citations: list[dict] = field(default_factory=list)  # đã được lọc, kèm thông tin Điều/Khoản/Điểm
    missing_info: str = ""
    dropped_citations: list[int] = field(default_factory=list)  # số bị cắt vì bịa, để log/debug


def _format_context(chunks: list[ContextChunk]) -> str:
    lines = []
    for i, chunk in enumerate(chunks, start=1):
        meta = chunk.metadata
        ref = f"{meta.get('source', '?')}, Điều {meta.get('dieu', '?')}"
        if meta.get("khoan"):
            ref += f", Khoản {meta['khoan']}"
        if meta.get("diem"):
            ref += f", Điểm {meta['diem']}"
        lines.append(f"[{i}] ({ref})\n{chunk.page_content}")
    return "\n\n".join(lines)


class LegalAnswerGenerator:
    def __init__(self, api_key: str | None = None):
        self.client = genai.Client(api_key=api_key or os.getenv("GOOGLE_API_KEY"))

    def generate(self, question: str, context_chunks: list[ContextChunk]) -> GeneratedAnswer:
        if not context_chunks:
            # Không có gì để trích dẫn -> trả lời an toàn ngay, khỏi cần gọi LLM tốn tiền
            return GeneratedAnswer(
                answerable=False,
                answer="Không tìm thấy căn cứ pháp lý liên quan trong kho dữ liệu hiện có.",
                citations=[],
                missing_info="Toàn bộ câu hỏi",
            )

        context_text = _format_context(context_chunks)
        user_prompt = f"Câu hỏi: {question}\n\nCác đoạn văn bản luật liên quan:\n\n{context_text}"

        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=user_prompt,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "response_mime_type": "application/json",
                "temperature": 0,  # trả lời pháp lý cần ổn định, không sáng tạo
            },
        )

        return self._parse_and_sanitize(response.text, context_chunks)

    @staticmethod
    def _parse_and_sanitize(raw_text: str, context_chunks: list[ContextChunk]) -> GeneratedAnswer:
        cleaned = raw_text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(cleaned)

        raw_citations = data.get("citations", [])
        valid_range = range(1, len(context_chunks) + 1)

        # LỚP CHỐNG BỊA THỨ 3: chỉ giữ lại citation có số thứ tự thực sự tồn tại
        # trong danh sách context đã đưa vào prompt -- số nào ngoài phạm vi này
        # chắc chắn là model tự bịa, phải cắt bỏ trước khi hiện cho người dùng.
        valid_citations = []
        dropped = []
        for c in raw_citations:
            if isinstance(c, int) and c in valid_range:
                chunk = context_chunks[c - 1]
                valid_citations.append({"index": c, "metadata": chunk.metadata})
            else:
                dropped.append(c)

        return GeneratedAnswer(
            answerable=bool(data.get("answerable", False)),
            answer=data.get("answer", ""),
            citations=valid_citations,
            missing_info=data.get("missing_info", ""),
            dropped_citations=dropped,
        )

