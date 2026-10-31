#!/usr/bin/env bash
# Consulta de deudas firmes/impugnadas en el SRI y guarda un PDF por cédula.
#
# Uso:  ./sri.sh 1712345678 0912345678 [RUC...]
#
# Antes hay que abrir el navegador una vez:
#   playwright-cli -s=sri open --config=./pw-sri.json \
#     "https://srienlinea.sri.gob.ec/sri-en-linea/SriPagosWeb/ConsultaDeudasFirmesImpugnadas/Consultas/consultaDeudasFirmesImpugnadas"
#
# Los PDFs se guardan junto a este script (override con SRI_OUTDIR=/ruta).
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="${SRI_SESSION:-sri}"
OUTDIR="${SRI_OUTDIR:-$SCRIPT_DIR}"
TEMPLATE="$SCRIPT_DIR/sri-template.js"
WORK="${TMPDIR:-/tmp}/sri-consulta"

mkdir -p "$OUTDIR" "$WORK"

if [[ $# -eq 0 ]]; then
  echo "Uso: $0 <cedula> [cedula ...]"
  exit 1
fi

fallos_seguidos=0

for ced in "$@"; do
  if ! [[ "$ced" =~ ^[0-9]{10,13}$ ]]; then
    echo "!! '$ced' no parece cédula/RUC válido, se omite"
    continue
  fi

  outfile="$OUTDIR/cedula-$ced.pdf"
  snippet="$WORK/q-$ced.js"
  sed -e "s/__CEDULA__/$ced/" -e "s|__OUTFILE__|$outfile|" "$TEMPLATE" > "$snippet"

  echo ">>> Consultando $ced"
  salida=$(playwright-cli -s="$SESSION" run-code --filename="$snippet" --raw 2>&1 | tail -5)
  echo "$salida"
  echo ""

  # Si el navegador se cayó o el SRI dejó de responder, no seguir perdiendo
  # ~2 minutos por RUC: a los 3 fallos seguidos se corta la consulta.
  # Un resultado bueno siempre trae "archivo"; los errores no.
  if [[ -z "$salida" || "$salida" != *archivo* ]]; then
    fallos_seguidos=$((fallos_seguidos + 1))
    if (( fallos_seguidos >= 3 )); then
      echo "!! 3 fallos seguidos; se detiene la consulta SRI"
      break
    fi
  else
    fallos_seguidos=0
  fi
done
