# Dify × LINE チャットボット

LINEとDifyを連携したAIチャットボットです。LINEでメッセージを送ると、Difyで作成したAIアプリが応答します。

## 機能

- LINEからのメッセージをDify APIに送信
- Difyからの応答をLINEに返信
- ユーザーごとの会話履歴を保持（セッション管理）
- 会話リセット機能（「リセット」または「reset」と送信）

## セットアップ手順

### 1. 必要な準備

#### LINE Developers での設定

1. [LINE Developers Console](https://developers.line.biz/console/) にアクセス
2. 新しいプロバイダーを作成（または既存のものを選択）
3. 「Messaging API」チャネルを作成
4. 以下の情報を取得：
   - **Channel Secret**: 「チャネル基本設定」タブから
   - **Channel Access Token**: 「Messaging API設定」タブで発行

#### Dify での設定

1. [Dify](https://dify.ai/) にログイン
2. 新しいアプリを作成（チャットボットタイプ推奨）
3. アプリの設定画面から **API Key** を取得
4. APIエンドポイントを確認（通常は `https://api.dify.ai/v1`）

### 2. 環境構築

```bash
# リポジトリをクローン（または新規作成）
cd Dify_LINE_APIBot

# 仮想環境を作成
python -m venv venv

# 仮想環境を有効化
# Windows:
venv\Scripts\activate
# Mac/Linux:
source venv/bin/activate

# 依存パッケージをインストール
pip install -r requirements.txt
```

### 3. 環境変数の設定

```bash
# .env.example をコピーして .env を作成
copy .env.example .env  # Windows
cp .env.example .env    # Mac/Linux
```

`.env` ファイルを編集し、取得した値を設定：

```env
LINE_CHANNEL_ACCESS_TOKEN=実際のアクセストークン
LINE_CHANNEL_SECRET=実際のチャネルシークレット
DIFY_API_KEY=実際のDify APIキー
DIFY_API_URL=https://api.dify.ai/v1
```

### 4. アプリケーションの起動

#### 開発環境

```bash
python app.py
```

#### 本番環境

```bash
gunicorn app:app --bind 0.0.0.0:5000
```

### 5. Webhook URLの設定

LINEからメッセージを受け取るには、サーバーを公開URLでアクセス可能にする必要があります。

#### ngrok を使用する場合（開発時）

```bash
# ngrok をインストール後
ngrok http 5000
```

表示されたURLをコピー（例：`https://xxxx.ngrok.io`）

#### LINE Developers Console での設定

1. LINE Developers Console でチャネル設定を開く
2. 「Messaging API設定」タブを選択
3. 「Webhook URL」に以下を設定：
   ```
   https://xxxx.ngrok.io/callback
   ```
4. 「Webhookの利用」をオンに設定
5. 「検証」ボタンでWebhookをテスト

### 6. 動作確認

1. LINEアプリでボットを友だち追加（QRコードから）
2. メッセージを送信
3. Difyで設定したAIが応答することを確認

## 使い方

| コマンド              | 説明                                 |
| --------------------- | ------------------------------------ |
| 通常のメッセージ      | AIが応答します                       |
| `リセット` or `reset` | 会話履歴をクリアして新しい会話を開始 |
| `クリア` or `clear`   | 会話履歴をクリアして新しい会話を開始 |

## デプロイ（Render）

### 1. GitHubリポジトリの準備

```bash
git init
git add .
git commit -m "Initial commit"
```

GitHubで新しいリポジトリを作成し、プッシュ：

```bash
git remote add origin https://github.com/あなたのユーザー名/Dify_LINE_APIBot.git
git branch -M main
git push -u origin main
```

### 2. Renderでのデプロイ

1. [Render](https://render.com/) にログイン
2. 「New +」→「Web Service」を選択
3. GitHubリポジトリを接続
4. 設定：
   - **Name**: `dify-line-bot`（任意）
   - **Runtime**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`

### 3. 環境変数の設定

Renderのダッシュボードで「Environment」タブを開き、以下を設定：

| Key                         | Value                      |
| --------------------------- | -------------------------- |
| `LINE_CHANNEL_ACCESS_TOKEN` | LINEのアクセストークン     |
| `LINE_CHANNEL_SECRET`       | LINEのチャネルシークレット |
| `DIFY_API_KEY`              | DifyのAPIキー              |
| `DIFY_API_URL`              | `https://api.dify.ai/v1`   |

### 4. LINE Webhook URLの設定

デプロイ完了後、RenderのURLをコピー（例：`https://dify-line-bot.onrender.com`）

LINE Developers Consoleで：

1. 「Messaging API設定」タブを開く
2. 「Webhook URL」に設定：
   ```
   https://あなたのアプリ名.onrender.com/callback
   ```
3. 「Webhookの利用」をオンに設定
4. 「検証」ボタンでテスト

### その他のデプロイオプション

- **Heroku**: `Procfile` を使用
- **Railway**: GitHub連携で簡単デプロイ
- **AWS Lambda**: Serverless Framework で対応可能

## トラブルシューティング

### Webhook検証が失敗する

- URLが正しいか確認（`/callback` を忘れずに）
- サーバーが起動しているか確認
- `LINE_CHANNEL_SECRET` が正しいか確認

### AIが応答しない

- `DIFY_API_KEY` が正しいか確認
- Difyアプリが公開されているか確認
- Difyのクレジット/クォータを確認

### 会話が継続しない

- アプリを再起動するとメモリ上の会話履歴はクリアされます
- 永続化が必要な場合は Redis などの導入を検討

## ファイル構成

```
Dify_LINE_APIBot/
├── app.py              # メインアプリケーション
├── config.py           # 設定管理
├── requirements.txt    # 依存パッケージ
├── .env.example        # 環境変数サンプル
├── .env                # 環境変数（git管理外）
└── README.md           # このファイル
```

## ライセンス

MIT License
