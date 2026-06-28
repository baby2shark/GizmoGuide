#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup-minio-bucket.sh
# 在 MinIO 中创建 Langfuse 所需的 S3 bucket。
#
# 用法：首次 docker compose up 后执行一次即可。
#   bash setup/setup-minio-bucket.sh
#
# 如果 volume 被清除（docker compose down -v），需要重新执行。
# ---------------------------------------------------------------------------
set -euo pipefail

COMPOSE_PROJECT="${COMPOSE_PROJECT_NAME:-gizmoguide}"
MINIO_CONTAINER="${COMPOSE_PROJECT}-minio-1"
BUCKET_NAME="langfuse"
MINIO_ENDPOINT="http://127.0.0.1:9000"
MINIO_USER="minio"
MINIO_PASS="miniosecret"

echo "==> Waiting for MinIO to be ready..."
for i in $(seq 1 30); do
    if docker exec "$MINIO_CONTAINER" sh -c "cat < /dev/null > /dev/tcp/127.0.0.1/9000" 2>/dev/null; then
        echo "    MinIO is up."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: MinIO did not become ready in 30s. Is docker compose running?"
        exit 1
    fi
    sleep 1
done

echo "==> Creating bucket '${BUCKET_NAME}' (if not exists)..."
docker exec "$MINIO_CONTAINER" sh -c "
    mc alias set local ${MINIO_ENDPOINT} ${MINIO_USER} ${MINIO_PASS} --api S3v4 2>/dev/null
    mc mb --ignore-existing local/${BUCKET_NAME}
"

echo "==> Done. Bucket '${BUCKET_NAME}' is ready."
