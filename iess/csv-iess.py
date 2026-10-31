#!/usr/bin/env python3
"""Genera certificados.csv a partir de los PDFs del IESS.

Columnas: codigo_unico, registrado, tiene_deuda, monto_deuda, motivo

Los RUC sin certificado quedan en la misma fila con registrado=no y el motivo
que dejó iess.py en resultados.json. No se genera un CSV aparte de errores.

Uso: ./csv-iess.py [carpeta] [salida.csv] [lista_rucs.txt]
"""
import csv
import json
import re
import subprocess
import sys
from pathlib import Path

SIN_DEUDA = re.compile(r"\bNO\s+registra\s+obligaciones\s+patronales\s+en\s+mora", re.I)
CON_DEUDA = re.compile(r"\bregistra\s+obligaciones\s+patronales\s+en\s+mora", re.I)
MONTO = re.compile(r"USD\s*\$?\s*([0-9][0-9,\.]*)")


def texto(pdf):
    return subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True, text=True,
    ).stdout


def main():
    base = Path(__file__).resolve().parent
    carpeta = Path(sys.argv[1]) if len(sys.argv) > 1 else base
    salida = Path(sys.argv[2]) if len(sys.argv) > 2 else carpeta / "certificados.csv"
    lista = Path(sys.argv[3]) if len(sys.argv) > 3 else base / "rucs.txt"

    rucs = [l.strip() for l in open(lista, encoding="utf-8") if l.strip()]

    resultados = {}
    ruta_resultados = carpeta / "resultados.json"
    if ruta_resultados.exists():
        resultados = json.load(open(ruta_resultados, encoding="utf-8"))

    filas = []
    resumen = {"con": 0, "sin": 0, "no_reg": 0, "revisar": 0}

    for ruc in rucs:
        pdf = carpeta / f"certificado-{ruc}.pdf"
        if not pdf.exists():
            motivo = (resultados.get(ruc) or {}).get("motivo") or ""
            filas.append({"codigo_unico": ruc, "registrado": "no",
                          "tiene_deuda": "", "monto_deuda": "", "motivo": motivo})
            resumen["no_reg"] += 1
            continue

        t = texto(pdf)
        if SIN_DEUDA.search(t):
            filas.append({"codigo_unico": ruc, "registrado": "si",
                          "tiene_deuda": "no", "monto_deuda": "0.00", "motivo": ""})
            resumen["sin"] += 1
        elif CON_DEUDA.search(t):
            m = MONTO.search(t)
            monto = f"{float(m.group(1).replace(',', '')):,.2f}" if m else ""
            filas.append({"codigo_unico": ruc, "registrado": "si",
                          "tiene_deuda": "si", "monto_deuda": monto, "motivo": ""})
            resumen["con"] += 1
        else:
            # PDF presente pero sin texto reconocible
            filas.append({"codigo_unico": ruc, "registrado": "si",
                          "tiene_deuda": "REVISAR", "monto_deuda": "",
                          "motivo": "PDF sin texto reconocible"})
            resumen["revisar"] += 1

    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["codigo_unico", "registrado", "tiene_deuda",
                        "monto_deuda", "motivo"],
        )
        w.writeheader()
        w.writerows(filas)

    print(f"{len(filas)} filas -> {salida}")
    print(f"registrados: {resumen['sin'] + resumen['con'] + resumen['revisar']} | "
          f"sin registro: {resumen['no_reg']}")
    print(f"con deuda: {resumen['con']} | sin deuda: {resumen['sin']} | revisar: {resumen['revisar']}")


if __name__ == "__main__":
    main()
