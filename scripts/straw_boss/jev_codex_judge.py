"""Comparable Jev requests using the preserved round-2 judging envelope."""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor


def judge_pairs(history: list[dict], state: list[dict], call_ids: list[str], criteria: dict) -> list[dict]:
    # Tokenization limits only the Jev judging request, never the savings gate.
    import tiktoken

    encoder = tiktoken.get_encoding("o200k_base")
    calls = {item["call_id"]: (i, item) for i, item in enumerate(history)
             if item["type"] in ("function_call", "custom_tool_call")}
    results = {item["call_id"]: item for item in history
               if item["type"] in ("function_call_output", "custom_tool_call_output")}

    def judge(call_id: str) -> dict:
        index, call = calls[call_id]
        output = encoder.encode(json.dumps(results[call_id]["output"], ensure_ascii=False))
        target = {"call_id": call_id, "index": index,
                  "call": call.get("input", call.get("arguments")),
                  "result_excerpt": encoder.decode(output[:5000]), "full_result_tokens": len(output)}
        body = {"model": "jev-latest", "state": {"conversation": state, "target": target},
                "questions": {name: {"type": "noul", "instructions": wording,
                    "criteria": {"true": wording, "false": "The proposition is false; this material can be pruned according to the stated retention contract."}}
                    for name, wording in criteria.items()}}
        state_tokens = len(encoder.encode(json.dumps(body["state"], ensure_ascii=False)))
        if state_tokens + max(len(encoder.encode(json.dumps(q, ensure_ascii=False)))
                              for q in body["questions"].values()) >= 32000:
            raise ValueError("comparable-request-exceeds-round2-limit")
        request = urllib.request.Request("https://api.typesafe.ai/v1/systemone",
            data=json.dumps(body).encode(), headers={"Content-Type": "application/json",
            "Authorization": "Bearer " + os.environ["TYPESAFE_API_KEY"]})
        started = time.monotonic()
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                answer = json.load(response)
        except urllib.error.HTTPError as error:
            raise ValueError(f"jev-http-{error.code}") from None
        if not answer.get("model") or type(answer.get("usage", {}).get("input_tokens")) is not int:
            raise ValueError("jev-missing-model-or-usage")
        return {"call_id": call_id, "response": answer, "state_tokens": state_tokens,
                "latency_ms": round((time.monotonic() - started) * 1000)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        return list(pool.map(judge, call_ids))
