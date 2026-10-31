#!/usr/bin/env bash
# Ejecuta SRI + IESS + SRI-RUC para los RUC que se pasen y prepara el listado
# de personas naturales para Función Judicial. Todo queda en una carpeta nueva
# dentro de salidas/ con la fecha y hora de la ejecución.
#
# Uso:
#   ./capturas.sh 1790012345001 0912345678001 ...
#   ./capturas.sh @lista.txt
#   ./capturas.sh --solo-csv salidas/2026-10-30_10-45-02
#
# Después del listado:
#   ./judicial.sh salidas/2026-10-30_10-45-02
#
# Opciones:
#   --solo-csv <carpeta>       No consulta portales; solo rearma el CSV judicial.
#   --mantener-navegador       No cierra la sesión de Playwright al terminar.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SESSION="${SRI_SESSION:-sri}"
SRI_URL="https://srienlinea.sri.gob.ec/sri-en-linea/SriPagosWeb/ConsultaDeudasFirmesImpugnadas/Consultas/consultaDeudasFirmesImpugnadas"

MANTENER_NAVEGADOR=0
SOLO_CSV=""
RUC_ENTRADA=()

uso() {
  cat <<EOF
Uso:
  $0 RUC [RUC...]
  $0 @lista.txt
  $0 --solo-csv <carpeta_de_ejecucion>

Opciones:
  --solo-csv <carpeta>   No consulta portales; solo rearma el CSV judicial.
  --mantener-navegador   No cierra la sesión de Playwright al terminar.

Después:
  ./judicial.sh <carpeta_de_ejecucion>
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --solo-csv)
      if [[ $# -lt 2 ]]; then
        echo "!! --solo-csv necesita una carpeta"
        uso
        exit 1
      fi
      SOLO_CSV="$2"
      shift 2
      ;;
    --mantener-navegador)
      MANTENER_NAVEGADOR=1
      shift
      ;;
    -h|--help)
      uso
      exit 0
      ;;
    @*)
      archivo="${1#@}"
      if [[ ! -f "$archivo" ]]; then
        echo "!! no existe la lista $archivo"
        exit 1
      fi
      while IFS= read -r linea || [[ -n "$linea" ]]; do
        linea="${linea%%#*}"
        linea="${linea//[[:space:]]/}"
        [[ -n "$linea" ]] && RUC_ENTRADA+=("$linea")
      done < "$archivo"
      shift
      ;;
    -*)
      echo "!! opción desconocida: $1"
      uso
      exit 1
      ;;
    *)
      RUC_ENTRADA+=("$1")
      shift
      ;;
  esac
done

if [[ -n "$SOLO_CSV" ]]; then
  if [[ ! -d "$SOLO_CSV" ]]; then
    echo "!! no existe la carpeta $SOLO_CSV"
    exit 1
  fi
  python3 "$ROOT/funcion_judicial/judicial.py" --solo-listado "$SOLO_CSV"
  exit $?
fi

if [[ ${#RUC_ENTRADA[@]} -eq 0 ]]; then
  uso
  exit 1
fi

# ---- validar y deduplicar ----
RUCs=()
declare -A vistos=()
invalidos=()
for r in "${RUC_ENTRADA[@]}"; do
  r="${r//[[:space:]]/}"
  [[ -z "$r" ]] && continue
  if ! [[ "$r" =~ ^[0-9]{10,13}$ ]]; then
    invalidos+=("$r")
    continue
  fi
  if [[ -n "${vistos[$r]:-}" ]]; then
    continue
  fi
  vistos[$r]=1
  RUCs+=("$r")
done

if [[ ${#invalidos[@]} -gt 0 ]]; then
  echo "!! se omiten códigos inválidos: ${invalidos[*]}"
fi
if [[ ${#RUCs[@]} -eq 0 ]]; then
  echo "!! no hay RUC válidos para consultar"
  exit 1
fi

for cmd in python3 pdftotext curl playwright-cli; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "!! falta el comando '$cmd'"
    exit 1
  fi
done

# ---- carpeta de la ejecución ----
FECHA="$(date +%Y-%m-%d_%H-%M-%S)"
RUN="$ROOT/salidas/$FECHA"
n=2
while [[ -e "$RUN" ]]; do
  RUN="$ROOT/salidas/${FECHA}-$n"
  n=$((n + 1))
done
mkdir -p "$RUN/sri" "$RUN/iess" "$RUN/contribuyentes"

LISTA="$(mktemp "${TMPDIR:-/tmp}/opencode-capturas-rucs-XXXXXX.txt")"
printf '%s\n' "${RUCs[@]}" > "$LISTA"

ABRIMOS_NAVEGADOR=0
cleanup() {
  rm -f "$LISTA"
  if [[ "$ABRIMOS_NAVEGADOR" -eq 1 && "$MANTENER_NAVEGADOR" -eq 0 ]]; then
    playwright-cli -s="$SESSION" close >/dev/null 2>&1 || true
  fi
  rm -rf "$RUN/.playwright-cli"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# Playwright deja su workspace (.playwright-cli) en el directorio actual.
# Trabajamos desde la carpeta de la ejecución para no ensuciar la raíz.
cd "$RUN" || exit 1

echo "============================================================"
echo " RUC a consultar: ${#RUCs[@]}"
echo " Carpeta:         $RUN"
echo "============================================================"

# ---- sesión de Playwright para el SRI ----
if playwright-cli list 2>/dev/null | grep -qE "(^|[[:space:]])${SESSION}([[:space:]]|$)"; then
  echo ">>> Reutilizando sesión Playwright '$SESSION'"
else
  echo ">>> Abriendo navegador ($SESSION)"
  if playwright-cli -s="$SESSION" open --config="$ROOT/sri/pw-sri.json" "$SRI_URL" >/dev/null 2>&1; then
    ABRIMOS_NAVEGADOR=1
  else
    echo "!! no se pudo abrir el navegador; el SRI quedará sin consultar"
  fi
fi

# ---- 1) SRI deudas ----
echo ""
echo ">>> SRI: deudas firmes / impugnadas / facilidades"
SRI_OUTDIR="$RUN/sri" "$ROOT/sri/sri.sh" "${RUCs[@]}" 2>&1 | tee "$RUN/sri/resultados.log"

echo ""
echo ">>> SRI: armando deudas.csv"
if ! python3 "$ROOT/sri/csv-deudas.py" "$RUN/sri" "$RUN/sri/deudas.csv" "$LISTA"; then
  echo "!! falló csv-deudas.py"
fi

# ---- 2) IESS ----
echo ""
echo ">>> IESS: certificados de cumplimiento"
if ! python3 "$ROOT/iess/iess.py" "$LISTA" "$RUN/iess"; then
  echo "!! falló iess.py"
fi

echo ""
echo ">>> IESS: armando certificados.csv"
if ! python3 "$ROOT/iess/csv-iess.py" "$RUN/iess" "$RUN/iess/certificados.csv" "$LISTA"; then
  echo "!! falló csv-iess.py"
fi

# ---- 3) SRI-RUC ----
echo ""
echo ">>> SRI-RUC: contribuyentes y llaves de búsqueda"
if ! python3 "$ROOT/sri-ruc/sri-ruc.py" "$LISTA" "$RUN/contribuyentes/contribuyentes.json"; then
  echo "!! falló sri-ruc.py"
fi

if [[ -f "$RUN/contribuyentes/contribuyentes.json" ]]; then
  echo ""
  echo ">>> SRI-RUC: armando contribuyentes.csv / establecimientos.csv"
  if ! python3 "$ROOT/sri-ruc/csv-ruc.py" "$RUN/contribuyentes/contribuyentes.json" "$RUN/contribuyentes"; then
    echo "!! falló csv-ruc.py"
  fi
fi

# ---- 4) Listado judicial ----
echo ""
echo ">>> Preparando listado judicial (personas naturales)"
if ! python3 "$ROOT/funcion_judicial/judicial.py" --solo-listado "$RUN"; then
  echo "!! falló el listado judicial"
fi

echo ""
echo "============================================================"
echo " Ejecución terminada: $RUN"
echo " Listado judicial:    $RUN/funcion_judicial/funcion-judicial.csv"
echo " Para buscar:         ./judicial.sh $RUN"
echo " PDFs SRI:            $(find "$RUN/sri" -maxdepth 1 -name 'cedula-*.pdf' | wc -l)"
echo " PDFs IESS:           $(find "$RUN/iess" -maxdepth 1 -name 'certificado-*.pdf' | wc -l)"
echo "============================================================"

if [[ -f "$RUN/funcion_judicial/funcion-judicial.csv" ]]; then
  exit 0
else
  exit 1
fi
