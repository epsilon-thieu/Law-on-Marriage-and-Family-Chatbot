"""
GIAI ĐOẠN: agent/legal_rag.py trong LangGraph Agent — HN&GD-RAG.

Node được gọi khi `analyzer` phân loại category="legal_rag". Nhiệm vụ:
    1. Lấy expanded_queries từ AnalyzerResult (đã có từ agent/analyzer.py)
    2. Gọi HybridRetriever cho TỪNG query (câu gốc + các câu viết lại)
    3. Gộp + dedupe kết quả từ nhiều query (vì mỗi query trả về top-k riêng,
       có thể trùng lặp hoặc bổ sung cho nhau)
    4. Convert sang ContextChunk rồi đưa qua LegalAnswerGenerator để sinh câu trả lời cuối

Vì sao phải gọi retrieval nhiều lần (theo từng expanded_query) thay vì 1 lần?
    Đây chính là bước tác giả gốc đo được hiệu quả nhất: viết lại câu hỏi thành
    nhiều cách diễn đạt kéo Recall@10 từ 0,324 -> 0,581. Nếu chỉ dùng đúng 1
    câu hỏi gốc để retrieve thì bỏ lỡ phần lớn lợi ích của bước analyzer.

Cách dùng (test độc lập, ráp cả 3 file lại thành 1 luồng hoàn chỉnh):
    python agent/legal_rag.py "vợ nhận được gì sau khi ly hôn"
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agent.analyzer import Analyzer, AnalyzerResult
from retrieval.hybrid_retriever import HybridRetriever, RetrievedChunk
from generation.legal_answer_generator import (
    LegalAnswerGenerator,
    ContextChunk,
    GeneratedAnswer,
)

MAX_CONTEXT_CHUNKS = 20


@dataclass
class LegalRagResult:
    generated: GeneratedAnswer
    num_chunks_used: int


def _merge_dedupe(all_results: list[list[RetrievedChunk]]) -> list[RetrievedChunk]:
    """Gộp kết quả từ nhiều query lại, dedupe theo chunk_id, giữ điểm rrf_score
    cao nhất nếu 1 chunk xuất hiện ở nhiều query (vì càng nhiều query cùng tìm
    ra 1 chunk thì chunk đó càng có khả năng liên quan thật sự)."""
    merged: dict[str, RetrievedChunk] = {}
    for results in all_results:
        for chunk in results:
            key = chunk.chunk_id
            if key not in merged or chunk.rrf_score > merged[key].rrf_score:
                merged[key] = chunk
    return sorted(merged.values(), key=lambda c: c.rrf_score, reverse=True)


def _to_context_chunks(chunks: list[RetrievedChunk]) -> list[ContextChunk]:
    return [ContextChunk(page_content=c.page_content, metadata=c.metadata) for c in chunks]


class LegalRagNode:
    def __init__(self):
        self.retriever = HybridRetriever()
        self.generator = LegalAnswerGenerator()

    def run(self, question: str, analyzer_result: AnalyzerResult) -> LegalRagResult:
        queries = [question] + list(analyzer_result.expanded_queries)

        all_results = [self.retriever.retrieve(q) for q in queries]
        merged = _merge_dedupe(all_results)[:MAX_CONTEXT_CHUNKS]

        context_chunks = _to_context_chunks(merged)
        generated = self.generator.generate(question, context_chunks)

        return LegalRagResult(generated=generated, num_chunks_used=len(context_chunks))


# def main():
#     if len(sys.argv) < 2:
#         print('Cách dùng: python agent/legal_rag.py "câu hỏi của bạn"')
#         return
#
#     question = " ".join(sys.argv[1:])
#
#     print("Đang phân tích câu hỏi (analyzer)...")
#     analyzer = Analyzer()
#     analyzer_result = analyzer.analyze(question)
#
#     if analyzer_result.category != "legal_rag":
#         print(f"\nCâu hỏi này được phân loại là '{analyzer_result.category}', "
#               f"không phải 'legal_rag' -- node này chỉ nên chạy khi category=legal_rag.")
#         print("(vẫn chạy tiếp để bạn test, nhưng lưu ý khi ráp vào graph.py thật "
#               "thì route sẽ tự chặn, không gọi node này)")
#
#     print("Đang khởi tạo retriever + generator (load model)...")
#     node = LegalRagNode()
#
#     print("Đang truy xuất context + sinh câu trả lời...")
#     result = node.run(question, analyzer_result)
#
#     print(f"\nCâu hỏi: {question}")
#     print(f"topic: {analyzer_result.topic} | role: {analyzer_result.relationship_role}")
#     print(f"Số chunk context dùng: {result.num_chunks_used}\n")
#
#     g = result.generated
#     print(f"answerable   : {g.answerable}")
#     print(f"answer       : {g.answer}")
#     print(f"missing_info : {g.missing_info}")
#     print("citations    :")
#     for c in g.citations:
#         meta = c["metadata"]
#         print(f"  [{c['index']}] {meta.get('source')} - Điều {meta.get('dieu')} - Khoản {meta.get('khoan')}")
#     if g.dropped_citations:
#         print(f"Đã cắt bỏ citation bịa: {g.dropped_citations}")
#
#
# if __name__ == "__main__":
#     main()