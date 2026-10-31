# Consulta SRI — deudas firmes, impugnadas y en facilidades de pago

Automatiza la consulta pública del SRI y guarda **un PDF por cédula/RUC** con el
mismo formato que el `Ctrl+P → Guardar como PDF` de Chrome.

Página consultada:
<https://srienlinea.sri.gob.ec/sri-en-linea/SriPagosWeb/ConsultaDeudasFirmesImpugnadas/Consultas/consultaDeudasFirmesImpugnadas>

## Archivos

| Archivo | Para qué sirve |
|---|---|
| `sri.sh` | Lanzador. Recibe las cédulas y genera los PDFs. |
| `sri-template.js` | Flujo dentro del navegador (llenar, consultar, imprimir). |
| `pw-sri.json` | Config del navegador (User-Agent, locale, timezone). |
| `csv-deudas.py` | Arma `deudas.csv` (tipo de deuda + monto + motivo) leyendo los PDFs. |
| `../capturas.sh` | Ejecuta SRI + IESS + SRI-RUC y deja todo en `salidas/<fecha>/`. |
| `../judicial.sh` | Prepara el listado y busca en Función Judicial. |

## Requisitos

`playwright-cli` (viene con `@playwright/cli`) y Chromium instalado:

```bash
playwright-cli install-browser chromium
```

## Uso

Para la ejecución completa (SRI + IESS + SRI-RUC + CSV maestro) usa el
lanzador de la raíz; no hace falta abrir el navegador a mano:

```bash
./capturas.sh 1790012345001 0912345678001
```

El resultado queda en `salidas/<fecha_hora>/`, con `sri/`, `iess/`,
`contribuyentes/` y `funcion_judicial/funcion-judicial.csv`. Los RUC se pasan
siempre como argumentos (no hay un `rucs.txt` fijo); también se acepta
`@lista.txt`.

### Solo el módulo SRI

```bash
cd sri

# 1) Abrir el navegador una sola vez (queda vivo ~1 hora)
playwright-cli -s=sri open --config=./pw-sri.json \
  "https://srienlinea.sri.gob.ec/sri-en-linea/SriPagosWeb/ConsultaDeudasFirmesImpugnadas/Consultas/consultaDeudasFirmesImpugnadas"

# 2) Consultar las cédulas que quieras
./sri.sh 1712345678 0912345678

# 3) Cerrar el navegador
playwright-cli -s=sri close
```

Salida: `cedula-<numero>.pdf` en esta misma carpeta (~4–5 s por cédula).
Se puede cambiar con `SRI_OUTDIR=/otra/ruta ./sri.sh ...`.

La consola devuelve un JSON con `archivo`, `encabezado` (fecha/hora) y `resumen`
(nombre + si registra deudas), útil para armar un CSV.

## CSV de deudas

```bash
./csv-deudas.py capturas capturas/deudas.csv lista-rucs.txt
```

Lee los PDFs (no vuelve a consultar el SRI) y genera un formato largo, una fila
por tipo de deuda con monto > 0:

```csv
codigo_unico,nombre,estado,tipo_deuda,cantidad,motivo
0912345678001,GOMEZ RUIZ ANA MARIA,CON DEUDAS,Facilidades de pago,"1,250.00",
1790012345001,PEREZ PEREZ JUAN,SIN DEUDAS,,0.00,
1712345678001,,ERROR,,,No se generó el PDF
```

Los montos van entre comillas porque el separador de miles es coma. Los RUC sin
PDF o con PDF ilegible quedan como `ERROR` en la misma fila, con el motivo en
la última columna; ya no se crea un CSV aparte para los errores.

## Detalles que importan

- **User-Agent**: el sitio está detrás de un WAF que cuelga la conexión con
  navegadores automatizados (`HeadlessChrome`). `pw-sri.json` envía un UA de
  Chrome real en Windows; sin eso la navegación nunca termina.
- **`page.pdf()`** usa el mismo motor de impresión que `Ctrl+P`, aplica el
  `@media print` del sitio y no abre diálogo.
- **Encabezado/pie**: se replican con `headerTemplate`/`footerTemplate`
  (fecha arriba-izq, título arriba-centro, URL abajo-izq, `n/total` abajo-der).
  `<span class="pageNumber">` y `totalPages` los rellena Chromium.
- **`printBackground: true`** conserva la barra azul del SRI y el check verde.
- **Selectores por rol** (`getByRole`) porque el sitio es Angular y sus clases
  cambian. Si el SRI rediseña la página, hay que ajustar `sri-template.js`.
- `format: 'A4'` a propósito: el sitio declara un `@page` en A3 y con
  `preferCSSPageSize` saldría una hoja enorme.
