from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any


LIBRARY_PATH = Path(__file__).resolve().parents[1] / "data" / "taskmaster_practice_library.json"
EXPECTED_CATEGORIES = {"汽车维修", "餐饮点单", "餐厅预订", "电影票务", "出行叫车"}


@lru_cache(maxsize=1)
def load_practice_library() -> dict[str, Any]:
    payload = json.loads(LIBRARY_PATH.read_text(encoding="utf-8"))
    items = payload.get("items") or []
    ids = [str(item.get("id") or "") for item in items]
    categories = [str(item.get("category") or "") for item in items]
    if len(items) != 10 or len(set(ids)) != 10:
        raise RuntimeError("Taskmaster 练习库必须恰好包含 10 条唯一素材")
    if set(categories) != EXPECTED_CATEGORIES or any(categories.count(category) != 2 for category in EXPECTED_CATEGORIES):
        raise RuntimeError("Taskmaster 练习库必须包含 5 个分类且每类 2 条")

    safe_items = []
    for item in items:
        source = item.get("source") or {}
        safe_items.append({
            "id": item["id"],
            "category": item["category"],
            "title": item["title"],
            "prompt": item["prompt"],
            "hint": item["hint"],
            "rubric": list(item.get("rubric") or []),
            "source": {
                "dataset": payload["dataset"],
                "split": source["split"],
                "instruction_id": source["instruction_id"],
                "conversation_id": source["conversation_id"],
                "utterance_index": int(source["utterance_index"]),
                "license": payload["license"],
            },
        })
    return {
        "items": safe_items,
        "total": len(safe_items),
        "categories": sorted(EXPECTED_CATEGORIES),
        "attribution": {
            "dataset": payload["dataset"],
            "label": payload["attribution"],
            "license": payload["license"],
            "url": payload["dataset_url"],
        },
    }
