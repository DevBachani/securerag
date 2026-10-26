# PROGRESS

## Current phase: 2 — Configuration and model providers
## Status: not started

## Environment
- OS / RAM / GPU: Windows 11 Home (10.0.27965) / ~8 GB RAM / no dedicated GPU
- LLM provider in use: ollama (model: llama3.1:latest, 8B)
- Python version: 3.12.4 (project pinned to >=3.11); uv 0.13.4
- Docker: 29.1.3 + Compose v2.40.3 (Docker Desktop)

## Completed phases
| Phase | Date | Commit | Notes |
|---|---|---|---|
| 0 — Environment setup | 2026-10-26 | chore: project setup, qdrant, smoke test | Smoke test 3/3: LLM OK, embed 384, Qdrant up. Ollama/llama3.1. |
| 1 — Synthetic corpus and manifest | 2026-10-26 | feat(data): synthetic Acme corpus with ACL manifest | 26 docs (23 md + 3 pdf), manifest + FACTS.md, 55 manifest tests pass. Traps excluded. |

## Key decisions (and why)
- LLM = Ollama / llama3.1:latest (local): no API key, no free-tier limits; machine already has it installed.
- Embeddings = BAAI/bge-small-en-v1.5 via fastembed (384-dim), NOT Ollama's nomic-embed-text (768-dim):
  the whole retrieval design (Qdrant collection size, chunk payload, "prints 384" check) is built around 384.
- GitHub: local repo only for now; no remote pushed yet.

## Eval scores so far
| Phase | Config | Faithfulness | Answer relevancy | Context precision | Context recall | Leakage rate |
|---|---|---|---|---|---|---|

## Open issues / questions
- Machine has only ~8 GB RAM. llama3.1:8b (4.9 GB) runs but is tight once Qdrant + fastembed +
  (later) the cross-encoder reranker are loaded. Watch for OOM / slowness; fallback = gemma:2b or mistral:7b.
- SPEC.md saved from a truncated paste (cut mid–Section 8). Replace with the full spec when available.
