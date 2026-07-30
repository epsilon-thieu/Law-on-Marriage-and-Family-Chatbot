"""
GIAI ĐOẠN: agent/out_of_scope.py trong LangGraph Agent — HN&GD-RAG.

Node được gọi khi analyzer phân loại category="out_of_scope" -- câu hỏi pháp
luật nhưng KHÔNG thuộc Luật Hôn nhân & Gia đình (VD: luật giao thông, luật
hình sự, luật đất đai không liên quan tài sản vợ chồng), hoặc câu hỏi hoàn
toàn không liên quan (VD: hỏi code, hỏi kiến thức phổ thông).

KHÔNG gọi retrieval, KHÔNG gọi LLM để "cố trả lời cho đủ" -- giữ đúng nguyên
tắc: hệ thống PHẢI biết giới hạn phạm vi của mình, từ chối rõ ràng thay vì
trả lời sai domain rồi khiến người dùng hiểu lầm là câu trả lời có căn cứ luật.

Cách dùng (test độc lập):
    python agent/out_of_scope.py "bubble sort hoạt động như thế nào"
"""
from __future__ import annotations

import sys

# Không cần gọi LLM cho node này -- câu trả lời cố định, tiết kiệm chi phí và
# đảm bảo tuyệt đối không có rủi ro model "cố" trả lời ngoài phạm vi.
DEFAULT_MESSAGE = (
    "Mình là hệ thống hỏi-đáp chuyên về Luật Hôn nhân và Gia đình Việt Nam "
    "(kết hôn, ly hôn, tài sản vợ chồng, quyền nuôi con, cấp dưỡng, nhận con nuôi, "
    "giám hộ...), nên mình chưa thể trả lời câu hỏi này. Bạn có câu hỏi nào liên "
    "quan tới hôn nhân, gia đình mình có thể giúp không?"
)


class OutOfScopeNode:
    def run(self, question: str) -> str:
        return DEFAULT_MESSAGE

