"""Localized Taskmaster exercises; source attribution is preserved for translations."""
from copy import deepcopy
import re
from .practice_library import load_practice_library

# Each pair is English/Japanese. Chinese instructions come from the source library.
TITLES = [
    ("Describe a car problem", "車の不具合を伝える"), ("Arrange a repair", "修理の日程を決める"),
    ("Choose a pickup location", "受け取る店舗を選ぶ"), ("Choose toppings", "トッピングを選ぶ"),
    ("Describe your ideal restaurant", "希望のレストランを伝える"), ("Confirm a reservation", "予約を確認する"),
    ("Handle a sold-out showing", "満席の場合に対応する"), ("Choose an earlier showing", "早い上映時間を選ぶ"),
    ("Arrange a pickup time", "迎えの時間を決める"), ("Say how many passengers", "乗車人数を伝える"),
]
HINTS = [
    ("Describe what happens, when it happens, and how often.", "症状、起きる場面、頻度を伝えましょう。"),
    ("Confirm the time or suggest a specific alternative.", "都合を伝え、難しければ別の日時を提案しましょう。"),
    ("Give the store location and a nearby landmark.", "店舗の場所と近くの目印を伝えましょう。"),
    ("Name your toppings and any dietary restrictions.", "希望の具材と食べられないものを伝えましょう。"),
    ("Describe two preferences, such as budget and cuisine.", "予算や料理の種類など、希望を二つ伝えましょう。"),
    ("Confirm the number of people, time, and whether to book.", "人数と時間を確認し、予約するか伝えましょう。"),
    ("Acknowledge the situation and suggest another time range.", "状況を受け止め、別の希望時間を伝えましょう。"),
    ("Say whether you want an earlier showing and give a time range.", "早い回を希望するかと、都合のよい時間帯を伝えましょう。"),
    ("Say whether you want to leave now or book a pickup time.", "今すぐ出発するか、迎えを予約するか伝えましょう。"),
    ("Give the passenger count and mention luggage or other needs.", "人数と、荷物や配慮が必要なことを伝えましょう。"),
]
SCENES = {
    "zh": ["在修车店", "预约保养", "咖啡店点单", "点披萨", "找餐厅", "餐厅订位", "买电影票", "调整观影时间", "预约接车", "乘车出行"],
    "en": ["At the repair shop", "Booking a service", "Ordering coffee", "Ordering pizza", "Finding a restaurant", "Booking a table", "Buying movie tickets", "Choosing a showtime", "Booking a pickup", "Taking a ride"],
    "ja": ["修理店で", "点検の予約", "カフェで注文", "ピザを注文", "レストランを探す", "席を予約", "映画のチケット", "上映時間を選ぶ", "迎えを予約", "車で移動"],
}
CATEGORY_CODES = [
    "car_repair", "car_repair", "food_ordering", "food_ordering", "restaurant_booking",
    "restaurant_booking", "movie_ticketing", "movie_ticketing", "ride_hailing", "ride_hailing",
]
CATEGORY_LABELS = {
    "zh": {
        "car_repair": "汽车维修", "food_ordering": "餐饮点单", "restaurant_booking": "餐厅预订",
        "movie_ticketing": "电影票务", "ride_hailing": "出行叫车",
    },
    "en": {
        "car_repair": "Car repair", "food_ordering": "Ordering food", "restaurant_booking": "Restaurant reservations",
        "movie_ticketing": "Movie tickets", "ride_hailing": "Booking a ride",
    },
    "ja": {
        "car_repair": "車の修理", "food_ordering": "飲食店で注文", "restaurant_booking": "レストラン予約",
        "movie_ticketing": "映画のチケット", "ride_hailing": "配車",
    },
}
SCENE_CODES = [
    "describe_problem", "arrange_repair", "choose_pickup_store", "choose_toppings",
    "describe_restaurant", "confirm_reservation", "sold_out_showing", "earlier_showing",
    "arrange_pickup_time", "passenger_count",
]
RELATIONSHIP_LABELS = {"zh": "顾客与服务人员", "en": "Customer and service staff", "ja": "客と店員"}
REGISTER_LABELS = {"zh": "礼貌", "en": "Polite", "ja": "丁寧"}
PROMPTS = {
    "zh": ["您预约是想处理什么问题？", "这周五可以吗？您能在早上八点半前把车送来保养吗？", "您想在哪家星巴克下单？", "好的，您想加哪些配料？", "好的，您对餐厅有什么具体要求？", "晚上七点有一张可坐两到四人的桌子，需要预订吗？", "很抱歉，这个场次已经售罄。需要帮您看看其他时间还有没有票吗？", "您想找一个更早的场次吗？", "好的，您是想现在就安排车来接您吗？", "一共有几位乘客？"],
    "ja": ["ご予約の内容を教えていただけますか？", "今週の金曜日はいかがですか？点検のため、午前八時半までにお車をお持ちいただけますか？", "どちらのスターバックスでご注文されますか？", "トッピングは何になさいますか？", "レストランについて、どのようなご希望がありますか？", "午後七時に二名から四名で利用できるテーブルが空いています。予約しましょうか？", "申し訳ありません。その回は満席です。別の時間の空席を確認しましょうか？", "もう少し早い回をお探ししましょうか？", "今すぐお迎えの車を手配しましょうか？", "何名様でご乗車ですか？"],
}
RUBRIC = {
    "zh": ["回应对方的问题", "补充具体信息", "表达清楚礼貌"],
    "en": ["Answer the question", "Include specific details", "Be clear and polite"],
    "ja": ["相手の質問に答える", "具体的な情報を加える", "明確かつ丁寧に伝える"],
}


def localized_library(target="en", native="zh", category=None, scene=None, page=1, page_size=12):
    result = deepcopy(load_practice_library())
    for i, item in enumerate(result["items"]):
        if target != "en":
            item["id"] += f"-{target}"
            item["prompt"] = PROMPTS[target][i]
            item["source"]["translated"] = True
        if native != "zh":
            index = 0 if native == "en" else 1
            item["title"] = TITLES[i][index]
            item["hint"] = HINTS[i][index]
            item["rubric"] = RUBRIC[native]
        item["title"] = SCENES[native][i]
        item["category_code"] = CATEGORY_CODES[i]
        item["category_label"] = CATEGORY_LABELS[native][CATEGORY_CODES[i]]
        item["category"] = item["category_label"]
        item["scene_code"] = SCENE_CODES[i]
        item["scene_label"] = SCENES[native][i]
        item["opening_line"] = item["prompt"]
        item["hidden_context"] = item["prompt"]
        item["relationship"] = RELATIONSHIP_LABELS[native]
        item["register"] = REGISTER_LABELS[native]
    all_items = [result["items"][i] for i in (2, 3, 4, 5, 6, 7, 8, 9, 0, 1)]
    category_codes = {item["category_code"] for item in all_items}
    scene_codes = {item["scene_code"] for item in all_items}
    if category and category not in category_codes:
        raise ValueError("所选大类不存在。")
    if scene and scene not in scene_codes:
        raise ValueError("所选小类不存在。")
    if category and scene and not any(
        item["category_code"] == category and item["scene_code"] == scene for item in all_items
    ):
        raise ValueError("所选小类不属于当前大类。")
    category_items = []
    for code in dict.fromkeys(item["category_code"] for item in all_items):
        members = [item for item in all_items if item["category_code"] == code]
        category_items.append({
            "code": code,
            "label": CATEGORY_LABELS[native][code],
            "item_count": len(members),
            "scenes": [
                {"code": item["scene_code"], "label": item["scene_label"], "item_count": 1}
                for item in members
            ],
        })
    filtered = [
        item for item in all_items
        if (not category or item["category_code"] == category)
        and (not scene or item["scene_code"] == scene)
    ]
    total = len(filtered)
    start = (page - 1) * page_size
    attribution = result["attribution"]
    return {
        "items": filtered[start:start + page_size],
        "total": total,
        "page": page,
        "page_size": page_size,
        "categories": category_items,
        "attributions": [attribution],
        "attribution": attribution,
    }


def localized_feedback(response, target="en", native="zh"):
    # These are transparent practice heuristics, not a language-proficiency score.
    detail = len(response.split()) >= 8 if target == "en" else len(re.sub(r"\s", "", response)) >= 16
    question = bool(re.search(r"[?？]|what do you|how about you|do you think|どう|いかが|ですか|ますか|吗|呢", response, re.I))
    reason = bool(re.search(r"because|for example|i think|i feel|因为|所以|例如|我觉得|から|ので|例えば|と思", response, re.I))
    messages = {
        "zh": [("你补充了具体信息。", "试着再补充一个细节。"), ("你邀请了对方继续交流。", "可以加一个自然的追问。"), ("你说明了观点或理由。", "可以补充自己的理由。")],
        "en": [("You included specific information.", "Try adding one more detail."), ("You invited the other person to respond.", "Try a natural follow-up question."), ("You shared a view or reason.", "Try explaining your reason.")],
        "ja": [("具体的な情報を加えられました。", "もう一つ具体的な情報を加えてみましょう。"), ("相手が話し続けられる問いかけがありました。", "自然な質問を加えてみましょう。"), ("意見や理由を伝えられました。", "自分の理由を添えてみましょう。")],
    }
    return [pair[0 if passed else 1] for pair, passed in zip(messages[native], (detail, question, reason))]
