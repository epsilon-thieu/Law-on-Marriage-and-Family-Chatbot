from pathlib import Path
import json
import pickle

from pyvi import ViTokenizer
from rank_bm25 import BM25Okapi

PROJECT_ROOT = Path(__file__).parent.parent
CHUNKS_PATH = PROJECT_ROOT / "data" / "processed" / "all_chunks.jsonl"
BM25_CACHE_PATH = PROJECT_ROOT / "data" / "bm25_cache.pkl"


def load_chunks(path: Path) -> list[dict]:
    chunks = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            chunks.append(json.loads(line))
    return chunks


def tokenize_vi(text: str) -> list[str]:
    return ViTokenizer.tokenize(text).split() # "tôi đi học tiếng anh"  --> ["tôi", "đi", "học", "tiếng_anh"]

def main():
    print(f"source of chunk: {CHUNKS_PATH}")
    chunks = load_chunks(CHUNKS_PATH)
    print(f"total chunks: {len(chunks)}")

    tokenized_corpus = [tokenize_vi(c["page_content"]) for c in chunks]

    bm25 = BM25Okapi(tokenized_corpus)

    cache = {
        "bm25": bm25,
        "documents": [
            {"page_content": c["page_content"], "metadata": c["metadata"]} for c in chunks
        ],
    }

    BM25_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(BM25_CACHE_PATH, "wb") as f:
        pickle.dump(cache, f)

    print(f"\nHoàn tất: đã lưu BM25 cache ({len(chunks)} chunk) vào {BM25_CACHE_PATH}")


if __name__ == "__main__":
    main()