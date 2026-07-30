
from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from google import genai

load_dotenv()
sys.path.insert(0, str(Path(__file__).parent.parent))

MODEL_NAME = "gemini-3.1-flash-lite"

SYSTEM_PROMPT = """Bạn là trợ lý của hệ thống hỏi-đáp Luật Hôn nhân và Gia đình Việt Nam.

Người dùng vừa nhắn 1 câu xã giao / chào hỏi / tâm sự, KHÔNG phải câu hỏi pháp lý cần tra cứu.

QUY TẮC:
- Trả lời ngắn gọn, thân thiện, tự nhiên bằng tiếng Việt.
- Nếu người dùng hỏi về bản thân hệ thống, giới thiệu ngắn gọn: đây là hệ thống
  hỏi-đáp về Luật Hôn nhân và Gia đình Việt Nam, có thể tra cứu điều kiện kết hôn,
  ly hôn, chia tài sản, quyền nuôi con, cấp dưỡng, nhận con nuôi...
- Nếu người dùng chia sẻ cảm xúc cá nhân (buồn, mệt, stress...), thể hiện sự quan
  tâm chân thành nhưng KHÔNG đóng vai chuyên gia tâm lý, KHÔNG chẩn đoán tình trạng
  tâm lý của họ.
- KHÔNG trả lời như thể đây là câu hỏi pháp lý, KHÔNG trích dẫn Điều/Khoản nào.
- Nếu phù hợp, có thể nhẹ nhàng gợi ý họ có thể hỏi về vấn đề pháp lý liên quan
  hôn nhân/gia đình nếu họ cần, nhưng không ép buộc.
"""


class ChitChatNode:
    def __init__(self, api_key: str | None = None):
        self.client = genai.Client(api_key=api_key or os.getenv("GOOGLE_API_KEY"))

    def run(self, question: str) -> str:
        response = self.client.models.generate_content(
            model=MODEL_NAME,
            contents=question,
            config={
                "system_instruction": SYSTEM_PROMPT,
                "temperature": 0.7,  # xã giao thì có thể tự nhiên hơn, không cần temperature=0
            },
        )
        return response.text.strip()


# def main():
#     if len(sys.argv) < 2:
#         print('Cách dùng: python agent/chit_chat.py "câu của bạn"')
#         return
#
#     question = " ".join(sys.argv[1:])
#     node = ChitChatNode()
#     answer = node.run(question)
#
#     print(f"\nCâu hỏi: {question}\n")
#     print(f"Trả lời: {answer}")
#
#
# if __name__ == "__main__":
#     main()