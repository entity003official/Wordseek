from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any


CATALOG_PATH = Path(__file__).resolve().parents[1] / "data" / "dialogue_practice_catalog.sqlite3"
EXPECTED_SCHEMA = "practice-materials.v1"
NAME_COLUMN = {"zh": "name_zh", "en": "name_en", "ja": "name_ja"}


class PracticeCatalogError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def _connect() -> sqlite3.Connection:
    if not CATALOG_PATH.is_file():
        raise PracticeCatalogError(
            "PRACTICE_CATALOG_UNAVAILABLE",
            "日语练习素材库尚未安装，请联系管理员重新部署。",
            retryable=True,
        )
    try:
        connection = sqlite3.connect(f"file:{CATALOG_PATH.as_posix()}?mode=ro", uri=True)
        connection.row_factory = sqlite3.Row
        schema = connection.execute(
            "SELECT value FROM metadata WHERE key='schema_version'"
        ).fetchone()
        if schema is None or schema[0] != EXPECTED_SCHEMA:
            connection.close()
            raise PracticeCatalogError(
                "PRACTICE_CATALOG_UNAVAILABLE",
                "日语练习素材库版本不兼容，请联系管理员重新构建。",
                retryable=False,
            )
        return connection
    except PracticeCatalogError:
        raise
    except sqlite3.Error as error:
        raise PracticeCatalogError(
            "PRACTICE_CATALOG_UNAVAILABLE",
            "日语练习素材库无法读取，请联系管理员检查部署文件。",
            retryable=True,
        ) from error


def _localized_taxonomy(
    connection: sqlite3.Connection, dimension: str, native_language: str
) -> dict[str, dict[str, Any]]:
    label_column = NAME_COLUMN[native_language]
    return {
        str(row["code"]): {
            "code": str(row["code"]),
            "label": str(row["label"]),
            "parent_code": row["parent_code"],
            "item_count": int(row["item_count"]),
        }
        for row in connection.execute(
            f"SELECT code, parent_code, {label_column} AS label, item_count "
            "FROM taxonomy WHERE dimension=? ORDER BY code",
            (dimension,),
        )
    }


def _context_text(raw: str) -> str:
    turns = json.loads(raw)
    return "\n".join(f"{turn['speaker']}: {turn['text']}" for turn in turns)


def _attributions(connection: sqlite3.Connection) -> list[dict[str, str]]:
    metadata = dict(connection.execute("SELECT key, value FROM metadata"))
    return [{
        "dataset": metadata["source_dataset"],
        "version": metadata["source_version"],
        "license": metadata["source_license"],
        "label": metadata["source_attribution"],
        "url": "https://github.com/nu-dialogue/real-persona-chat",
    }]


def list_japanese_practice_materials(
    native_language: str,
    category: str | None = None,
    scene: str | None = None,
    page: int = 1,
    page_size: int = 12,
) -> dict[str, Any]:
    connection = _connect()
    try:
        categories = _localized_taxonomy(connection, "category", native_language)
        scenes = _localized_taxonomy(connection, "scene", native_language)
        relationships = _localized_taxonomy(connection, "relationship", native_language)
        registers = _localized_taxonomy(connection, "register", native_language)
        if category and category not in categories:
            raise PracticeCatalogError("INVALID_PRACTICE_CATEGORY", "所选大类不存在。")
        if scene and scene not in scenes:
            raise PracticeCatalogError("INVALID_PRACTICE_SCENE", "所选小类不存在。")
        if category and scene and scenes[scene]["parent_code"] != category:
            raise PracticeCatalogError("INVALID_PRACTICE_SCENE", "所选小类不属于当前大类。")

        category_items: list[dict[str, Any]] = []
        for value in categories.values():
            child_scenes = [
                {"code": child["code"], "label": child["label"], "item_count": child["item_count"]}
                for child in scenes.values()
                if child["parent_code"] == value["code"] and child["item_count"] > 0
            ]
            if child_scenes:
                category_items.append({
                    "code": value["code"], "label": value["label"],
                    "item_count": value["item_count"], "scenes": child_scenes,
                })

        where: list[str] = []
        parameters: list[Any] = []
        if category:
            where.append("category_code=?")
            parameters.append(category)
        if scene:
            where.append("scene_code=?")
            parameters.append(scene)
        where_clause = f" WHERE {' AND '.join(where)}" if where else ""
        total = int(connection.execute(
            "SELECT COUNT(*) FROM materials" + where_clause, parameters
        ).fetchone()[0])
        rows = connection.execute(
            "SELECT * FROM materials" + where_clause +
            " ORDER BY scene_code, id LIMIT ? OFFSET ?",
            [*parameters, page_size, (page - 1) * page_size],
        ).fetchall()
        hint_column = {"zh": "hint_zh", "en": "hint_en", "ja": "hint_ja"}[native_language]
        items: list[dict[str, Any]] = []
        for row in rows:
            category_info = categories[str(row["category_code"])]
            scene_info = scenes[str(row["scene_code"])]
            context = _context_text(str(row["context_json"]))
            items.append({
                "id": row["id"],
                "category": category_info["label"],
                "category_code": row["category_code"],
                "category_label": category_info["label"],
                "scene_code": row["scene_code"],
                "scene_label": scene_info["label"],
                "title": row["title"],
                "prompt": context,
                "opening_line": row["opening_line"],
                "hidden_context": context,
                "relationship": relationships.get(str(row["relationship_code"]), {}).get("label"),
                "register": registers.get(str(row["register_code"]), {}).get("label"),
                "hint": row[hint_column],
                "rubric": [
                    "回应对方内容", "补充具体信息", "给对方继续回应的空间"
                ],
                "source": {
                    "dataset": row["source_dataset"],
                    "version": row["source_version"],
                    "conversation_id": row["source_dialogue_id"],
                    "utterance_index": row["source_turn_index"],
                    "license": row["source_license"],
                    "review_status": "auto_accepted",
                },
            })
        attributions = _attributions(connection)
        return {
            "categories": category_items,
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "attributions": attributions,
            "attribution": attributions[0],
        }
    except sqlite3.Error as error:
        raise PracticeCatalogError(
            "PRACTICE_CATALOG_UNAVAILABLE",
            "日语练习素材库读取失败，请联系管理员检查数据文件。",
            retryable=True,
        ) from error
    finally:
        connection.close()


def get_japanese_practice_material(material_id: str, native_language: str) -> dict[str, Any] | None:
    result = list_japanese_practice_materials(native_language, page=1, page_size=24)
    match = next((item for item in result["items"] if item["id"] == material_id), None)
    if match:
        return match
    connection = _connect()
    try:
        row = connection.execute(
            "SELECT category_code, scene_code FROM materials WHERE id=?", (material_id,)
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        return None
    filtered = list_japanese_practice_materials(
        native_language, category=row["category_code"], scene=row["scene_code"], page=1, page_size=24
    )
    return next((item for item in filtered["items"] if item["id"] == material_id), None)
