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
    
    payload = {
        "inputs": {},
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
