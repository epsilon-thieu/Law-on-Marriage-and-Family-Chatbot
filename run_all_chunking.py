"""
Cách dùng:
    python run_all_chunking.py                # chạy hết, in tổng
    python run_all_chunking.py --only ND_82_2020   # chỉ debug 1 văn bản
"""
import argparse
import json
from pathlib import Path

import yaml

from processing.legal_splitter import (
    extract_docx_paragraphs,
    split_docx_legal,
    print_debug_report,
)

CONFIG_PATH = Path(__file__).parent / "config" / "documents.yaml"
OUTPUT_PATH = Path(__file__).parent / "data" / "processed" / "all_chunks.jsonl"


def load_documents_config() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)["documents"]


def process_one_document(doc_cfg: dict) -> list:
    skip_texts = set(doc_cfg.get("skip_texts", []))
    stop_patterns = doc_cfg.get("stop_at_patterns", [])

    elements = extract_docx_paragraphs(doc_cfg["path"], skip_texts=skip_texts)
    chunks = split_docx_legal(
        elements,
        source_name=doc_cfg["source_name"],
        stop_at_patterns=stop_patterns,
    )
    return chunks


def save_chunks_jsonl(all_chunks: list, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        for c in all_chunks:
            f.write(
                json.dumps(
                    {"page_content": c.page_content, "metadata": c.metadata},
                    ensure_ascii=False,
                )
                + "\n"
            )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--only",
        help="Chỉ chạy + in debug report cho 1 source_name (vd: ND_82_2020)",
        default=None,
    )
    args = parser.parse_args()

    docs_cfg = load_documents_config()
    if args.only:
        docs_cfg = [d for d in docs_cfg if d["source_name"] == args.only]
        if not docs_cfg:
            raise SystemExit(f"Không tìm thấy source_name={args.only} trong config")

    all_chunks = []
    print(f"{'Văn bản':<20} {'Số chunk':>10}")
    print("-" * 32)
    for doc_cfg in docs_cfg:
        try:
            chunks = process_one_document(doc_cfg)
        except Exception as e:
            print(f"[LỖI] {doc_cfg['source_name']}: {e}")
            continue

        all_chunks.extend(chunks)
        print(f"{doc_cfg['source_name']:<20} {len(chunks):>10}")

        if args.only:
            print_debug_report(chunks)  # xem chi tiết khi debug 1 file

    print("-" * 32)
    print(f"{'TỔNG':<20} {len(all_chunks):>10}\n")

    if not args.only:
        save_chunks_jsonl(all_chunks, OUTPUT_PATH)
        print(f"Đã ghi {len(all_chunks)} chunk vào: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()