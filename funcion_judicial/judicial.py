#!/usr/bin/env python3
"""Listado y consulta de causas en Función Judicial.

Modo 1: preparar el listado
    ./judicial.sh --solo-listado salidas/2026-10-30_10-45-16

Modo 2: buscar en Función Judicial
    ./judicial.sh salidas/2026-10-30_10-45-16

El listado sale de <carpeta>/contribuyentes/contribuyentes.json (o de ruc/ en
ejecuciones viejas). Solo incluye personas naturales: titulares personas y
representantes legales personas. La búsqueda se hace como Demandado/Procesado.

Salida:
    <carpeta>/funcion_judicial/funcion-judicial.csv
    <carpeta>/funcion_judicial/judicial-<cedula>.pdf

El CSV tiene 8 columnas:
    cedula, nombre, ruc_titular, nombre_titular, relacion,
    judicial, pdf, observaciones
"""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

URL = "https://procesosjudiciales.funcionjudicial.gob.ec/busqueda-filtros"
SESSION = "judicial"
COLUMNAS = [
    "cedula", "nombre", "ruc_titular", "nombre_titular", "relacion",
    "judicial", "pdf", "observaciones",
]
FINALES = ("CON CAUSAS", "SIN CAUSAS")


def ruta_contribuyentes(carpeta):
    for nombre in ("contribuyentes", "ruc"):
        ruta = carpeta / nombre / "contribuyentes.json"
        if ruta.exists():
            return ruta
    return None


def leer_csv(ruta):
    if not ruta.exists():
        return []
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def escribir_csv(ruta, filas):
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)


def unir(*partes):
    return "; ".join(p.strip() for p in partes if p and p.strip())


def claves_del_contribuyente(c):
    """Devuelve las llaves CEDULA/PERSONA NATURAL de un contribuyente."""
    ruc = c["ruc"]
    nombre_titular = (c.get("razonSocial") or "").strip()
    claves = c.get("claves_busqueda") or []

    # Compatibilidad con JSON viejos sin claves_busqueda.
    if not claves:
        if c.get("tipoContribuyente") == "PERSONA NATURAL":
            claves = [{
                "clave": ruc[:10],
                "tipo": "CEDULA",
                "nombre": nombre_titular,
                "tipoContribuyente": "PERSONA NATURAL",
                "relacion": "TITULAR",
            }]
        else:
            claves = [
                {
                    "clave": (r.get("identificacion") or "").strip(),
                    "tipo": "CEDULA",
                    "nombre": (r.get("nombre") or "").strip(),
                    "tipoContribuyente": "PERSONA NATURAL",
                    "relacion": "REPRESENTANTE",
                }
                for r in (c.get("representantesLegales") or [])
                if len((r.get("identificacion") or "").strip()) == 10
            ]

    salida = []
    for k in claves:
        if (k.get("tipo") or "").upper() != "CEDULA":
            continue
        if (k.get("tipoContribuyente") or "").upper() != "PERSONA NATURAL":
            continue
        cedula = str(k.get("clave") or "").strip()
        nombre = (k.get("nombre") or "").strip()
        if not cedula or not nombre:
            continue
        salida.append({
            "cedula": cedula,
            "nombre": nombre,
            "ruc_titular": ruc,
            "nombre_titular": nombre_titular,
            "relacion": k.get("relacion") or "TITULAR",
            "judicial": "NO CONSULTADO",
            "pdf": "",
            "observaciones": "",
        })
    return salida


def construir_listado(doc):
    filas = []
    for c in doc.get("contribuyentes", []):
        if not c.get("existe"):
            continue
        filas.extend(claves_del_contribuyente(c))

    # Una fila por cédula. Si una persona es titular y representante, gana
    # TITULAR y se deja la nota en observaciones.
    elegidas = {}
    for fila in filas:
        ced = fila["cedula"]
        prev = elegidas.get(ced)
        if prev is None:
            elegidas[ced] = fila
            continue

        if fila["relacion"] == "TITULAR" and prev["relacion"] != "TITULAR":
            nota = f"También es representante de {prev['nombre_titular']}"
            fila["observaciones"] = unir(fila["observaciones"], nota)
            elegidas[ced] = fila
        elif fila["relacion"] != "TITULAR" and prev["relacion"] == "TITULAR":
            nota = f"También es representante de {fila['nombre_titular']}"
            prev["observaciones"] = unir(prev["observaciones"], nota)
        else:
            nota = f"También representa a {fila['nombre_titular']}"
            prev["observaciones"] = unir(prev["observaciones"], nota)

    return list(elegidas.values())


def solo_listado(carpeta, reset=False):
    ruta = ruta_contribuyentes(carpeta)
    if ruta is None:
        print("!! no existe contribuyentes/contribuyentes.json (ni ruc/contribuyentes.json)")
        return 1

    doc = json.load(open(ruta, encoding="utf-8"))
    filas = construir_listado(doc)
    destino = carpeta / "funcion_judicial" / "funcion-judicial.csv"

    previas = {}
    if destino.exists() and not reset:
        previas = {f.get("cedula"): f for f in leer_csv(destino) if f.get("cedula")}

    for fila in filas:
        prev = previas.get(fila["cedula"])
        if prev:
            fila["judicial"] = prev.get("judicial") or "NO CONSULTADO"
            fila["pdf"] = prev.get("pdf") or ""
            if prev.get("observaciones"):
                fila["observaciones"] = prev["observaciones"]

    escribir_csv(destino, filas)
    conteo = Counter(f["relacion"] for f in filas)
    print(f"{len(filas)} búsquedas -> {destino}")
    print(f"titulares: {conteo.get('TITULAR', 0)} | "
          f"representantes: {conteo.get('REPRESENTANTE', 0)}")
    print(f"fuente: {ruta}")
    return 0


def parsear_salida(texto):
    """Playwright devuelve un JSON que puede venir envuelto en comillas."""
    for linea in reversed(texto.splitlines()):
        linea = linea.strip()
        if not linea:
            continue

        try:
            data = json.loads(linea)
            if isinstance(data, str):
                data = json.loads(data)
            if isinstance(data, dict):
                return data
        except Exception:
            pass

        m = re.match(r'^"(.*)"$', linea)
        if m:
            try:
                data = json.loads('"' + m.group(1) + '"')
                data = json.loads(data)
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
    return None


def correr(cmd, cwd=None):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def sesion_abierta():
    p = correr(["playwright-cli", "list"])
    if p.returncode != 0:
        return False
    return bool(re.search(rf"(^|\s){re.escape(SESSION)}(\s|$)", p.stdout, re.M))


def abrir_navegador(root, carpeta):
    if sesion_abierta():
        print(f">>> Reutilizando sesión Playwright '{SESSION}'")
        return False

    print(f">>> Abriendo navegador ({SESSION})")
    config = root / "funcion_judicial" / "pw-judicial.json"
    p = correr([
        "playwright-cli", f"-s={SESSION}", "open", "--headed",
        f"--config={config}", URL,
    ], cwd=carpeta)
    if p.returncode != 0:
        print((p.stderr or p.stdout or "no se pudo abrir el navegador")[:500])
        return None
    return True


def buscar(carpeta, root, args):
    destino = carpeta / "funcion_judicial" / "funcion-judicial.csv"
    if not destino.exists():
        rc = solo_listado(carpeta)
        if rc != 0:
            return rc

    todas = leer_csv(destino)
    if not todas:
        print("!! el listado judicial está vacío")
        return 1

    filas = todas[:args.limite] if args.limite else todas

    abrimos = abrir_navegador(root, carpeta)
    if abrimos is None:
        return 1

    print(">>> Si aparece el desafío de imágenes del captcha, resuélvelo en el navegador.")
    print(">>> Búsqueda como Demandado/Procesado.\n")

    plantilla = (root / "funcion_judicial" / "judicial-template.js").read_text(encoding="utf-8")
    tmp = Path(tempfile.mkdtemp(prefix="judicial-", dir=str(carpeta)))

    try:
        for i, fila in enumerate(filas, 1):
            cedula = fila["cedula"]
            nombre = fila["nombre"]
            out = (carpeta / "funcion_judicial" / f"judicial-{cedula}.pdf").resolve()

            if (args.reusar and out.exists()
                    and (fila.get("judicial") or "") in FINALES):
                print(f"[{i}/{len(filas)}] {cedula}  ya existe, se omite")
                continue

            snippet = (plantilla
                       .replace("__CEDULA__", json.dumps(cedula))
                       .replace("__NOMBRE__", json.dumps(nombre))
                       .replace("__OUTFILE__", json.dumps(str(out)))
                       .replace("__URL__", json.dumps(URL))
                       .replace("__ESPERAR_CAPTCHA__", str(args.esperar_captcha)))
            ruta_snippet = tmp / f"q-{cedula}.js"
            ruta_snippet.write_text(snippet, encoding="utf-8")

            print(f"[{i}/{len(filas)}] {cedula}  {nombre[:50]}")

            p = correr([
                "playwright-cli", f"-s={SESSION}", "run-code",
                f"--filename={ruta_snippet}", "--raw",
            ], cwd=carpeta)

            data = parsear_salida(p.stdout)
            if not data:
                fila["judicial"] = "ERROR"
                fila["pdf"] = ""
                detalle = (p.stderr or p.stdout or "sin respuesta de Playwright").strip()
                fila["observaciones"] = unir(fila.get("observaciones"), detalle[:250])
            else:
                estado = (data.get("estado") or "ERROR").strip()
                fila["judicial"] = estado
                fila["pdf"] = (str(out.relative_to(carpeta)) if out.exists() else "")
                error = (data.get("error") or "").strip()
                if error:
                    fila["observaciones"] = unir(fila.get("observaciones"), error)
                elif estado in FINALES:
                    fila["observaciones"] = ""

            escribir_csv(destino, todas)
            print(f"    -> {fila['judicial']}  {fila['pdf'] or '(sin PDF)'}")
            if i < len(filas):
                time.sleep(args.pausa)

    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        if abrimos and not args.mantener_navegador:
            correr(["playwright-cli", f"-s={SESSION}", "close"], cwd=carpeta)
        shutil.rmtree(carpeta / ".playwright-cli", ignore_errors=True)

    conteo = Counter(f.get("judicial") or "NO CONSULTADO" for f in todas)
    print(f"\nCSV: {destino}")
    print(" | ".join(f"{k}: {v}" for k, v in sorted(conteo.items())))
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Prepara el listado y consulta causas en Función Judicial.",
    )
    parser.add_argument("carpeta", help="Carpeta de ejecución (salidas/<fecha>)")
    parser.add_argument("--solo-listado", action="store_true",
                        help="Solo arma el CSV desde contribuyentes.json; no consulta.")
    parser.add_argument("--reset", action="store_true",
                        help="Al rearmar el listado, borra estados y PDFs anteriores.")
    parser.add_argument("--limite", type=int,
                        help="Procesar solo las primeras N cédulas (para probar).")
    parser.add_argument("--reusar", action="store_true",
                        help="Omitir las cédulas que ya tienen PDF y estado final.")
    parser.add_argument("--esperar-captcha", type=int, default=90,
                        help="Segundos de espera si aparece un desafío de captcha (default 90).")
    parser.add_argument("--pausa", type=float, default=2.0,
                        help="Segundos entre búsquedas (default 2).")
    parser.add_argument("--mantener-navegador", action="store_true",
                        help="No cerrar la sesión de Playwright al terminar.")
    args = parser.parse_args()

    carpeta = Path(args.carpeta).resolve()
    if not carpeta.is_dir():
        print(f"!! no existe la carpeta {carpeta}")
        return 1

    root = Path(__file__).resolve().parent.parent

    if args.solo_listado:
        return solo_listado(carpeta, reset=args.reset)
    return buscar(carpeta, root, args)


if __name__ == "__main__":
    sys.exit(main())
