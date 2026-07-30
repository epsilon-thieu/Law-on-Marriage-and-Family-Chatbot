"""
GIAI ĐOẠN: retrieval/hybrid_retriever.py trong sơ đồ TRAFFIC-RAG.

Load lại 2 index đã build sẵn:
    - data/qdrant_db      (dense, từ indexing/build_dense_index.py)
    - data/bm25_cache.pkl (sparse, từ indexing/build_bm25_cache.py)

Với 1 câu hỏi đầu vào:
    1. Dense retrieval  (e5-base, cosine)
    2. Sparse retrieval (BM25Okapi, k1=1.5, b=0.75)
    3. Trộn 2 danh sách bằng Reciprocal Rank Fusion (RRF)
    4. Kéo thêm "sibling" (Khoản liền trước/liền sau, k=2)
    5. Dò tham chiếu chéo kiểu "theo Khoản X Điều Y" -> kéo đoạn được dẫn tới
    6. Diversify: cap số đoạn cùng 1 Điều lại (~log_k=10) để tránh 1 Điều
       chiếm hết top-k

Cài đặt trước khi chạy (đã cài ở bước indexing rồi thì bỏ qua):
    pip install rank-bm25 pyvi qdrant-client sentence-transformers

Cách dùng:
    python retrieval/hybrid_retriever.py "đèn vàng có được vượt không"
"""
from __future__ import annotations

from pathlib import Path
from dataclasses import dataclass, field
import math
import pickle
import re
import sys

from pyvi import ViTokenizer
from rank_bm25 import BM25Okapi
from qdrant_client import QdrantClient
from sentence_transformers import SentenceTransformer

# ----- Cấu hình (khớp với 2 file indexing) -----
MODEL_NAME = "intfloat/multilingual-e5-base"
COLLECTION_NAME = "traffic_law"

DENSE_TOP_K = 20
SPARSE_TOP_K = 20
RRF_K = 60  # hằng số chuẩn trong công thức RRF gốc (Cormack et al., 2009)
FUSED_TOP_K = 10  # số đoạn cuối cùng trả về sau khi trộn + mở rộng

SIBLING_WINDOW = 2  # kéo thêm tối đa 2 Khoản liền trước/liền sau
DIVERSIFY_CAP = max(1, round(math.log(FUSED_TOP_K + 1, 2)))  # ~log_k=10 -> cap nhỏ

CROSS_REF_PATTERN = re.compile(
    r"(?:theo|tại)\s+[Kk]hoản\s+(\d+)\s*(?:[,.]?\s*)?[Đđ]iều\s+(\d+)"
)

PROJECT_ROOT = Path(__file__).parent.parent
BM25_CACHE_PATH = PROJECT_ROOT / "data" / "bm25_cache.pkl"
QDRANT_PATH = PROJECT_ROOT / "data" / "qdrant_db"


@dataclass
class RetrievedChunk:
    page_content: str
    metadata: dict
    # điểm/thứ hạng gốc, giữ lại để debug, không dùng để so sánh giữa dense/sparse
    dense_rank: int | None = None
    sparse_rank: int | None = None
    rrf_score: float = 0.0
    source: list[str] = field(default_factory=list)  # "dense" / "sparse" / "sibling" / "cross_ref"

    @property
    def chunk_id(self) -> str:
        """ID duy nhất để dedupe. legal_splitter.py không sinh id riêng, nên ghép
        source-chuong-muc-dieu-khoan-diem làm khóa (khớp đúng field trong metadata)."""
        meta = self.metadata
        return "|".join(
            str(meta.get(k, ""))
            for k in ("source", "chuong", "muc", "dieu", "khoan", "diem")
        )


def tokenize_vi(text: str) -> list[str]:
    """Giống hệt bước tokenize lúc build BM25 cache — PHẢI đồng nhất, không thì lệch điểm."""
    return ViTokenizer.tokenize(text).split()


class HybridRetriever:
    def __init__(self):
        print(f"Load BM25 cache từ: {BM25_CACHE_PATH}")
        with open(BM25_CACHE_PATH, "rb") as f:
            cache = pickle.load(f)
        self.bm25: BM25Okapi = cache["bm25"]
        self.documents: list[dict] = cache["documents"]

        print(f"Load Qdrant từ: {QDRANT_PATH}")
        self.client = QdrantClient(path=str(QDRANT_PATH))

        print(f"Load model encode: {MODEL_NAME}")
        self.model = SentenceTransformer(MODEL_NAME)

        # Index nhanh Điều -> list các chunk cùng Điều, phục vụ sibling + cross-ref.
        # Gộp thêm chuong/muc vào khóa để tránh 2 Điều trùng số nhưng khác Chương/Mục
        # (VD: nhiều Nghị định đều có "Điều 5" nhưng là 2 Điều hoàn toàn khác nhau).
        self._by_article: dict[tuple, list[int]] = {}
        for i, doc in enumerate(self.documents):
            meta = doc["metadata"]
            key = (meta.get("source"), meta.get("chuong"), meta.get("muc"), meta.get("dieu"))
            self._by_article.setdefault(key, []).append(i)
        # sắp xếp lại trong từng Điều theo thứ tự Khoản (giả định metadata có "khoan" là số)
        for key, idxs in self._by_article.items():
            idxs.sort(key=lambda i: self._khoan_order(self.documents[i]["metadata"]))

        # Index phụ (source, dieu) -> list chunk, dùng riêng cho cross-ref vì tham chiếu
        # chéo có thể trỏ sang Điều ở Chương/Mục khác trong cùng văn bản.
        self._by_source_dieu: dict[tuple, list[int]] = {}
        for i, doc in enumerate(self.documents):
            meta = doc["metadata"]
            key2 = (meta.get("source"), str(meta.get("dieu")))
            self._by_source_dieu.setdefault(key2, []).append(i)

    @staticmethod
    def _khoan_order(meta: dict):
        khoan = meta.get("khoan")
        try:
            return (0, int(khoan))
        except (TypeError, ValueError):
            return (1, str(khoan))

    # ---------- 1. Dense ----------
    def _dense_search(self, query: str, top_k: int = DENSE_TOP_K) -> list[RetrievedChunk]:
        # QUAN TRỌNG: e5 bắt buộc tiền tố "query: " lúc encode câu hỏi
        vector = self.model.encode(f"query: {query}", normalize_embeddings=True).tolist()
        hits = self.client.query_points(
            collection_name=COLLECTION_NAME, query=vector, limit=top_k
        ).points

        results = []
        for rank, hit in enumerate(hits):
            payload = dict(hit.payload)
            page_content = payload.pop("page_content")
            results.append(
                RetrievedChunk(
                    page_content=page_content,
                    metadata=payload,
                    dense_rank=rank,
                    source=["dense"],
                )
            )
        return results

    # ---------- 2. Sparse ----------
    def _sparse_search(self, query: str, top_k: int = SPARSE_TOP_K) -> list[RetrievedChunk]:
        tokenized_query = tokenize_vi(query)
        scores = self.bm25.get_scores(tokenized_query)
        ranked_idx = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for rank, idx in enumerate(ranked_idx):
            doc = self.documents[idx]
            results.append(
                RetrievedChunk(
                    page_content=doc["page_content"],
                    metadata=doc["metadata"],
                    sparse_rank=rank,
                    source=["sparse"],
                )
            )
        return results

    # ---------- 3. RRF fusion ----------
    @staticmethod
    def _rrf_fuse(
        dense_results: list[RetrievedChunk], sparse_results: list[RetrievedChunk]
    ) -> list[RetrievedChunk]:
        """RRF chỉ cần THỨ HẠNG, không cần quy đổi thang điểm dense/sparse (Cormack et al., 2009)."""
        merged: dict[str, RetrievedChunk] = {}

        for chunk in dense_results:
            merged[chunk.chunk_id] = chunk
            chunk.rrf_score += 1.0 / (RRF_K + chunk.dense_rank + 1)

        for chunk in sparse_results:
            key = chunk.chunk_id
            if key in merged:
                existing = merged[key]
                existing.sparse_rank = chunk.sparse_rank
                existing.source.append("sparse")
                existing.rrf_score += 1.0 / (RRF_K + chunk.sparse_rank + 1)
            else:
                chunk.rrf_score += 1.0 / (RRF_K + chunk.sparse_rank + 1)
                merged[key] = chunk

        return sorted(merged.values(), key=lambda c: c.rrf_score, reverse=True)

    # ---------- 4. Sibling expansion ----------
    def _add_siblings(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Kéo thêm tối đa SIBLING_WINDOW Khoản liền trước/liền sau trong cùng 1 Điều.
        Lý do: mức phạt tiền và mức trừ điểm của NĐ 168 hay nằm ở 2 Khoản khác nhau
        trong cùng 1 Điều -> nếu chỉ lấy đúng đoạn khớp thì dễ trả lời thiếu nửa kia."""
        extra: list[RetrievedChunk] = []
        seen_ids = {c.chunk_id for c in chunks}

        for chunk in list(chunks):
            meta = chunk.metadata
            key = (meta.get("source"), meta.get("chuong"), meta.get("muc"), meta.get("dieu"))
            siblings_idx = self._by_article.get(key, [])
            if not siblings_idx:
                continue
            try:
                pos = next(
                    i for i, idx in enumerate(siblings_idx)
                    if self.documents[idx]["page_content"] == chunk.page_content
                )
            except StopIteration:
                continue

            lo = max(0, pos - SIBLING_WINDOW)
            hi = min(len(siblings_idx), pos + SIBLING_WINDOW + 1)
            for idx in siblings_idx[lo:hi]:
                doc = self.documents[idx]
                sib = RetrievedChunk(page_content=doc["page_content"], metadata=doc["metadata"], source=["sibling"])
                if sib.chunk_id not in seen_ids:
                    seen_ids.add(sib.chunk_id)
                    extra.append(sib)

        return chunks + extra

    # ---------- 5. Cross-reference ----------
    def _add_cross_refs(self, chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
        """Bắt cụm 'theo Khoản X Điều Y' rồi kéo luôn đoạn được dẫn tới, để không trả lời
        được nửa này mà bỏ sót nửa kia (VD: điều khoản chuyển tiếp, điều dẫn chiếu)."""
        extra: list[RetrievedChunk] = []
        seen_ids = {c.chunk_id for c in chunks}

        for chunk in list(chunks):
            meta = chunk.metadata
            # Tham chiếu chéo trong luật thường trỏ tới Điều khác NHƯNG CÙNG văn bản
            # (source) và cùng Chương/Mục hiện tại không nhất thiết đúng, nên chỉ khóa
            # theo source; chuong/muc để None cho khớp mọi Chương/Mục trong văn bản đó.
            for khoan_ref, dieu_ref in CROSS_REF_PATTERN.findall(chunk.page_content):
                key2 = (meta.get("source"), dieu_ref)
                for idx in self._by_source_dieu.get(key2, []):
                    doc = self.documents[idx]
                    if str(doc["metadata"].get("khoan")) != khoan_ref:
                        continue
                    ref = RetrievedChunk(page_content=doc["page_content"], metadata=doc["metadata"], source=["cross_ref"])
                    if ref.chunk_id not in seen_ids:
                        seen_ids.add(ref.chunk_id)
                        extra.append(ref)

        return chunks + extra

    # ---------- 6. Diversify ----------
    @staticmethod
    def _diversify(chunks: list[RetrievedChunk], cap: int = DIVERSIFY_CAP) -> list[RetrievedChunk]:
        """Cap số đoạn cùng 1 Điều để tránh 1 Điều chiếm hết top-k, giữ nguyên thứ tự
        rrf_score giảm dần khi chọn."""
        counts: dict[tuple, int] = {}
        result = []
        for chunk in chunks:
            meta = chunk.metadata
            key = (meta.get("source"), meta.get("chuong"), meta.get("muc"), meta.get("dieu"))
            if counts.get(key, 0) >= cap:
                continue
            counts[key] = counts.get(key, 0) + 1
            result.append(chunk)
        return result

    # ---------- Pipeline chính ----------
    def retrieve(self, query: str, top_k: int = FUSED_TOP_K) -> list[RetrievedChunk]:
        dense_results = self._dense_search(query)
        sparse_results = self._sparse_search(query)

        fused = self._rrf_fuse(dense_results, sparse_results)
        fused_top = fused[:top_k]

        expanded = self._add_siblings(fused_top)
        expanded = self._add_cross_refs(expanded)

        return self._diversify(expanded)


def main():
    if len(sys.argv) < 2:
        print('Cách dùng: python retrieval/hybrid_retriever.py "câu hỏi của bạn"')
        return

    query = " ".join(sys.argv[1:])
    retriever = HybridRetriever()

    print(f"\nCâu hỏi: {query}\n")
    results = retriever.retrieve(query)

    for i, chunk in enumerate(results, start=1):
        meta = chunk.metadata
        print(f"[{i}] nguồn={chunk.source} rrf={chunk.rrf_score:.4f} "
              f"| {meta.get('source', '?')} - Điều {meta.get('dieu', '?')} "
              f"- Khoản {meta.get('khoan', '?')} - Điểm {meta.get('diem', '?')}")
        preview = chunk.page_content[:150].replace("\n", " ")
        print(f"    {preview}...\n")


if __name__ == "__main__":
    main()
