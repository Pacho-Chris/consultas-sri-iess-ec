#!/usr/bin/env python3
"""Consulta de RUC del SRI -> contribuyentes.json

Usa los endpoints públicos de sri-catastro-sujeto-servicio-internet:
  ConsultaRuc/obtenerPorNumerosRuc?&ruc=X&ruc=Y   (acepta varios RUC)
  Establecimiento/consultarPorNumeroRuc?numeroRuc=X

Además de los RUC de la lista, consulta en cadena los RUC de los
representantes legales que sean sociedades, para dejar en el JSON todas las
llaves de búsqueda que se usarán en Función Judicial.

Uso: ./sri-ruc.py [lista_rucs.txt] [salida.json]
"""
import json
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE = "https://srienlinea.sri.gob.ec/sri-catastro-sujeto-servicio-internet/rest"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36")
LOTE = 40          # RUC por petición
PAUSA = 0.3        # segundos entre consultas de establecimientos


def get_json(url):
    """Usa curl: el servidor resetea conexiones de urllib tras varias peticiones."""
    ultimo = None
    for intento in range(4):
        p = subprocess.run(
            ["curl", "-sS", "--max-time", "90",
             "-H", f"User-Agent: {UA}",
             "-H", "Accept: application/json",
             "-w", "\n%{http_code}", url],
            capture_output=True, text=True,
        )
        if p.returncode == 0:
            cuerpo, _, codigo = p.stdout.rpartition("\n")
            if codigo in ("204", "404", "400"):
                return None
            if codigo == "200":
                if not cuerpo.strip():
                    return None
                return json.loads(cuerpo)
            ultimo = f"HTTP {codigo}"
        else:
            ultimo = (p.stderr or "").strip()[:120]
        time.sleep(1.5 * (intento + 1))
    print(f"      !! sin respuesta ({ultimo})")
    return None


def si_no(v):
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        if v.strip().upper() == "SI":
            return True
        if v.strip().upper() == "NO":
            return False
    return None


def fecha(v):
    if not v:
        return ""
    return str(v)[:10]


def consultar_contribuyentes(rucs):
    """{ruc: objeto} usando el endpoint que acepta varios RUC."""
    encontrados = {}
    for i in range(0, len(rucs), LOTE):
        trozo = rucs[i:i + LOTE]
        query = "".join(f"&ruc={r}" for r in trozo)
        data = get_json(f"{BASE}/ConsultaRuc/obtenerPorNumerosRuc?{query}")
        if data:
            for c in data.get("contribuyentes", []):
                encontrados[c["numeroRuc"]] = c
        print(f"  lote {i//LOTE + 1}: {len(trozo)} pedidos, "
              f"{len(data.get('contribuyentes', [])) if data else 0} devueltos")
        time.sleep(PAUSA)
    return encontrados


def consultar_representantes(crudos):
    """Consulta los RUC de representantes que sean sociedades, en cadena.

    Devuelve {ruc: objeto_o_existe_false} con las entidades nuevas.  No hay
    tope de profundidad: se detiene cuando ya no aparecen RUC nuevos.  El set
    ``procesados`` evita ciclos (A representa a B y B a A).
    """
    extra = {}
    procesados = set()
    cola = []

    for c in list(crudos.values()):
        for r in c.get("representantesLegales") or []:
            ident = (r.get("identificacion") or "").strip()
            if len(ident) == 13 and ident not in procesados:
                cola.append(ident)

    while cola:
        pendientes = []
        for ruc in cola:
            if ruc in procesados:
                continue
            procesados.add(ruc)
            pendientes.append(ruc)

        faltantes = [r for r in pendientes if r not in crudos]
        if faltantes:
            print(f"  representantes: {len(faltantes)} RUC por consultar")
            encontrados = consultar_contribuyentes(faltantes)
            for ruc in faltantes:
                c = encontrados.get(ruc)
                if c:
                    extra[ruc] = c
                    crudos[ruc] = c
                else:
                    extra[ruc] = {"existe": False}

        cola = []
        for ruc in pendientes:
            c = crudos.get(ruc)
            if not c:
                continue
            if c.get("tipoContribuyente") == "PERSONA NATURAL":
                continue
            for r in c.get("representantesLegales") or []:
                ident = (r.get("identificacion") or "").strip()
                if len(ident) == 13 and ident not in procesados:
                    cola.append(ident)

    return extra


def clave_de(ruc, tipo=None):
    """Devuelve (clave, tipo_clave) para consultar en Función Judicial."""
    if tipo == "PERSONA NATURAL":
        return ruc[:10], "CEDULA"
    if tipo:
        return ruc, "RUC"
    # Sin datos del SRI: heurística por la estructura del RUC.
    if len(ruc) == 10:
        return ruc, "CEDULA"
    if len(ruc) == 13:
        # 9 = sociedad, 6 = entidad pública; el resto se asume persona natural.
        if ruc[2] in "69":
            return ruc, "RUC"
        return ruc[:10], "CEDULA"
    return ruc, "RUC"


def claves_de(c, crudos):
    """Llaves del titular y de sus representantes, en cadena."""
    ruc = c["numeroRuc"]
    tipo = c.get("tipoContribuyente")
    clave, tipo_clave = clave_de(ruc, tipo)

    claves = [{
        "clave": clave,
        "tipo": tipo_clave,
        "nombre": c.get("razonSocial") or "",
        "tipoContribuyente": tipo or "",
        "estado": c.get("estadoContribuyenteRuc") or "",
        "relacion": "TITULAR",
        "nivel": 0,
        "representaA": None,
    }]

    visitados = {ruc}
    cola = [(r, 1, ruc) for r in (c.get("representantesLegales") or [])]

    while cola:
        rep, nivel, padre = cola.pop(0)
        ident = (rep.get("identificacion") or "").strip()
        if not ident or ident in visitados:
            continue
        visitados.add(ident)

        nombre_rep = (rep.get("nombre") or "").strip()
        ent = crudos.get(ident) if len(ident) == 13 else None

        if len(ident) == 10:
            clave_rep, tipo_rep = ident, "CEDULA"
            tipo_rep_contrib = "PERSONA NATURAL"
            estado_rep = "NO CONSULTADO"
        elif len(ident) == 13:
            if ent and ent.get("tipoContribuyente") == "PERSONA NATURAL":
                clave_rep, tipo_rep = ident[:10], "CEDULA"
                tipo_rep_contrib = "PERSONA NATURAL"
                estado_rep = ent.get("estadoContribuyenteRuc") or ""
                nombre_rep = ent.get("razonSocial") or nombre_rep
            elif ent:
                clave_rep, tipo_rep = ident, "RUC"
                tipo_rep_contrib = ent.get("tipoContribuyente") or "SOCIEDAD"
                estado_rep = ent.get("estadoContribuyenteRuc") or ""
                nombre_rep = ent.get("razonSocial") or nombre_rep
                for r2 in ent.get("representantesLegales") or []:
                    id2 = (r2.get("identificacion") or "").strip()
                    if id2 and id2 not in visitados:
                        cola.append((r2, nivel + 1, ident))
            else:
                if ident[2] in "69":
                    clave_rep, tipo_rep = ident, "RUC"
                else:
                    clave_rep, tipo_rep = ident[:10], "CEDULA"
                tipo_rep_contrib = "NO ENCONTRADO"
                estado_rep = "NO CONSULTADO"
        else:
            continue

        claves.append({
            "clave": clave_rep,
            "tipo": tipo_rep,
            "nombre": nombre_rep,
            "tipoContribuyente": tipo_rep_contrib,
            "estado": estado_rep,
            "relacion": "REPRESENTANTE",
            "nivel": nivel,
            "representaA": padre,
        })

    return claves


def consultar_establecimientos(ruc):
    data = get_json(f"{BASE}/Establecimiento/consultarPorNumeroRuc?numeroRuc={ruc}")
    if not data:
        return []
    salida = []
    for e in data:
        salida.append({
            "numero": e.get("numeroEstablecimiento"),
            "nombreComercial": e.get("nombreFantasiaComercial"),
            "tipo": e.get("tipoEstablecimiento"),
            "estado": e.get("estado"),
            "esMatriz": e.get("matriz") == "SI",
            "direccion": e.get("direccionCompleta"),
        })
    return salida


def main():
    base = Path(__file__).resolve().parent
    lista = Path(sys.argv[1]) if len(sys.argv) > 1 else base / "rucs.txt"
    salida = Path(sys.argv[2]) if len(sys.argv) > 2 else base / "contribuyentes.json"

    rucs = [l.strip() for l in open(lista, encoding="utf-8") if l.strip()]
    print(f"Consultando {len(rucs)} RUC en SRI...")

    crudos = consultar_contribuyentes(rucs)
    extra = consultar_representantes(crudos)

    out = []
    for i, ruc in enumerate(rucs, 1):
        c = crudos.get(ruc)
        if not c:
            clave, tipo_clave = clave_de(ruc, None)
            out.append({
                "ruc": ruc,
                "existe": False,
                "claves_busqueda": [{
                    "clave": clave,
                    "tipo": tipo_clave,
                    "nombre": "",
                    "tipoContribuyente": "NO ENCONTRADO",
                    "estado": "NO ENCONTRADO",
                    "relacion": "TITULAR",
                    "nivel": 0,
                    "representaA": None,
                }],
            })
            print(f"[{i}/{len(rucs)}] {ruc}  NO EXISTE")
            continue

        est = consultar_establecimientos(ruc)
        f = c.get("informacionFechasContribuyente") or {}
        item = {
            "ruc": ruc,
            "existe": True,
            "razonSocial": c.get("razonSocial"),
            "estado": c.get("estadoContribuyenteRuc"),
            "tipoContribuyente": c.get("tipoContribuyente"),
            "regimen": c.get("regimen"),
            "categoria": c.get("categoria"),
            "actividadEconomicaPrincipal": (c.get("actividadEconomicaPrincipal") or "").strip(),
            "obligadoLlevarContabilidad": si_no(c.get("obligadoLlevarContabilidad")),
            "agenteRetencion": si_no(c.get("agenteRetencion")),
            "contribuyenteEspecial": si_no(c.get("contribuyenteEspecial")),
            "contribuyenteFantasma": si_no(c.get("contribuyenteFantasma")),
            "transaccionesInexistente": si_no(c.get("transaccionesInexistente")),
            "fechaInicioActividades": fecha(f.get("fechaInicioActividades")),
            "fechaCese": fecha(f.get("fechaCese")),
            "fechaReinicioActividades": fecha(f.get("fechaReinicioActividades")),
            "fechaActualizacion": fecha(f.get("fechaActualizacion")),
            "motivoCancelacionSuspension": c.get("motivoCancelacionSuspension"),
            "representantesLegales": [
                {"identificacion": r.get("identificacion"), "nombre": r.get("nombre")}
                for r in (c.get("representantesLegales") or [])
            ],
            "establecimientos": est,
            "claves_busqueda": claves_de(c, crudos),
        }
        out.append(item)
        print(f"[{i}/{len(rucs)}] {ruc}  {item['estado']:<10} "
              f"{(item['razonSocial'] or '')[:38]:<38} est:{len(est)} "
              f"llaves:{len(item['claves_busqueda'])}")
        time.sleep(PAUSA)

    entes_extra = []
    for ruc in sorted(extra):
        c = extra[ruc]
        entes_extra.append({
            "ruc": ruc,
            "existe": bool(c.get("numeroRuc")),
            "razonSocial": c.get("razonSocial"),
            "estado": c.get("estadoContribuyenteRuc"),
            "tipoContribuyente": c.get("tipoContribuyente"),
            "representantesLegales": [
                {"identificacion": r.get("identificacion"), "nombre": r.get("nombre")}
                for r in (c.get("representantesLegales") or [])
            ],
        })

    con_datos = [c for c in out if c["existe"]]
    resumen = {
        "por_estado": dict(Counter(c["estado"] for c in con_datos)),
        "por_tipo": dict(Counter(c["tipoContribuyente"] for c in con_datos)),
        "por_regimen": dict(Counter(c["regimen"] for c in con_datos)),
        "con_representante_legal": sum(1 for c in con_datos if c["representantesLegales"]),
        "obligados_contabilidad": sum(1 for c in con_datos if c["obligadoLlevarContabilidad"]),
        "agentes_retencion": sum(1 for c in con_datos if c["agenteRetencion"]),
        "representantes_consultados": len(entes_extra),
        "con_sociedad_representante": sum(
            1 for c in con_datos
            if any(len((r.get("identificacion") or "")) == 13
                   for r in c["representantesLegales"])
        ),
        "llaves_busqueda": sum(len(c.get("claves_busqueda") or []) for c in out),
    }

    doc = {
        "generado": datetime.now().astimezone().isoformat(timespec="seconds"),
        "fuente": "SRI - ConsultaRuc (sri-catastro-sujeto-servicio-internet)",
        "total_consultados": len(rucs),
        "encontrados": len(con_datos),
        "no_encontrados": len(rucs) - len(con_datos),
        "resumen": resumen,
        "entes_extra": entes_extra,
        "contribuyentes": out,
    }

    salida.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n{len(out)} registros -> {salida}")
    print(f"encontrados: {doc['encontrados']} | no encontrados: {doc['no_encontrados']}")
    print(f"representantes extra: {len(entes_extra)} | "
          f"llaves de búsqueda: {resumen['llaves_busqueda']}")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
