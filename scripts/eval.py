"""Retrieval and answer evaluation against a running API.

    uv run python scripts/eval.py                       # API at http://localhost:8000
    API_URL=http://host:8000 TOP_K=3 uv run python scripts/eval.py

Uses ADMIN_API_KEY from the environment (or .env). It:
  1. creates a throwaway tenant and uploads every file in eval/corpus/,
  2. asks each question in eval/questions.jsonl through POST /queries,
  3. reports, per question and overall:
       - hit@k: the expected document is among the retrieved sources
       - reciprocal rank: 1 / position of the expected document (0 if missing)
       - keyword recall: share of the expected keywords found in the answer (case-insensitive)
  4. prints the tokens and estimated cost the run used, then deletes the tenant.

What the numbers mean depends on the configured providers: with the default fake embeddings and
fake LLM it measures word-overlap retrieval and an extractive placeholder answer, not a real model.
"""

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

API_URL = os.environ.get("API_URL", "http://localhost:8000")
TOP_K = int(os.environ.get("TOP_K", "5"))
ADMIN = {"Authorization": f"Bearer {os.environ.get('ADMIN_API_KEY', '')}"}


def parse_sse(body: str) -> list[tuple[str, Any]]:
    events = []
    for block in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in block.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


def run(client: httpx.Client) -> int:
    created = client.post("/admin/tenants", headers=ADMIN, json={"name": f"eval-{uuid.uuid4()}"})
    created.raise_for_status()
    tenant_id = created.json()["data"]["tenant"]["id"]
    auth = {"Authorization": f"Bearer {created.json()['data']['apiKey']}"}

    try:
        for path in sorted((ROOT / "eval" / "corpus").glob("*.md")):
            response = client.post(
                "/documents",
                headers=auth,
                files={"file": (path.name, path.read_bytes(), "text/markdown")},
            )
            response.raise_for_status()

        cases = [
            json.loads(line)
            for line in (ROOT / "eval" / "questions.jsonl").read_text().splitlines()
            if line.strip()
        ]
        hits, reciprocal_ranks, recalls = [], [], []
        input_tokens = output_tokens = 0
        cost = 0.0

        print(f"{'hit':>4} {'rank':>4} {'kw':>5}  question")
        for case in cases:
            response = client.post(
                "/queries", headers=auth, json={"question": case["question"], "topK": TOP_K}
            )
            response.raise_for_status()
            events = parse_sse(response.text)
            sources = [s["filename"] for s in events[0][1]["sources"]]
            answer = "".join(data["text"] for name, data in events if name == "token").lower()
            done = events[-1][1]

            rank = (
                sources.index(case["expected_document"]) + 1
                if case["expected_document"] in sources
                else 0
            )
            found = [kw for kw in case["keywords"] if kw.lower() in answer]
            recall = len(found) / len(case["keywords"])

            hits.append(rank > 0)
            reciprocal_ranks.append(1 / rank if rank else 0.0)
            recalls.append(recall)
            input_tokens += done.get("inputTokens", 0)
            output_tokens += done.get("outputTokens", 0)
            cost += float(done.get("estimatedCostUsd", 0))
            print(
                f"{'yes' if rank else 'no':>4} {rank or '-':>4} {recall:>5.2f}  {case['question']}"
            )

        n = len(cases)
        print()
        print(f"Questions        {n}")
        print(f"Hit@{TOP_K:<12} {sum(hits) / n:.2f}")
        print(f"MRR              {sum(reciprocal_ranks) / n:.2f}")
        print(f"Keyword recall   {sum(recalls) / n:.2f}")
        print(f"Tokens           {input_tokens} in / {output_tokens} out")
        print(f"Estimated cost   ${cost:.6f} (from the configured LLM_*_USD_PER_MTOK prices)")
        return 0
    finally:
        client.delete(f"/admin/tenants/{tenant_id}", headers=ADMIN)


if __name__ == "__main__":
    with httpx.Client(base_url=API_URL, timeout=120) as http:
        sys.exit(run(http))
