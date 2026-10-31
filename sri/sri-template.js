// Consulta de deudas firmes SRI -> PDF con el mismo formato que Ctrl+P de Chrome
// __CEDULA__ y __OUTFILE__ se reemplazan por sri.sh
async (page) => {
  const cedula = "__CEDULA__";
  const out = "__OUTFILE__";

  // 1. Si estamos en una página de resultados, volver al formulario
  const nueva = page.getByRole('button', { name: 'Nueva consulta' });
  if (await nueva.count()) {
    await nueva.first().click();
  }

  // 2. Escribir la cédula
  const input = page.getByRole('textbox', { name: 'RUC / cédula' });
  await input.waitFor({ state: 'visible', timeout: 30000 });
  await input.fill('');
  await input.fill(cedula);
  await page.waitForTimeout(300);

  // 3. Esperar a que "Consultar" se habilite y hacer clic
  const btn = page.getByRole('button', { name: 'Consultar' });
  let habilitado = false;
  for (let i = 0; i < 60; i++) {
    if (await btn.first().isEnabled()) { habilitado = true; break; }
    await page.waitForTimeout(250);
  }
  if (!habilitado) {
    return JSON.stringify({ cedula, error: 'El botón Consultar no se habilitó (¿cédula inválida?)' });
  }
  await btn.first().click();

  // 4. Esperar la respuesta
  try {
    await page.getByText('Fecha de corte').first().waitFor({ timeout: 90000 });
  } catch (e) {
    return JSON.stringify({ cedula, error: 'Sin respuesta del SRI: ' + e.message.slice(0, 150) });
  }
  await page.waitForTimeout(1500);

  // 5. PDF con encabezado/pie estilo Chrome (fecha, titulo, URL, pagina x/y)
  const ahora = new Date();
  const fechaChrome =
    (ahora.getMonth() + 1) + '/' + ahora.getDate() + '/' + String(ahora.getFullYear()).slice(-2) + ', ' +
    ((ahora.getHours() % 12) || 12) + ':' + String(ahora.getMinutes()).padStart(2, '0') + ' ' +
    (ahora.getHours() >= 12 ? 'PM' : 'AM');

  const titulo = await page.title();
  const url = page.url();
  const fs = 'font-size:7.5px;color:#000;font-family:Arial,Helvetica,sans-serif;';

  const header = ''
    + '<div style="width:100%;' + fs + 'padding:0 10mm;">'
    + '<table style="width:100%;border-collapse:collapse;"><tr>'
    + '<td style="text-align:left;width:25%;">' + fechaChrome + '</td>'
    + '<td style="text-align:center;width:50%;">' + titulo + '</td>'
    + '<td style="text-align:right;width:25%;"></td>'
    + '</tr></table></div>';

  const footer = ''
    + '<div style="width:100%;' + fs + 'padding:0 10mm;">'
    + '<table style="width:100%;border-collapse:collapse;"><tr>'
    + '<td style="text-align:left;width:75%;">' + url + '</td>'
    + '<td style="text-align:right;width:25%;"><span class="pageNumber"></span>/<span class="totalPages"></span></td>'
    + '</tr></table></div>';

  await page.pdf({
    path: out,
    format: 'A4',
    printBackground: true,
    displayHeaderFooter: true,
    headerTemplate: header,
    footerTemplate: footer,
    margin: { top: '15mm', bottom: '15mm', left: '10mm', right: '10mm' }
  });

  const texto = (await page.evaluate(() => document.body.innerText))
    .replace(/\n{2,}/g, '\n')
    .trim();

  return JSON.stringify({ cedula, archivo: out, encabezado: fechaChrome, resumen: texto.slice(0, 1200) });
}
