"""
Dify × LINE チャットボット
LINEからのメッセージをDify APIに送信し、AIの応答をLINEに返信します。
"""

import hashlib
import hmac
import base64
import requests
from flask import Flask, request, abort, jsonify
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent
)
from linebot.v3.exceptions import InvalidSignatureError

import config

app = Flask(__name__)

# LINE Bot API 設定
configuration = Configuration(access_token=config.LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(config.LINE_CHANNEL_SECRET)

# ユーザーごとの会話IDを保持（セッション管理用）
user_conversations = {}

# ユーザーごとの設定を保持
user_settings = {}


def call_dify_api(user_id: str, message: str) -> str:
    """
    Dify APIを呼び出してAIの応答を取得します。
    
    Args:
        user_id: LINEユーザーID（会話の識別に使用）
        message: ユーザーからのメッセージ
    
    Returns:
        AIからの応答テキスト
    """
    headers = {
        "Authorization": f"Bearer {config.DIFY_API_KEY}",
        "Content-Type": "application/json"
    }
    
    # 会話IDがあれば継続、なければ新規会話
    conversation_id = user_conversations.get(user_id)
    
    # ユーザー設定から入力変数を取得（空の値は送信しない）
    settings = user_settings.get(user_id, {})
    inputs = {}
    if settings.get("age"):
        inputs["age"] = settings["age"]
    if settings.get("address"):
        inputs["address"] = settings["address"]
    if settings.get("tenki"):
        inputs["tenki"] = settings["tenki"]
    
    payload = {
        "inputs": inputs,
        "query": message,
        "response_mode": "blocking",
        "user": user_id
    }
    
    # 既存の会話があれば会話IDを追加
    if conversation_id:
        payload["conversation_id"] = conversation_id
    
    try:
        response = requests.post(
            f"{config.DIFY_API_URL}/chat-messages",
            headers=headers,
            json=payload,
            timeout=60
        )
        response.raise_for_status()
        
        data = response.json()
        
        # 会話IDを保存（次回の会話継続用）
        if "conversation_id" in data:
            user_conversations[user_id] = data["conversation_id"]
        
        return data.get("answer", "申し訳ありません。応答を生成できませんでした。")
        
    except requests.exceptions.Timeout:
        return "応答がタイムアウトしました。もう一度お試しください。"
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Dify API error: {e}")
        # エラーレスポンスの詳細をログ出力
        if hasattr(e, 'response') and e.response is not None:
            app.logger.error(f"Response status: {e.response.status_code}")
            app.logger.error(f"Response body: {e.response.text}")
        return "エラーが発生しました。しばらくしてからもう一度お試しください。"


def handle_settings_command(user_id: str, message: str) -> str:
    """
    設定コマンドを処理します。
    
    Args:
        user_id: LINEユーザーID
        message: 設定コマンド（例: "設定 年齢 3歳"）
    
    Returns:
        応答メッセージ
    """
    # ユーザー設定を初期化
    if user_id not in user_settings:
        user_settings[user_id] = {}
    
    # コマンドをパース
    parts = message.split(" ", 2)
    if len(parts) < 3:
        return "設定形式: 設定 [項目] [値]\n\n例:\n・設定 年齢 3歳\n・設定 最寄り駅 渋谷駅\n・設定 天気 晴れ"
    
    key = parts[1]
    value = parts[2]
    
    # キーのマッピング
    key_mapping = {
        "年齢": "age",
        "age": "age",
        "最寄り駅": "address",
        "駅": "address",
        "address": "address",
        "天気": "tenki",
        "tenki": "tenki"
    }
    
    if key in key_mapping:
        user_settings[user_id][key_mapping[key]] = value
        return f"設定を保存しました: {key} = {value}"
    else:
        return f"不明な設定項目: {key}\n\n設定可能な項目:\n・年齢\n・最寄り駅\n・天気"


@app.route("/", methods=["GET"])
def index():
    """ヘルスチェック用エンドポイント"""
    return jsonify({
        "status": "ok",
        "message": "Dify × LINE Bot is running!"
    })


@app.route("/callback", methods=["POST"])
def callback():
    """
    LINE Webhookのコールバックエンドポイント
    LINEからのWebhookリクエストを受け取り、署名を検証して処理します。
    """
    # 署名の検証
    signature = request.headers.get("X-Line-Signature")
    
    if not signature:
        abort(400)
    
    body = request.get_data(as_text=True)
    app.logger.info(f"Request body: {body}")
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature")
        abort(400)
    
    return "OK"


@handler.add(MessageEvent, message=TextMessageContent)
def handle_text_message(event: MessageEvent):
    """
    テキストメッセージを処理します。
    ユーザーからのメッセージをDifyに送信し、応答をLINEに返信します。
    """
    user_id = event.source.user_id
    user_message = event.message.text
    
    app.logger.info(f"User {user_id}: {user_message}")
    
    # 特殊コマンドの処理
    if user_message.lower() in ["リセット", "reset", "クリア", "clear"]:
        # 会話履歴をリセット
        if user_id in user_conversations:
            del user_conversations[user_id]
        reply_text = "会話履歴をリセットしました。新しい会話を始めましょう！"
    
    # 設定コマンドの処理
    elif user_message.startswith("設定 "):
        reply_text = handle_settings_command(user_id, user_message)
    
    elif user_message.lower() in ["設定確認", "設定"]:
        # 現在の設定を表示
        settings = user_settings.get(user_id, {})
        if settings:
            reply_text = f"現在の設定:\n・年齢: {settings.get('age', '未設定')}\n・最寄り駅: {settings.get('address', '未設定')}\n・天気: {settings.get('tenki', '未設定')}"
        else:
            reply_text = "設定がありません。\n\n設定方法:\n・設定 年齢 3歳\n・設定 最寄り駅 渋谷駅\n・設定 天気 晴れ"
    
    else:
        # Dify APIを呼び出して応答を取得
        reply_text = call_dify_api(user_id, user_message)
    
    # LINEに返信
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply_text)]
            )
        )


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=config.PORT,
        debug=config.DEBUG
    )
