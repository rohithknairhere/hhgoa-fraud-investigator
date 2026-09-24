#!/usr/bin/env bash
# Provision HHGOA_IEEE on a TigerGraph instance (run where the `gsql` client is available).
set -euo pipefail
cd "$(dirname "$0")"
python ../backend/scripts/export_tigergraph_csv.py --out ./data
gsql schema.gsql
gsql load.gsql
gsql install.gsql
echo "HHGOA_IEEE ready. Set TG_HOST / TG_USERNAME / TG_PASSWORD / TG_SECRET in backend/.env"
