#!/bin/sh

SYSTEM_CA="/etc/ssl/certs/ca-certificates.crt"
CERTS_DIR="/etc/nginx/external-server-certs"
COMBINED_CA="$CERTS_DIR/combined-ca.crt"

echo "Generating combined CA bundle..."

# システム標準の証明書をベースとしてコピー
if [ -f "$SYSTEM_CA" ]; then
    cp "$SYSTEM_CA" "$COMBINED_CA"
else
    echo "Warning: System CA bundle not found at $SYSTEM_CA"
    > "$COMBINED_CA"
fi

# certs ディレクトリ内の .crt ファイルをすべて結合（※自分自身の combined-ca.crt は除外）
for crt in "$CERTS_DIR"/*.crt; do
    if [ -f "$crt" ] && [ "$(basename "$crt")" != "combined-ca.crt" ]; then
        echo "Appending custom CA: $(basename "$crt")"
        echo "" >> "$COMBINED_CA"
        cat "$crt" >> "$COMBINED_CA"
    fi
done

echo "CA bundle generation completed."
echo "Processing Nginx template with envsubst..."
# テンプレートファイルから環境変数を展開し、設定ファイルを生成
# （使用している環境変数をドル記号付きでリストアップして渡すか、シェル変数として自動展開させる）
envsubst '$OPENAI_API_BASE_URL' \
    < /etc/nginx/templates/default.conf.template \
    > /etc/nginx/conf.d/default.conf

# Nginxをフォアグラウンドで起動
exec nginx -g "daemon off;"