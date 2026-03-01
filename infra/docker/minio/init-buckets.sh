#!/bin/sh
# ============================================================
# Agente Energia Col — Inicialización de buckets MinIO
# ============================================================
set -e

echo "Configurando MinIO Client..."
mc alias set local http://minio:9000 "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"

echo "Creando buckets..."
mc mb --ignore-existing local/raw-data
mc mb --ignore-existing local/features
mc mb --ignore-existing local/models
mc mb --ignore-existing local/reports

echo "Configurando políticas de retención..."
# raw-data: retener 90 días
mc ilm rule add --expire-days 90 local/raw-data

# reports: retener 365 días
mc ilm rule add --expire-days 365 local/reports

echo "Estructura de buckets:"
mc ls local/

echo "MinIO inicializado correctamente."
