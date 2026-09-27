MESSAGES = {
    "en": {
        "TOPIC_DEVELOPMENT": ("You gave a short response after your partner spoke.", "A brief response can be appropriate. Add a detail if you want to continue.", "Add a reason, example or natural follow-up."),
        "FOLLOW_UP_QUESTION": ("You invited your partner to respond with a question.", "Follow-up questions can keep both people involved.", "Acknowledge their point, then ask a specific question."),
        "TURN_BALANCE": ("This turn was relatively long.", "Long answers can be useful. You can also make room for your partner.", "Pause after your point and invite a response."),
        "CLARIFICATION": ("You asked to clarify something.", "Checking understanding can reduce misunderstandings.", "Specify which phrase you want repeated or explained."),
    },
    "ja": {
        "TOPIC_DEVELOPMENT": ("相手の発言の後に短く応じています。", "短い返答が適切な場合もあります。続けたいときは情報を一つ加えましょう。", "理由や例、自然な質問を加えてみましょう。"),
        "FOLLOW_UP_QUESTION": ("質問で相手に発言の機会を渡しています。", "追加の質問は双方の参加を促します。", "相手の内容に応じてから、具体的に質問しましょう。"),
        "TURN_BALANCE": ("この発言は比較的長く続いています。", "長い回答が役立つこともあります。相手が参加できる余地も作れます。", "意見を伝えたら一度区切り、相手の回答を促しましょう。"),
        "CLARIFICATION": ("聞き取れない点や不明な点を確認しています。", "確認することで誤解を減らせます。", "繰り返してほしい言葉や説明が必要な部分を具体的に伝えましょう。"),
    },
}
EXAMPLES = {
    "zh": {
        "TOPIC_DEVELOPMENT": "我觉得可以，因为大家都能参加。你觉得呢？",
        "FOLLOW_UP_QUESTION": "听起来很有意思。你当时为什么决定试一试呢？",
        "TURN_BALANCE": "这就是我的看法。你的经历是怎样的？",
        "CLARIFICATION": "不好意思，最后一句我没听清，可以再说一遍吗？",
    },
    "ja": {
        "TOPIC_DEVELOPMENT": "みんなが参加できるので、いいと思います。どう思いますか？",
        "FOLLOW_UP_QUESTION": "面白そうですね。やってみようと思ったきっかけは何ですか？",
        "TURN_BALANCE": "私はそう考えています。あなたはどうですか？",
        "CLARIFICATION": "すみません、最後の部分が聞き取れませんでした。もう一度お願いします。",
    },
}


def localize_insight(insight, event_type, native, target):
    result = dict(insight)
    if native in MESSAGES:
        result.update(zip(("observation", "context", "suggestion"), MESSAGES[native][event_type]))
    if target in EXAMPLES:
        result["example"] = EXAMPLES[target][event_type]
    return result
