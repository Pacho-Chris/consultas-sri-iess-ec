# Consultas SRI / IESS / RUC + Función Judicial (Ecuador)

Herramientas de línea de comandos para consultar los portales **públicos** del
SRI, IESS y Función Judicial de Ecuador, guardar los PDFs de cada consulta y
armar CSVs con el resumen.

- **SRI** — deudas firmes, impugnadas y en facilidades de pago.
- **IESS** — certificado de cumplimiento de obligaciones patronales.
- **SRI-RUC** — contribuyentes, establecimientos y representantes legales.
- **Función Judicial** — búsqueda de personas naturales como *Demandado / Procesado*.

> ⚠️ Este repositorio **solo contiene código**. No incluye datos de personas ni
> resultados de consultas. Tú eres responsable de los datos que generes con él.

## Requisitos

- Linux o macOS (los scripts son Bash + Python 3).
- `python3` (3.8+)
- `pdftotext` (paquete `poppler-utils`)
- `curl`
- [`playwright-cli`](https://www.npmjs.com/package/@playwright/cli) con Chromium

```bash
# Debian / Ubuntu
sudo apt install python3 poppler-utils curl
npm install -g @playwright/cli
playwright-cli install-browser chromium
```

## Instalación

```bash
git clone https://github.com/Pacho-Chris/consultas-sri-iess-ec.git
cd consultas-sri-iess-ec
chmod +x capturas.sh judicial.sh sri/sri.sh
```

No hay dependencias de Python que instalar: todo usa la biblioteca estándar.

## Uso rápido

```bash
# 1) Consulta SRI + IESS + SRI-RUC y prepara el listado judicial
./capturas.sh 1790012345001 0912345678001

# 2) Busca el listado en Función Judicial (paso aparte, por el captcha)
./judicial.sh salidas/2026-10-30_10-45-16
```

También puedes pasar una lista desde archivo:

```bash
./capturas.sh @ejemplos/rucs-ejemplo.txt
```

Los RUC se pasan **siempre** como argumentos: no hay ninguna lista fija en el
repositorio. Se aceptan cédulas de 10 dígitos y RUC de 13.

## Salida

Cada ejecución crea una carpeta con fecha y hora dentro de `salidas/`
(ignorada por Git). Nada se escribe en la raíz del proyecto.

```
salidas/2026-10-30_10-45-16/
├── sri/
│   ├── cedula-<ruc>.pdf
│   ├── deudas.csv
│   └── resultados.log
├── iess/
│   ├── certificado-<ruc>.pdf
│   ├── certificados.csv
│   └── resultados.json
├── contribuyentes/
│   ├── contribuyentes.csv
│   ├── establecimientos.csv
│   └── contribuyentes.json
└── funcion_judicial/
    ├── funcion-judicial.csv
    └── judicial-<cedula>.pdf
```

`contribuyentes/contribuyentes.json` es la fuente de los nombres, tipos y
representantes legales. Los otros dos CSV son detalle/consulta manual.

Formatos de ejemplo: [`ejemplos/deudas-ejemplo.csv`](ejemplos/deudas-ejemplo.csv)
y [`ejemplos/funcion-judicial-ejemplo.csv`](ejemplos/funcion-judicial-ejemplo.csv).

## Listado judicial

Dentro de `funcion_judicial/` se genera **un solo CSV** con las personas
naturales que se buscan como **Demandado / Procesado**:

```csv
cedula,nombre,ruc_titular,nombre_titular,relacion,judicial,pdf,observaciones
1712345678,PEREZ PEREZ JUAN,1712345678001,PEREZ PEREZ JUAN,TITULAR,NO CONSULTADO,,
0912345678,GOMEZ RUIZ ANA MARIA,0990012345001,EMPRESA EJEMPLO S.A.S.,REPRESENTANTE,SIN CAUSAS,funcion_judicial/judicial-0912345678.pdf,
```

- Personas naturales titulares y representantes personas.
- No se busca por RUC de empresas.
- `judicial`: `NO CONSULTADO`, `CON CAUSAS`, `SIN CAUSAS`, `ERROR`.
- `pdf`: ruta relativa al PDF generado.
- `observaciones`: errores de captcha u otras notas.

El PDF se guarda también cuando no hay resultados; en ese caso el CSV queda
como `SIN CAUSAS`.

## Opciones

### `capturas.sh`

| Opción | Qué hace |
|---|---|
| `--solo-csv <carpeta>` | No consulta portales; solo rearma el CSV judicial. |
| `--mantener-navegador` | No cierra la sesión de Playwright al terminar. |

### `judicial.sh`

| Opción | Qué hace |
|---|---|
| `--solo-listado` | Solo arma el CSV desde `contribuyentes.json`; no consulta. |
| `--limite N` | Procesa solo las primeras N cédulas (para probar). |
| `--reusar` | Omite las cédulas que ya tienen PDF y estado final. |
| `--esperar-captcha S` | Segundos de espera si aparece un desafío de imágenes (default 90). |
| `--pausa S` | Segundos entre búsquedas (default 2). |
| `--mantener-navegador` | No cierra la sesión de Playwright al terminar. |

**Captcha:** el navegador se abre visible (no headless). El checkbox de
reCAPTCHA se marca de forma asistida; si Google muestra el desafío de imágenes,
**la persona usuaria lo resuelve en esa ventana**. Si no se resuelve a tiempo,
esa cédula queda como `ERROR` y el script continúa con la siguiente.

## Rearmar el listado sin consultar

```bash
./capturas.sh --solo-csv salidas/2026-10-30_10-45-16
```

## Módulos

| Carpeta | Qué hace |
|---|---|
| `sri/` | Deudas firmes/impugnadas/facilidades de pago → un PDF por RUC. Ver [`sri/README.md`](sri/README.md). |
| `iess/` | Certificado de cumplimiento patronal → un PDF por RUC. |
| `sri-ruc/` | Contribuyentes, establecimientos y representantes legales. |
| `funcion_judicial/` | Listado de personas naturales, búsqueda y PDFs judiciales. Ver [`funcion_judicial/README.md`](funcion_judicial/README.md). |
| `ejemplos/` | Listas y CSVs de ejemplo con datos ficticios. |

## Uso responsable

Estas herramientas consultan portales de información pública, pero eso **no
significa que los datos puedan usarse para cualquier fin**:

- Úsalas solo para los fines legítimos que la ley permite (por ejemplo, una
  verificación propia o con autorización del titular).
- Respeta los términos de uso y las políticas de cada portal. No está pensado
  para extracción masiva, scraping continuo ni monitoreo de terceros.
- Los PDFs y CSVs generados contienen **datos personales**. Guárdalos de forma
  segura, no los publiques y elimínalos cuando ya no los necesites.
- En Ecuador aplica la **Ley Orgánica de Protección de Datos Personales
  (LOPDP)**: el tratamiento de datos de terceros requiere base legal,
  finalidad determinada y medidas de seguridad. La responsabilidad es de quien
  ejecuta las consultas.
- Los scripts incluyen pausas entre consultas. No las reduzcas a cero ni
  paralelices ejecuciones: puedes afectar servicios públicos y ser bloqueado.

Los autores no se hacen responsables del uso indebido de estas herramientas ni
de las consecuencias legales derivadas del tratamiento de los datos obtenidos.

## Licencia

[MIT](LICENSE). Puedes usar, copiar, modificar y redistribuir el código,
conservando el aviso de copyright.
