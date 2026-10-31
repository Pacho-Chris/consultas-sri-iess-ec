#!/usr/bin/env bash
# Prepara el listado judicial y/o busca en Función Judicial.
#
# Uso:
#   ./judicial.sh --solo-listado salidas/2026-10-30_10-45-16
#   ./judicial.sh salidas/2026-10-30_10-45-16
#   ./judicial.sh salidas/2026-10-30_10-45-16 --limite 1 --reusar
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$ROOT/funcion_judicial/judicial.py" "$@"
