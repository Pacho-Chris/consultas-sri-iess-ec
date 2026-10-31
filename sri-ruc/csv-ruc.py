#!/usr/bin/env python3
"""Convierte contribuyentes.json a CSV.

Genera:
  contribuyentes.csv    - una fila por RUC
  establecimientos.csv  - una fila por establecimiento (597)

Fechas en formato dd/mm/aaaa. Booleanos como SI/NO.

Uso: ./csv-ruc.py [contribuyentes.json] [carpeta_salida]
"""
import csv
import json
import sys
from pathlib import Path


def fecha(v):
    """'2023-03-08' -> '08/03/2023'"""
    if not v:
        return ""
    partes = str(v)[:10].split("-")
    if len(partes) != 3:
        return str(v)
    return f"{partes[2]}/{partes[1]}/{partes[0]}"


def sn(v):
    if v is None:
        return ""
    return "SI" if v else "NO"


def main():
    base = Path(__file__).resolve().parent
    origen = Path(sys.argv[1]) if len(sys.argv) > 1 else base / "contribuyentes.json"
    destino = Path(sys.argv[2]) if len(sys.argv) > 2 else origen.parent

    doc = json.load(open(origen, encoding="utf-8"))
    contribuyentes = doc["contribuyentes"]

    cols = [
        "ruc", "razonSocial", "estado", "tipoContribuyente", "regimen", "categoria",
        "actividadEconomicaPrincipal", "obligadoLlevarContabilidad", "agenteRetencion",
        "contribuyenteEspecial", "contribuyenteFantasma", "transaccionesInexistente",
        "fechaInicioActividades", "fechaCese", "fechaReinicioActividades",
        "fechaActualizacion", "representantesLegales", "establecimientos_total",
        "establecimientos_abiertos",
    ]

    filas, est_filas = [], []
    for c in contribuyentes:
        est = c.get("establecimientos") or []
        reps = c.get("representantesLegales") or []
        filas.append({
            "ruc": c["ruc"],
            "razonSocial": c.get("razonSocial") or "",
            "estado": c.get("estado") or "",
            "tipoContribuyente": c.get("tipoContribuyente") or "",
            "regimen": c.get("regimen") or "",
            "categoria": c.get("categoria") or "",
            "actividadEconomicaPrincipal": c.get("actividadEconomicaPrincipal") or "",
            "obligadoLlevarContabilidad": sn(c.get("obligadoLlevarContabilidad")),
            "agenteRetencion": sn(c.get("agenteRetencion")),
            "contribuyenteEspecial": sn(c.get("contribuyenteEspecial")),
            "contribuyenteFantasma": sn(c.get("contribuyenteFantasma")),
            "transaccionesInexistente": sn(c.get("transaccionesInexistente")),
            "fechaInicioActividades": fecha(c.get("fechaInicioActividades")),
            "fechaCese": fecha(c.get("fechaCese")),
            "fechaReinicioActividades": fecha(c.get("fechaReinicioActividades")),
            "fechaActualizacion": fecha(c.get("fechaActualizacion")),
            "representantesLegales": "; ".join(
                f'{r["nombre"]} ({r["identificacion"]})' for r in reps
            ),
            "establecimientos_total": len(est),
            "establecimientos_abiertos": sum(1 for e in est if e.get("estado") == "ABIERTO"),
        })

        for e in est:
            est_filas.append({
                "ruc": c["ruc"],
                "razonSocial": c.get("razonSocial") or "",
                "numero": e.get("numero") or "",
                "nombreComercial": e.get("nombreComercial") or "",
                "tipo": e.get("tipo") or "",
                "estado": e.get("estado") or "",
                "esMatriz": sn(e.get("esMatriz")),
                "direccion": e.get("direccion") or "",
            })

    f1 = destino / "contribuyentes.csv"
    with open(f1, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(filas)

    f2 = destino / "establecimientos.csv"
    with open(f2, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f, fieldnames=["ruc", "razonSocial", "numero", "nombreComercial",
                           "tipo", "estado", "esMatriz", "direccion"]
        )
        w.writeheader()
        w.writerows(est_filas)

    print(f"{len(filas)} filas -> {f1}")
    print(f"{len(est_filas)} filas -> {f2}")


if __name__ == "__main__":
    main()
