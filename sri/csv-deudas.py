#!/usr/bin/env python3
"""Arma deudas.csv a partir de los PDFs generados por sri.sh.

Formato largo: una fila por cada tipo de deuda con monto > 0.
Los contribuyentes sin deuda quedan en una sola fila con tipo_deuda vacío.
Los que no tienen PDF o tienen un PDF ilegible quedan como ERROR con el motivo
en la misma fila: no se genera un CSV aparte de errores.

Uso: ./csv-deudas.py <carpeta_pdfs> <salida.csv> [lista_de_rucs.txt]
"""
import csv
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

TIPOS = ["Deudas firmes", "Deudas impugnadas", "Facilidades de pago"]

# líneas que marcan el fin del bloque del nombre
STOP = re.compile(
    r"^(Deudas firmes|Impuesto|No registra|El ciudadano|Valor total|Ver detalle|"
    r"Pague|Nota:|Consultar|Nueva consulta)",
    re.IGNORECASE,
)
TOTAL = re.compile(r"Valor total\s*:\s*USD\s*\$([0-9][0-9,\.]*)")


def limpiar(s):
    # quita glifos de icon-font (área de uso privado) y caracteres invisibles
    s = "".join(c for c in s if unicodedata.category(c) not in ("Co", "Cf", "Mn"))
    return s.replace("\xa0", " ").strip()


def texto_pdf(pdf):
    return subprocess.run(
        ["pdftotext", "-layout", str(pdf), "-"],
        capture_output=True, text=True, check=True,
    ).stdout


def extraer(pdf):
    texto = texto_pdf(pdf)
    lineas = [limpiar(l) for l in texto.splitlines()]

    nombre = ""
    for i, l in enumerate(lineas):
        if "Apellidos y nombres" in l:
            partes = []
            for sig in lineas[i + 1:]:
                if not sig:
                    continue
                if STOP.match(sig):
                    break
                partes.append(sig)
                if len(partes) >= 2:      # nombre en 2 líneas como máximo
                    break
            nombre = " ".join(partes).strip()
            break

    montos = [float(m.replace(",", "")) for m in TOTAL.findall(texto)]
    montos = (montos + [0.0, 0.0, 0.0])[:3]
    return nombre, montos


def main():
    if len(sys.argv) < 3:
        print("Uso: csv-deudas.py <carpeta_pdfs> <salida.csv> [lista_de_rucs.txt]")
        sys.exit(1)

    carpeta = Path(sys.argv[1])
    salida = Path(sys.argv[2])
    orden = None
    if len(sys.argv) > 3 and Path(sys.argv[3]).exists():
        orden = [l.strip() for l in open(sys.argv[3], encoding="utf-8") if l.strip()]

    disponibles = {p.stem.replace("cedula-", ""): p for p in carpeta.glob("cedula-*.pdf")}
    codigos = orden or sorted(disponibles)

    filas = []
    for cod in codigos:
        pdf = disponibles.get(cod)
        if not pdf:
            filas.append({
                "codigo_unico": cod, "nombre": "", "estado": "ERROR",
                "tipo_deuda": "", "cantidad": "", "motivo": "No se generó el PDF",
            })
            continue

        try:
            nombre, montos = extraer(pdf)
        except Exception as e:
            filas.append({
                "codigo_unico": cod, "nombre": "", "estado": "ERROR",
                "tipo_deuda": "", "cantidad": "",
                "motivo": f"PDF ilegible ({type(e).__name__})",
            })
            continue

        con_deuda = [(t, m) for t, m in zip(TIPOS, montos) if m > 0]

        if con_deuda:
            for tipo, monto in con_deuda:
                filas.append({
                    "codigo_unico": cod, "nombre": nombre, "estado": "CON DEUDAS",
                    "tipo_deuda": tipo, "cantidad": f"{monto:,.2f}", "motivo": "",
                })
        else:
            filas.append({
                "codigo_unico": cod, "nombre": nombre, "estado": "SIN DEUDAS",
                "tipo_deuda": "", "cantidad": "0.00", "motivo": "",
            })

    with open(salida, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["codigo_unico", "nombre", "estado", "tipo_deuda",
                        "cantidad", "motivo"],
            quoting=csv.QUOTE_MINIMAL,
        )
        w.writeheader()
        w.writerows(filas)

    print(f"{len(filas)} filas -> {salida}")
    from collections import Counter
    print(Counter(f["estado"] for f in filas))
    total = sum(float(f["cantidad"].replace(",", "")) for f in filas if f["cantidad"])
    print(f"monto total: {total:,.2f} USD")


if __name__ == "__main__":
    main()
