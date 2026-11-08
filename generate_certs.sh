#!/bin/bash
# ホストの IP アドレス(IPv4/LAN内)
HOST_IP="$(hostname -I | grep -oE '192.168.[0-9]+.[0-9]+')" # 192.168.xxx.xxx のアドレスを取り出し
P12_PASSWORD="changeIt"

# Nginxコンテナ名
NGINX_CONTAINER="nginx"

echo "Checking if Nginx container '$NGINX_CONTAINER' is running..."

# コンテナが起動中か判定
if [ "$(docker ps -q -f name=^/${NGINX_CONTAINER}$)" ]; then
    echo "--------------------------------------------------------"
    echo "WARNING: Nginx container '$NGINX_CONTAINER' is currently running."
    echo "To generate new SSL certificates, the container must be stopped."
    echo "--------------------------------------------------------"
    read -p "Do you want to stop the container now? (y/n): " confirm
    if [[ $confirm == [yY] ]]; then
        echo "Stopping Nginx container..."
        docker stop "$NGINX_CONTAINER"
        STOPPED=true
    else
        echo "Aborting certificate generation."
        exit 1
    fi
else
    echo "Nginx container is not running. Proceeding..."
fi

# ここで証明書生成処理を実行
echo "Generating self-signed SSL certificates..."
mkdir -p ./volumes/nginx/certs
cd ./volumes/nginx/certs
# サーバー用秘密鍵(root CA)の作成
openssl genrsa -out localhost_ca.key 2048 
# CA 向けの証明書署名要求の作成
openssl req -new -key localhost_ca.key -out localhost_ca.csr -subj "/C=JP/ST=Tokyo/L=Tokyo/O=Local/CN=$HOST_IP"
# 自己署名サーバー証明書の作成
openssl x509 -days 3650 -in localhost_ca.csr -out nginx.crt -req -signkey localhost_ca.key

# 自己署名サーバー証明書をp12, pemに変換
openssl pkcs12 -export -inkey localhost_ca.key -in nginx.crt -out nginx.p12 -passin "pass:" -passout "pass:" -password "pass:"
openssl pkcs12 -in nginx.p12 -out nginx.pem  -passin "pass:" -passout "pass:" -password "pass:"
# CA証明書の秘密鍵を作成
openssl pkcs12 -in nginx.p12 -nodes -out nginx-ca.key -nocerts  -passin "pass:" -passout "pass:" -password "pass:"

openssl x509 -req -in localhost_ca.csr -CA nginx.pem -CAkey nginx-ca.key -CAcreateserial -out nginx.crt -days 3650 -sha256 -extensions SAN -extfile <(printf "
[SAN]
subjectAltName=@alt_names
basicConstraints=CA:FALSE
[alt_names]
DNS.1=localhost
IP.1=$HOST_IP
IP.2=127.0.0.1")

echo "Certificates generated in ./volumes/nginx/"

# 必要であればコンテナを再起動
if [ "$STOPPED" = true ]; then
    echo "Restarting Nginx container..."
    docker start "$NGINX_CONTAINER"
fi

echo "X509v3 Subject Alternative Name に nginxコンテナを動かすホストOSのローカルIPが記載されていることを確認してください。"
openssl x509 -in nginx.crt -text -noout

echo "Done."

echo "./volumes/nginx/certs/nginx.crt をサーバーを利用するリモート端末が信頼するルートCA証明書ストアへ追加してください"