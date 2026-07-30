from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from dotenv import load_dotenv

from google import genai

load_dotenv()

PROJECT_ROOT = Path(__file__).parent.parent

MODEL_NAME = "gemini-3.1-flash-lite"

CATEGORIES = ["legal_rag", "chit_chat", "out_of_scope", "web_search"]

TOPICS = [
    "ket_hon",              # điều kiện kết hôn, đăng ký kết hôn, kết hôn trái pháp luật
    "ly_hon",               # ly hôn thuận tình / đơn phương, căn cứ ly hôn
    "tai_san_vo_chong",     # tài sản chung/riêng, chia tài sản khi ly hôn, khi 1 bên mất
    "quyen_nuoi_con",       # quyền nuôi con sau ly hôn, thay đổi người trực tiếp nuôi con
    "cap_duong",            # nghĩa vụ cấp dưỡng (cho con, cho vợ/chồng, cho cha mẹ)
    "nhan_nuoi_con_nuoi",   # điều kiện, thủ tục nhận con nuôi
    "giam_ho",              # giám hộ, người giám hộ đương nhiên/được chỉ định
    "yeu_to_nuoc_ngoai",    # kết hôn/ly hôn có yếu tố nước ngoài
    "khac",                 # không rơi vào 8 mảng trên nhưng vẫn thuộc phạm vi luật
]

RELATIONSHIP_ROLES = ["vo_chong", "con", "cha_me", "nguoi_giam_ho", "khong_ro"]

SYSTEM_PROMPT = f"""Bạn là bộ phân loại câu hỏi cho hệ thống hỏi-đáp Luật Hôn nhân và Gia đình Việt Nam.

Với mỗi câu hỏi, hãy phân tích và trả về CHÍNH XÁC 1 object JSON, không thêm chữ nào khác,
không thêm ```json, theo đúng khuôn sau:

{{
  "category": "<1 trong 4 giá trị: {CATEGORIES}>",
  "intent": "<mô tả ngắn gọn ý định câu hỏi, 1 câu tiếng Việt>",
  "topic": "<1 trong các giá trị: {TOPICS}>",
  "relationship_role": "<1 trong các giá trị: {RELATIONSHIP_ROLES}>",
  "expanded_queries": ["<cách diễn đạt lại 1>", "<cách diễn đạt lại 2>", "<cách diễn đạt lại 3>"]
}}

QUY TẮC PHÂN LOẠI category:
- "legal_rag": câu hỏi cần tra cứu Luật Hôn nhân & Gia đình, Nghị định/Thông tư liên quan
  (điều kiện, thủ tục, quyền, nghĩa vụ, mức cấp dưỡng, chia tài sản, quyền nuôi con...)
- "chit_chat": chào hỏi, xã giao, hỏi về bản thân hệ thống, không cần tra luật
- "out_of_scope": câu hỏi pháp luật nhưng KHÔNG thuộc Luật Hôn nhân & Gia đình
  (VD: hỏi luật giao thông, luật hình sự, luật đất đai không liên quan tài sản vợ chồng)
- "web_search": câu hỏi cần thông tin thời sự/cập nhật ngoài phạm vi văn bản luật đã có
  trong kho (VD: án lệ mới, số liệu thống kê ly hôn mới nhất)

QUY TẮC expanded_queries:
- Viết lại câu hỏi gốc thành 3 cách diễn đạt khác nhau, dùng đúng thuật ngữ pháp lý
  của mảng "topic" đã xác định (VD: nếu topic="ly_hon" thì nên có từ "căn cứ ly hôn",
  "thuận tình ly hôn", "đơn phương ly hôn" tùy ngữ cảnh câu hỏi)
- Giữ nguyên ý gốc, không suy diễn thêm tình tiết mà người dùng không nói tới
- Nếu category không phải "legal_rag" thì expanded_queries để mảng rỗng []

QUY TẮC relationship_role:
- Chỉ gán khi câu hỏi có thể suy ra rõ ràng ai đang hỏi (VD: "tôi và vợ tôi" -> vo_chong,
  "con tôi" kèm ngữ cảnh đang hỏi quyền của cha mẹ -> cha_me)
- Nếu không rõ, để "khong_ro", TUYỆT ĐỐI không suy đoán khi câu hỏi không có manh mối
"""


@dataclass
class AnalyzerResult:
    category: str
    intent: str
    topic: str
    relationship_role: str
    expanded_queries: list[str] = field(default_factory=list)

    @classmethod
    def from_json_text(cls, text: str) -> "AnalyzerResult":
        # Phòng trường hợp model lỡ bọc ```json ... ``` dù đã cấm trong prompt
        cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        data = json.loads(cleaned)

        category = data.get("category", "out_of_scope")
        if category not in CATEGORIES:
            category = "out_of_scope"

        topic = data.get("topic", "khac")
        if topic not in TOPICS:
            topic = "khac"

        role = data.get("relationship_role", "khong_ro")
        if role not in RELATIONSHIP_ROLES:
            role = "khong_ro"

        return cls(
            category=category,
            intent=data.get("intent", ""),
            topic=topic,
            relationship_role=role,
            expanded_queries=data.get("expanded_queries", []) if category == "legal_rag" else [],
        )


class Analyzer:
    def __init__(self, api_key: str | None = None):
        self.client = genai.Client(api_key=api_key or os.environ.get("GOOGLE_API_KEY"))

    def analyze(self, question: str, history: list = None) -> AnalyzerResult:
        history_text = ""
        # Lấy tối đa 4-6 tin nhắn gần nhất để không làm loãng prompt
        if history and len(history) > 1:
            recent_msgs = history[-5:-1]  # Bỏ tin nhắn hiện tại vừa add
            history_text = "LỊCH SỬ CHÁT GẦN ĐÂY:\n"
            for msg in recent_msgs:
                # Format tin nhắn dạng [User/Bot]: content
                role = "User" if getattr(msg, 'type', '') == 'human' or (isinstance(msg, tuple) and msg[0] == 'user') else "Bot"
                content = getattr(msg, 'content', str(msg[1]) if isinstance(msg, tuple) else str(msg))
                history_text += f"{role}: {content}\n"
            history_text += "\n"

        prompt_input = f"{history_text}CÂU HỎI HIỆN TẠI: {question}"

        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt_input,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "response_mime_type": "application/json",
                "temperature": 0,
            },
        )
        return AnalyzerResult.from_json_text(response.text)


def main():
    if len(sys.argv) < 2:
        print('Cách dùng: python agent/analyzer.py "câu hỏi của bạn"')
        return

    question = " ".join(sys.argv[1:])
    analyzer = Analyzer()
    result = analyzer.analyze(question)

    print(f"\nCâu hỏi: {question}\n")
    print(f"category          : {result.category}")
    print(f"intent            : {result.intent}")
    print(f"topic             : {result.topic}")
    print(f"relationship_role : {result.relationship_role}")
    print("expanded_queries  :")
    for q in result.expanded_queries:
        print(f"  - {q}")


if __name__ == "__main__":
    main()