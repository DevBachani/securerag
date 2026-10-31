"""Ask the baseline RAG a question from the command line.

Usage:
  uv run python scripts/ask.py "How many earned leaves do employees get?"
  uv run python scripts/ask.py --top-k 6 "What is the Q2 FY27 budget?"
"""

from __future__ import annotations

import argparse
import sys

from securerag.db.session import load_principal
from securerag.rag import answer

# Model output can contain Unicode (e.g. narrow no-break spaces) that the Windows
# cp1252 console cannot encode; force UTF-8 so printing never crashes.
sys.stdout.reconfigure(encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask the baseline RAG a question.")
    parser.add_argument("question", help="The question to answer.")
    parser.add_argument("--user", default="u_ceo", help="User id asking (default u_ceo).")
    parser.add_argument("--top-k", type=int, default=None, help="Chunks to retrieve.")
    args = parser.parse_args()

    principal = load_principal(args.user)
    result = answer(args.question, principal, top_k=args.top_k)

    print(f"Q: {args.question}   (as {principal.id}: {', '.join(principal.groups)})\n")
    print("Answer:")
    print(result["answer"])

    print("\nSources:")
    if result["citations"]:
        for c in result["citations"]:
            location = c["section"] or (f"Page {c['page']}" if c["page"] else "")
            suffix = f" - {location}" if location else ""
            print(f"  [{c['n']}] {c['title']}{suffix} ({c['doc_id']})")
    else:
        print("  (none cited)")

    if result["refused"]:
        print("\n[refused: not enough information in the corpus]")


if __name__ == "__main__":
    main()
