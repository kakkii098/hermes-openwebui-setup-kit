# What is This
LLM のための関連サービスのコンテナです。  
ホストコンピュータの外に公開する場合、それぞれのポートへのアクセス許可(ufwなど)が必要です。
ホスト OS は Linux を想定しています。

## 注意事項
本リポジトリは公開していますが基本的に作者個人が利用する想定です。
本リポジトリは現状のままの公開となり、それの利用により発生したあらゆる損害等に作者は一切の責任等を負いません。
各自の責任と判断に基づいて利用してください。

## 初期設定
### SSL証明書の信頼
以下の手順で自己署名証明書を発行・信頼してください。

・コンテナのホストOS: 証明書を発行
```
chmod +x generate_certs.sh
/bin/bash generate_certs.sh
```

・サービスを利用するクライアントPC: 証明書を信頼
- ./volumes/nginx/certs/nginx.crt をルート証明書機関の証明書として信頼する

### 各種変数の設定
・コンテナのホストOS
.env.template をコピーして .env とし、それを編集してください。
変数の設定は .env.template のファイル内説明を参照してください。
```
cp .env.template .env
vi .env
```

### ファイアウォールの設定
コンテナのホストOS以外からコンテナ内にアクセスする場合、以下のポートへの接続を許可してください。(ufwなど)
これらのポート設定は docker-compose.yml の nginx サービスで定義しています。

| port | サービス | 詳細 |
| --- | --- | -- |
| 9000 | searxng | Web検索エンジン |
| 9001 | stt | Speech To Text |
| 9002 | tts | Text To Speech |
| 9003 | open-webui | ウェブIF |
| 9004 | hermes | ゲートウェイ(OpenAI API 互換 API/デフォルトは外部に非公開) |
| 9005 | hermes | ダッシュボード |

## コンテナ構成について
### searxng: Web検索エンジン
Web 検索を利用する際に仲介する検索サービスです。  

ポート: 9000

### stt: STT(Speech To Text)エンジン
音声入力を使用するための文字起こしサービスです。  
OpenAI API 互換のエンドポイント(/audio/transcriptions)を持っています。  

ポート: 9001

### tts: TTS(Text To Speech)エンジン
音声読み上げするためのサービスです。
OpenAI API 互換のエンドポイント(/audio/speech)を持っています。  

ポート: 9002

### open-webui : Open WebUI コンテナ
ウェブブラウザから AI にアクセスするインタフェイスを提供するコンテナです。  
ホストOSの 9003 ポート(例: 127.0.0.1:9003 )で利用出来ます。  
また、**インターネットへの公開は想定しておりません**。

ポート: 9003

### hermes : Hermes Agent コンテナ
外部の Hermes Desktop などから接続するためのエージェントコンテナです。
ホストOSの以下のポートで利用出来ます。
また、**インターネットへの公開は想定しておりません**。

ゲートウェイ(openai api 互換 api) ポート: 9004
ダッシュボードポート: 9005

### nginx : SSL プロキシ コンテナ
全てのコンテナの SSL プロキシです。
**実際にはこのコンテナを経由して他のサービスにアクセスします**


## 注意事項
以下のコンテナバージョンの hermes, open-webui の組み合わせで、open-webui が hermes api server 経由で OpenAI 互換エンドポイントにアクセスした際に、 ```/v1``` がパスから外れる以上を確認しています。

nousresearch/hermes-agent
```
sha256:adb7890916de63245523492be8f68f9d2095fecbec4e2a6dab7960381f0fc002
```
ghcr.io/open-webui/open-webui
```
sha256:975e3965dcf5832804d2f77e167920794757027c5a2046917d42023d75fac431
```

### 対策
Open AI API 互換 API の前に Nginx を噛ませて、以下のように```/chat/completions```を```/v1/chat/completions```に転送してください。
```
map $http_upgrade $connection_upgrade { 
    default upgrade;
    ''      close;
} 

# NGINX_PORT, LLM_HOST, LLM_PORT は読み替えてください
server {
    listen $NGINX_PORT ssl;
    
    ssl_certificate     /etc/nginx/ssl/xxxxxxxxxx.crt;  # Self Signed Certificates
    ssl_certificate_key /etc/nginx/ssl/xxxxxxxxxx.key;  # Self Signed Certificates Key

    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header Upgrade $http_upgrade; 
    proxy_set_header Connection $connection_upgrade;

    location /chat/completions {
        # /chat/completions だけを対象とし、/v1/chat/completions へ書き換え
        rewrite ^ /v1/chat/completions break;
        proxy_pass http://$LLM_HOST:$LLM_PORT;
    }

    location / {
        proxy_pass http:/$LLM_HOST:$LLM_PORT;
	}
}

```