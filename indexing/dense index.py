from pathlib import Path
import json

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from sentence_transformers import SentenceTransformer

# Cấu hình
MODEL_NAME = "intfloat/multilingual-e5-base"
COLLECTION_NAME = "matrimonial_law"
BATCH_SIZE = 32

PROJECT_ROOT = Path(__file__).parent.parent
CHUNKS_PATH = PROJECT_ROOT / "data" / "processed" / "all_chunks.jsonl"
QDRANT_PATH = PROJECT_ROOT / "data" / "qdrant_db"  # Qdrant lưu file ngay tại đây, không cần server


def load_chunks(path: Path) -> list[dict]:
    chunks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    return chunks


def main():
    print(f"source of chunk: {CHUNKS_PATH}")
    chunks = load_chunks(CHUNKS_PATH)
    print(f"total chunks: {len(chunks)}")

    model = SentenceTransformer(MODEL_NAME)
    vector_dim = model.get_sentence_embedding_dimension()

    QDRANT_PATH.parent.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(QDRANT_PATH))

    if client.collection_exists(COLLECTION_NAME):
        client.delete_collection(COLLECTION_NAME)
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(size=vector_dim, distance=Distance.COSINE),
    )

    # QUAN TRỌNG: e5 bắt buộc tiền tố "passage: " khi encode văn bản để lưu trữ
    # (và "query: " khi encode câu hỏi lúc retrieve, xem retrieval/hybrid_retriever.py)
    texts_to_encode = [f"passage: {c['page_content']}" for c in chunks]

    print("Đang encode toàn bộ chunk")
    embeddings = model.encode(
        texts_to_encode,
        batch_size=BATCH_SIZE,
        show_progress_bar=True,
        normalize_embeddings=True,  # cần chuẩn hoá vì dùng Distance.COSINE
    )

    print("Đang upload vào Qdrant")
    points = [
        PointStruct(
            id=i,
            vector=embeddings[i].tolist(),
            payload={"page_content": chunks[i]["page_content"], **chunks[i]["metadata"]},
        )
        for i in range(len(chunks))
    ]
    client.upsert(collection_name=COLLECTION_NAME, points=points)

    print(f"\nHoàn tất: {len(points)} vector đã lưu vào collection '{COLLECTION_NAME}'")


if __name__ == "__main__":
    main()