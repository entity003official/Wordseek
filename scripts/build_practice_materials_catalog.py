from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


CATALOG_SCHEMA = "practice-materials.v1"
DATASET_ID = "real_persona_chat_1_0_0"
REQUIRED_LICENSE_STATUS = "verified_from_local_license"
MAX_PER_SCENE = 20
MAX_CONTEXT_TURNS = 6
MAX_CONTEXT_CHARS = 1600

CATEGORY_JA = {
    "daily_life": "日常生活", "food_dining": "食事・飲食", "shopping": "買い物",
    "travel_transport": "旅行・交通", "education": "学校・学習", "workplace": "仕事",
    "social": "交流・人間関係", "services_emergency": "生活サービス・緊急対応",
}

SCENE_JA = {
    "additional_order": "追加注文", "after_sales": "アフターサービス", "airport": "空港",
    "apology": "謝罪", "attraction": "観光地", "baggage": "荷物", "bank": "銀行",
    "bus": "バス", "cafe": "カフェ", "car_rental": "レンタカー", "checkout": "会計",
    "class": "授業", "classmate_discussion": "クラスメートとの話し合い",
    "client_communication": "顧客との連絡", "colleague_chat": "同僚との会話",
    "convenience_store": "コンビニ", "daily_chat": "日常会話", "dating": "デート",
    "delivery_service": "配送サービス", "device_failure": "機器の故障",
    "dietary_restrictions": "食事制限", "directions": "道案内",
    "discount_membership": "割引・会員", "email_confirmation": "メール確認",
    "emergency_help": "緊急時の助け", "exam": "試験", "fitting": "試着",
    "food_delivery": "フードデリバリー", "gratitude": "感謝", "greeting": "あいさつ",
    "group_assignment": "グループ課題", "hobbies": "趣味", "hospital": "病院",
    "hotel": "ホテル", "housework": "家事", "interview": "面接", "invitation": "誘い",
    "leave_request": "休暇申請", "library": "図書館", "lost_item": "落とし物",
    "meals": "食事", "meeting": "会議", "misunderstanding": "誤解の解消",
    "new_friends": "新しい友人", "opinion": "意見を伝える", "party": "集まり・パーティー",
    "payment": "支払い", "pharmacy": "薬局", "phone_call": "電話", "police": "警察",
    "presentation": "発表", "price_inquiry": "価格を尋ねる", "product_search": "商品を探す",
    "refusal": "断る", "reporting": "報告", "request_help": "助けを求める",
    "restaurant_ordering": "レストランで注文", "restaurant_recommendation": "店のおすすめ",
    "restaurant_reservation": "レストラン予約", "returns_exchange": "返品・交換",
    "self_introduction": "自己紹介", "size_color": "サイズ・色", "study_abroad": "留学",
    "subway_train": "地下鉄・電車", "taxi": "タクシー", "teacher_question": "先生への質問",
    "weather": "天気", "weekend_plans": "週末の予定",
}

RELATIONSHIP_JA = {
    "classmate": "同級生", "colleague": "同僚", "customer_service": "客と店員",
    "friend": "友人", "stranger": "初対面", "superior": "上司", "teacher": "先生",
    "unknown": "一般的な相手",
}
REGISTER_JA = {"casual": "カジュアル", "polite": "丁寧", "honorific": "敬語"}

# Same transparent keyword rules as the source classifier. They let the exporter
# select an opening near the evidence that caused the scene classification.
SCENE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "weather": ("天気", "雨", "晴", "曇", "雪", "暑", "寒", "涼", "気温", "湿度", "台風", "季節"),
    "hobbies": ("趣味", "映画", "ドラマ", "アニメ", "漫画", "音楽", "ゲーム", "読書", "スポーツ", "写真", "カラオケ", "推し"),
    "weekend_plans": ("週末", "休日", "休みの日", "連休", "予定", "明日は", "今度の休み"),
    "meals": ("朝ご飯", "朝食", "昼ご飯", "昼食", "夕飯", "夕食", "晩ご飯", "料理", "食べ", "献立", "レシピ"),
    "housework": ("家事", "掃除", "洗濯", "皿洗い", "食洗機", "片付け", "ゴミ出し"),
    "self_introduction": ("初めまして", "はじめまして", "出身です", "住んでいます", "自己紹介"),
    "cafe": ("カフェ", "喫茶店", "コーヒー", "珈琲", "スターバックス", "スタバ"),
    "restaurant_ordering": ("レストラン", "外食", "居酒屋", "注文", "メニュー", "飲食店", "ラーメン屋", "焼肉"),
    "additional_order": ("追加注文", "おかわり", "もう一品"),
    "restaurant_recommendation": ("おすすめの店", "おすすめのお店", "美味しい店", "店を探"),
    "dietary_restrictions": ("アレルギー", "苦手な食べ物", "食べられない", "ベジタリアン", "ヴィーガン"),
    "checkout": ("会計", "お勘定", "レジ", "支払い"),
    "food_delivery": ("出前", "デリバリー", "ウーバーイーツ", "宅配ピザ"),
    "convenience_store": ("コンビニ", "セブンイレブン", "ファミリーマート", "ローソン"),
    "price_inquiry": ("値段", "価格", "いくら", "高い", "安い"),
    "product_search": ("買い物", "ショッピング", "商品", "通販", "ネットショップ", "購入"),
    "size_color": ("サイズ", "色違い", "カラー", "服", "洋服", "ファッション"),
    "fitting": ("試着", "着てみ"), "returns_exchange": ("返品", "交換", "返金"),
    "discount_membership": ("割引", "セール", "ポイント", "会員"),
    "directions": ("道に迷", "道案内", "行き方", "どこですか", "場所が分から"),
    "subway_train": ("電車", "地下鉄", "駅", "新幹線", "乗り換え", "ホーム"),
    "bus": ("バス", "バス停"), "taxi": ("タクシー", "配車"),
    "airport": ("空港", "飛行機", "フライト", "搭乗"),
    "hotel": ("ホテル", "旅館", "宿泊", "チェックイン"),
    "attraction": ("観光", "旅行", "温泉", "名所", "遊園地", "水族館", "動物園"),
    "car_rental": ("レンタカー", "車を借"), "baggage": ("荷物", "スーツケース", "手荷物"),
    "class": ("授業", "講義", "ゼミ"), "teacher_question": ("先生に", "教授に", "教員に"),
    "classmate_discussion": ("同級生", "クラスメイト", "同じクラス"),
    "group_assignment": ("グループ課題", "共同課題", "班で"),
    "presentation": ("発表", "プレゼン", "スピーチ"), "library": ("図書館",),
    "exam": ("試験", "テスト", "受験", "資格試験"), "study_abroad": ("留学", "海外の学校"),
    "colleague_chat": ("同僚", "職場", "会社の人", "上司", "部下"),
    "meeting": ("会議", "ミーティング", "打ち合わせ"), "reporting": ("報告", "日報", "進捗"),
    "request_help": ("手伝って", "助けて", "お願いでき", "相談が"),
    "leave_request": ("有給", "休暇", "休みを取", "欠勤"),
    "client_communication": ("取引先", "顧客", "お客様", "営業先"),
    "interview": ("面接", "就活", "転職"), "phone_call": ("電話", "通話", "折り返し"),
    "email_confirmation": ("メール", "電子メール", "送信した"),
    "new_friends": ("友達にな", "新しい友達", "知り合った", "初対面"),
    "invitation": ("誘って", "一緒に行", "行きませんか", "参加しませんか"),
    "refusal": ("断った", "断る", "遠慮します"),
    "apology": ("謝った", "ごめんなさい", "申し訳ない", "すみませんでした"),
    "gratitude": ("感謝", "ありがたい", "お礼"),
    "opinion": ("どう思", "意見", "考え方", "賛成", "反対"),
    "dating": ("デート", "恋人", "彼氏", "彼女", "恋愛"),
    "party": ("パーティー", "飲み会", "集まり", "同窓会"),
    "misunderstanding": ("誤解", "勘違い", "仲直り"),
    "hospital": ("病院", "診察", "医者", "入院", "通院"),
    "pharmacy": ("薬局", "薬を", "処方箋", "ドラッグストア"),
    "bank": ("銀行", "口座", "振込", "ATM"), "police": ("警察", "交番"),
    "delivery_service": ("宅配便", "配達", "郵便", "荷物が届"),
    "after_sales": ("修理", "保証", "サポート", "問い合わせ"),
    "lost_item": ("忘れ物", "落とし物", "なくした", "紛失"),
    "device_failure": ("故障", "壊れた", "動かない", "不具合"),
    "emergency_help": ("救急", "緊急", "助けてください", "事故"),
}

QUESTION_OR_REQUEST = re.compile(
    r"[?？]|(?:です|ます|でしょう|ません|いただけ|くれ|もらえ|どう|どこ|いつ|誰|何|なぜ|いかが)(?:か|ませんか)|"
    r"教えて|お願い|ください|一緒に|ませんか|しよう|しましょう"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def localized_rows(source: sqlite3.Connection) -> dict[tuple[str, str], tuple[str, str]]:
    return {
        (str(row[0]), str(row[1])): (str(row[2]), str(row[3]))
        for row in source.execute("SELECT dimension, code, name_zh, name_en FROM taxonomy")
    }


def excerpt_for_dialogue(
    turns: list[sqlite3.Row], scene: str
) -> tuple[int, str, list[dict[str, str]]] | None:
    if len({row["speaker"] for row in turns}) < 2:
        return None
    keywords = SCENE_KEYWORDS.get(scene, ())
    anchors = [i for i, row in enumerate(turns) if any(word in row["text"] for word in keywords)]
    if not anchors:
        return None
    candidate_indexes: set[int] = set()
    for anchor in anchors:
        candidate_indexes.update(range(max(0, anchor - 2), min(len(turns), anchor + 3)))
    ranked: list[tuple[int, int]] = []
    for index in sorted(candidate_indexes):
        if index + 1 >= len(turns) or turns[index]["speaker"] == turns[index + 1]["speaker"]:
            continue
        text = compact(turns[index]["text"])
        if not text or len(text) > 500:
            continue
        score = 4 if QUESTION_OR_REQUEST.search(text) else 0
        score += 2 if index in anchors else 0
        score += 1 if 5 <= len(text) <= 160 else 0
        ranked.append((-score, index))
    if not ranked:
        return None
    ranked.sort()
    opening_index = ranked[0][1]
    start = max(0, opening_index - (MAX_CONTEXT_TURNS - 1))
    selected = turns[start : opening_index + 1]
    alias: dict[str, str] = {}
    context: list[dict[str, str]] = []
    for row in selected:
        speaker = str(row["speaker"])
        alias.setdefault(speaker, f"speaker_{chr(65 + len(alias))}")
        context.append({"speaker": alias[speaker], "text": compact(row["text"])})
    while len(json.dumps(context, ensure_ascii=False)) > MAX_CONTEXT_CHARS and len(context) > 1:
        context.pop(0)
    if len(json.dumps(context, ensure_ascii=False)) > MAX_CONTEXT_CHARS:
        return None
    return opening_index, compact(turns[opening_index]["text"]), context


def create_schema(target: sqlite3.Connection) -> None:
    target.executescript(
        """
        PRAGMA journal_mode=DELETE;
        PRAGMA foreign_keys=ON;
        CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE taxonomy (
          dimension TEXT NOT NULL,
          code TEXT NOT NULL,
          parent_code TEXT,
          name_zh TEXT NOT NULL,
          name_en TEXT NOT NULL,
          name_ja TEXT NOT NULL,
          item_count INTEGER NOT NULL DEFAULT 0,
          PRIMARY KEY (dimension, code)
        );
        CREATE TABLE materials (
          id TEXT PRIMARY KEY,
          language TEXT NOT NULL CHECK(language = 'ja'),
          category_code TEXT NOT NULL,
          scene_code TEXT NOT NULL,
          title TEXT NOT NULL,
          opening_line TEXT NOT NULL,
          context_json TEXT NOT NULL,
          hint_zh TEXT NOT NULL,
          hint_en TEXT NOT NULL,
          hint_ja TEXT NOT NULL,
          relationship_code TEXT NOT NULL,
          register_code TEXT NOT NULL,
          intent_code TEXT NOT NULL,
          source_dataset TEXT NOT NULL,
          source_version TEXT NOT NULL,
          source_dialogue_id TEXT NOT NULL,
          source_license TEXT NOT NULL,
          source_attribution TEXT NOT NULL,
          source_turn_index INTEGER NOT NULL,
          quality_score REAL NOT NULL,
          confidence REAL NOT NULL
        );
        CREATE INDEX ix_materials_category_scene_id ON materials(category_code, scene_code, id);
        CREATE INDEX ix_materials_scene_id ON materials(scene_code, id);
        """
    )


def build_catalog(source_path: Path, target_path: Path, report_path: Path) -> dict[str, Any]:
    source = sqlite3.connect(f"file:{source_path.as_posix()}?mode=ro", uri=True)
    source.row_factory = sqlite3.Row
    dataset = source.execute("SELECT * FROM datasets WHERE id = ?", (DATASET_ID,)).fetchone()
    if dataset is None:
        raise RuntimeError(f"源库缺少数据集 {DATASET_ID}")
    if dataset["license_status"] != REQUIRED_LICENSE_STATUS:
        raise RuntimeError(
            f"拒绝导出 {DATASET_ID}: license_status={dataset['license_status']!r}，"
            f"必须为 {REQUIRED_LICENSE_STATUS!r}"
        )
    names = localized_rows(source)
    candidates = source.execute(
        """
        SELECT * FROM dialogues
        WHERE dataset_id = ?
          AND review_status = 'auto_accepted'
          AND quality_flags_json = '[]'
          AND quality_score >= 3.5
        ORDER BY primary_category, scene, quality_score DESC, confidence DESC, id
        """,
        (DATASET_ID,),
    ).fetchall()
    by_scene: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in candidates:
        by_scene[str(row["scene"])].append(row)

    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.unlink(missing_ok=True)
    target = sqlite3.connect(target_path)
    create_schema(target)
    excluded = Counter()
    counts = Counter()
    selected_ids: list[str] = []

    for scene in sorted(by_scene):
        for dialogue in by_scene[scene]:
            if counts[scene] >= MAX_PER_SCENE:
                break
            turns = source.execute(
                "SELECT turn_index, speaker, text FROM utterances WHERE dialogue_id = ? ORDER BY turn_index",
                (dialogue["id"],),
            ).fetchall()
            excerpt = excerpt_for_dialogue(turns, scene)
            if excerpt is None:
                excluded["invalid_excerpt"] += 1
                continue
            opening_index, opening_line, context = excerpt
            material_id = "rpc-" + hashlib.sha256(
                f"{dialogue['source_dialogue_id']}:{opening_index}".encode("utf-8")
            ).hexdigest()[:16]
            title = opening_line if len(opening_line) <= 72 else opening_line[:71] + "…"
            target.execute(
                """
                INSERT INTO materials VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    material_id, "ja", dialogue["primary_category"], scene, title, opening_line,
                    json.dumps(context, ensure_ascii=False, separators=(",", ":")),
                    "先回应对方，再补充一个具体细节。",
                    "Respond to your partner, then add one specific detail.",
                    "相手に答えてから、具体的な情報を一つ加えてみましょう。",
                    dialogue["relationship"], dialogue["register_level"], dialogue["intent"],
                    dataset["name"], dataset["version"], dialogue["source_dialogue_id"],
                    dataset["license"], dataset["attribution"], opening_index,
                    float(dialogue["quality_score"]), float(dialogue["confidence"]),
                ),
            )
            counts[scene] += 1
            selected_ids.append(material_id)

    category_counts = Counter()
    for row in target.execute("SELECT category_code, COUNT(*) FROM materials GROUP BY category_code"):
        category_counts[row[0]] = row[1]
    for (dimension, code), (name_zh, name_en) in sorted(names.items()):
        if dimension not in {"category", "scene", "relationship", "register"}:
            continue
        if dimension == "scene" and counts[code] == 0:
            continue
        if dimension == "category" and category_counts[code] == 0:
            continue
        parent = None
        if dimension == "scene":
            parent = source.execute(
                "SELECT parent_code FROM taxonomy WHERE dimension='scene' AND code=?", (code,)
            ).fetchone()[0]
        name_ja = (
            CATEGORY_JA.get(code) if dimension == "category" else
            SCENE_JA.get(code) if dimension == "scene" else
            RELATIONSHIP_JA.get(code) if dimension == "relationship" else
            REGISTER_JA.get(code)
        ) or name_en
        item_count = counts[code] if dimension == "scene" else category_counts[code] if dimension == "category" else 0
        target.execute(
            "INSERT INTO taxonomy VALUES (?,?,?,?,?,?,?)",
            (dimension, code, parent, name_zh, name_en, name_ja, item_count),
        )

    metadata = {
        "schema_version": CATALOG_SCHEMA,
        "target_language": "ja",
        "source_dataset_id": DATASET_ID,
        "source_dataset": str(dataset["name"]),
        "source_version": str(dataset["version"]),
        "source_license": str(dataset["license"]),
        "source_license_status": str(dataset["license_status"]),
        "source_attribution": str(dataset["attribution"]),
        "source_database_sha256": sha256_file(source_path),
        "selection_order": "category, scene, quality_score desc, confidence desc, dialogue id",
    }
    target.executemany("INSERT INTO metadata(key,value) VALUES (?,?)", sorted(metadata.items()))
    target.commit()
    target.execute("VACUUM")
    target.close()
    source.close()

    report: dict[str, Any] = {
        "schema_version": CATALOG_SCHEMA,
        "source_database": "data/dialogue-materials/dialogue_materials.sqlite3",
        "source_database_sha256": metadata["source_database_sha256"],
        "output_database": "backend/app/data/dialogue_practice_catalog.sqlite3",
        "dataset": {
            "id": DATASET_ID, "name": dataset["name"], "version": dataset["version"],
            "license": dataset["license"], "license_status": dataset["license_status"],
            "attribution": dataset["attribution"],
        },
        "filters": {
            "review_status": "auto_accepted", "quality_flags": [], "minimum_quality_score": 3.5,
            "maximum_per_scene": MAX_PER_SCENE, "maximum_context_turns": MAX_CONTEXT_TURNS,
            "maximum_context_characters": MAX_CONTEXT_CHARS,
        },
        "counts": {
            "eligible_dialogues": len(candidates), "selected_materials": len(selected_ids),
            "categories": len(category_counts), "scenes": len(counts),
            "excluded": dict(sorted(excluded.items())),
        },
        "category_counts": dict(sorted(category_counts.items())),
        "scene_counts": dict(sorted(counts.items())),
        "material_ids_sha256": hashlib.sha256("\n".join(selected_ids).encode("utf-8")).hexdigest(),
        "safety": {
            "contains_jmultiwoz": False, "contains_persona_attributes": False,
            "contains_demographics": False, "contains_original_speaker_ids": False,
            "contains_pending_review": False,
        },
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    project = Path(__file__).resolve().parents[1]
    workspace = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description="从完整对话素材库生成日语练习精选库")
    parser.add_argument(
        "--source", type=Path,
        default=workspace / "data" / "dialogue-materials" / "dialogue_materials.sqlite3",
    )
    parser.add_argument(
        "--output", type=Path,
        default=project / "backend" / "app" / "data" / "dialogue_practice_catalog.sqlite3",
    )
    parser.add_argument(
        "--report", type=Path,
        default=project / "backend" / "app" / "data" / "dialogue_practice_catalog.report.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.source.is_file():
        raise SystemExit(f"找不到完整素材库: {args.source}")
    report = build_catalog(args.source, args.output, args.report)
    print(json.dumps(report["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
