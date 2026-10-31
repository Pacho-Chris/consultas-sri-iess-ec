#!/usr/bin/env python3
"""Descarga el Certificado de Cumplimiento de Obligaciones Patronales del IESS.

Uso: ./iess.py [lista_rucs.txt] [carpeta_salida]

Por cada RUC/Cédula:
  - GET del formulario JSF para obtener sesión + javax.faces.ViewState
  - POST con el RUC
  - si la respuesta es un PDF -> certificado-<ruc>.pdf
  - si no -> se anota en resultados.json con el motivo
"""
import http.cookiejar
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

URL = "https://www.iess.gob.ec/empleador-web/pages/morapatronal/certificadoCumplimientoPublico.jsf"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
PAUSA = 0.5


def abrir_sesion():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", UA), ("Accept-Language", "es-EC,es;q=0.9")]
    return op


def consultar(ruc, op):
    """Devuelve (bytes_pdf, None) o (None, motivo)."""
    html = op.open(URL, timeout=60).read().decode("utf-8", "replace")

    m = re.search(r'id="frmCertificadoCumplimiento".*?action="([^"]+)"', html, re.S)
    if not m:
        return None, "no se encontró el formulario"
    action = m.group(1)

    viewstates = re.findall(r'name="javax\.faces\.ViewState"[^>]*value="([^"]+)"', html)
    if not viewstates:
        return None, "no se encontró ViewState"

    data = {
        "frmCertificadoCumplimiento": "frmCertificadoCumplimiento",
        "frmCertificadoCumplimiento:j_id9": ruc,
        "frmCertificadoCumplimiento:j_id11": "CONSULTAR",
        "javax.faces.ViewState": viewstates[-1],
    }
    req = urllib.request.Request(
        "https://www.iess.gob.ec" + action,
        data=urllib.parse.urlencode(data).encode(),
    )
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    req.add_header("Referer", URL)

    resp = op.open(req, timeout=120)
    body = resp.read()

    if body[:4] == b"%PDF":
        return body, None

    texto = body.decode("utf-8", "replace")
    motivos = re.findall(r"El RUC ingresado no es correcto", texto)
    if motivos:
        return None, "sin registro patronal (el RUC no es correcto para IESS)"
    return None, "respuesta sin PDF"


def main():
    base = Path(__file__).resolve().parent
    lista = Path(sys.argv[1]) if len(sys.argv) > 1 else base / "rucs.txt"
    salida = Path(sys.argv[2]) if len(sys.argv) > 2 else base
    salida.mkdir(parents=True, exist_ok=True)

    rucs = [l.strip() for l in open(lista, encoding="utf-8") if l.strip()]
    ok, fallos = [], []
    resultados = {}

    for i, ruc in enumerate(rucs, 1):
        pdf = None
        motivo = None
        for intento in (1, 2):
            try:
                pdf, motivo = consultar(ruc, abrir_sesion())
                break
            except Exception as e:
                motivo = f"error de red: {type(e).__name__}: {e}"
                time.sleep(2)

        if pdf:
            destino = salida / f"certificado-{ruc}.pdf"
            destino.write_bytes(pdf)
            ok.append((ruc, len(pdf)))
            resultados[ruc] = {"ok": True, "archivo": destino.name, "motivo": ""}
            print(f"[{i}/{len(rucs)}] {ruc}  OK  {len(pdf)//1024} KB")
        else:
            fallos.append((ruc, motivo))
            resultados[ruc] = {"ok": False, "archivo": None, "motivo": motivo or ""}
            print(f"[{i}/{len(rucs)}] {ruc}  --  {motivo}")

        time.sleep(PAUSA)

    (salida / "resultados.json").write_text(
        json.dumps(resultados, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\nDescargados: {len(ok)} | Sin certificado: {len(fallos)}")


if __name__ == "__main__":
    main()
