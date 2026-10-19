"""查看课程向量库（RAG 归档）情况。

用法：
  python scripts/view_kb.py                 # 列出所有会话的向量库与条目数
  python scripts/view_kb.py --session <会话ID>   # 查看某会话入库明细（id + 元数据 + 文本摘要）
  python scripts/view_kb.py --session <ID> --full  # 显示入库全文
  python scripts/view_kb.py --query "逐差法" --session <ID>  # 检索测试
"""

import argparse
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

SESSIONS = ROOT / "data" / "output" / "sessions"


def list_sessions():
    print(f"{'会话ID':24s} {'名称':20s} {'kb_db':>6s} {'条目':>4s}")
    idx = {}
    idx_path = SESSIONS / "sessions.json"
    if idx_path.exists():
        idx = {s["id"]: s.get("name", "") for s in json.loads(idx_path.read_text(encoding="utf-8")).get("sessions", [])}
    for d in sorted(SESSIONS.iterdir()):
        if not d.is_dir():
            continue
        kb = d / "kb_db"
        count = "-"
        if kb.exists():
            count = _count(d)
        print(f"{d.name:24s} {idx.get(d.name, ''):20s} {str(kb.exists()):>6s} {str(count):>4s}")


def _count(session_dir):
    try:
        kb = _open(session_dir)
        return kb.collection.count()
    except Exception as e:
        return f"err:{e}"


def _open(session_dir):
    from experiment_report_grader.embedding.chroma import Chroma
    return Chroma(config={}, session_dir=str(SESSIONS / session_dir))


def show(session_dir, full=False):
    kb = _open(session_dir)
    col = kb.collection
    n = col.count()
    print(f"会话 {session_dir} 向量库条目数: {n}")
    if n == 0:
        return
    data = col.get(include=["documents", "metadatas"])
    for doc_id, doc, meta in zip(data["ids"], data["documents"], data["metadatas"]):
        print(f"\n— {doc_id}")
        print(f"  元数据: {json.dumps(meta, ensure_ascii=False)}")
        text = (doc or "").replace("\n", " ")
        print(f"  正文: {text if full else text[:120] + ('…' if len(text) > 120 else '')}")


def query(session_dir, q):
    kb = _open(session_dir)
    hits = kb.collection.query(query_texts=[q], n_results=5, include=["documents", "metadatas", "distances"])
    print(f"检索「{q}」Top5：")
    for doc_id, doc, meta, dist in zip(hits["ids"][0], hits["documents"][0],
                                       hits["metadatas"][0], hits["distances"][0]):
        print(f"  {doc_id}  相似度≈{1 - dist:.3f}  {(doc or '')[:80].replace(chr(10), ' ')}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--session")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--query")
    args = ap.parse_args()
    if args.session and args.query:
        query(args.session, args.query)
    elif args.session:
        show(args.session, args.full)
    else:
        list_sessions()
