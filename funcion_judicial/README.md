# Función Judicial

Lee las personas naturales de una ejecución de `capturas.sh`, busca cada una
como **Demandado / Procesado** en:

<https://procesosjudiciales.funcionjudicial.gob.ec/busqueda-filtros>

y guarda un PDF por cédula.

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `judicial.py` | Prepara el listado y orquesta las búsquedas. |
| `judicial-template.js` | Llena el formulario, marca el checkbox del captcha y guarda el PDF. |
| `pw-judicial.json` | Config del navegador (User-Agent real, locale, timezone). |

## Uso

```bash
# Solo armar el CSV (no consulta la página)
./judicial.sh --solo-listado salidas/2026-01-01_10-00-00

# Buscar todas las cédulas
./judicial.sh salidas/2026-01-01_10-00-00

# Probar con una sola
./judicial.sh salidas/2026-01-01_10-00-00 --limite 1
```

Salida:

```
<ejecucion>/funcion_judicial/
├── funcion-judicial.csv
└── judicial-<cedula>.pdf
```

El CSV tiene: `cedula`, `nombre`, `ruc_titular`, `nombre_titular`, `relacion`,
`judicial`, `pdf`, `observaciones`.

## Captcha

El navegador se abre visible (no headless). El primer **BUSCAR** muestra un
reCAPTCHA v2. El script marca el checkbox y espera ~4 segundos antes del
segundo **BUSCAR**. Si Google muestra el desafío de imágenes, hay que
resolverlo en esa ventana; si no se resuelve en `--esperar-captcha` segundos,
la cédula queda como `ERROR`.
