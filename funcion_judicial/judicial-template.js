// Una búsqueda en Función Judicial como Demandado/Procesado.
// __CEDULA__, __NOMBRE__, __OUTFILE__, __URL__ y __ESPERAR_CAPTCHA__ los
// reemplaza judicial.py. __ESPERAR_CAPTCHA__ va en segundos.
async (page) => {
  const cedula = __CEDULA__;
  const nombre = __NOMBRE__;
  const out = __OUTFILE__;
  const url = __URL__;
  const esperarCaptchaMs = __ESPERAR_CAPTCHA__ * 1000;

  const error = (mensaje) => JSON.stringify({
    cedula, nombre, estado: 'ERROR', error: mensaje
  });

  try {
    // 1. Formulario
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 60000 });

    const inputCedula = page.locator(
      'input[placeholder="Ingrese la identificación del Demandado/Procesado"]'
    ).first();
    await inputCedula.waitFor({ state: 'visible', timeout: 30000 });
    await inputCedula.fill('');
    await inputCedula.fill(cedula);

    const inputNombre = page.locator(
      'input[placeholder="Ingrese los apellidos y nombres del Demandado/Procesado"]'
    ).first();
    await inputNombre.waitFor({ state: 'visible', timeout: 15000 });
    await inputNombre.fill('');
    await inputNombre.fill(nombre);
    await page.waitForTimeout(300);

    // 2. Primer BUSCAR (dispara el captcha)
    const buscar = page.locator('button[type="submit"].boton-buscar').first();
    await buscar.waitFor({ state: 'visible', timeout: 15000 });

    let habilitado = false;
    for (let i = 0; i < 60; i++) {
      if (await buscar.isEnabled()) {
        habilitado = true;
        break;
      }
      await page.waitForTimeout(250);
    }
    if (!habilitado) {
      return error('El formulario no se habilitó (revise el nombre o la cédula)');
    }
    await buscar.click();

    // 3. Captcha
    const anchor = page.frameLocator(
      'iframe[src*="recaptcha/api2/anchor"]'
    ).locator('#recaptcha-anchor');
    await anchor.waitFor({ state: 'visible', timeout: 30000 });

    const yaMarcado = (await anchor.getAttribute('aria-checked')) === 'true';
    if (!yaMarcado) {
      await anchor.click();
    }

    let captchaOk = yaMarcado;
    const inicioCaptcha = Date.now();
    while (Date.now() - inicioCaptcha < esperarCaptchaMs) {
      const hayIframe = await page.locator(
        'iframe[src*="recaptcha/api2/anchor"]'
      ).count();
      if (!hayIframe) {
        captchaOk = true;
        break;
      }
      const estado = await anchor.getAttribute('aria-checked').catch(() => null);
      if (estado === 'true') {
        captchaOk = true;
        break;
      }
      await page.waitForTimeout(500);
    }
    if (!captchaOk) {
      return error('captcha no resuelto');
    }

    // El sitio espera el evento success; le damos el margen que pediste.
    await page.waitForTimeout(4000);

    // 4. Segundo BUSCAR (consulta real)
    await page.locator('button[type="submit"].boton-buscar').first().click();

    // 5. Esperar resultado
    let estadoFinal = null;
    let mensajeError = '';
    const inicioBusqueda = Date.now();
    while (Date.now() - inicioBusqueda < 90000) {
      if (page.url().includes('/causas')) {
        estadoFinal = 'CON CAUSAS';
        break;
      }
      if (await page.getByText(/La consulta no devolvió resultados/i).count()) {
        estadoFinal = 'SIN CAUSAS';
        break;
      }
      if (await page.getByText(/Ingrese los datos exactos de la causa/i).count()) {
        mensajeError = 'La consulta devolvió el mensaje de datos exactos / error';
        break;
      }
      await page.waitForTimeout(500);
    }

    if (!estadoFinal) {
      return error(mensajeError || 'sin respuesta de la consulta');
    }

    if (estadoFinal === 'CON CAUSAS') {
      await page.getByText(/registros encontrados/i).first()
        .waitFor({ timeout: 30000 }).catch(() => {});
      await page.locator('mat-paginator').first()
        .waitFor({ timeout: 30000 }).catch(() => {});
      await page.waitForTimeout(1000);
    } else {
      await page.waitForTimeout(500);
    }

    // 6. PDF estilo Ctrl+P de Chrome
    const ahora = new Date();
    const fechaChrome =
      (ahora.getMonth() + 1) + '/' + ahora.getDate() + '/' +
      String(ahora.getFullYear()).slice(-2) + ', ' +
      ((ahora.getHours() % 12) || 12) + ':' +
      String(ahora.getMinutes()).padStart(2, '0') + ' ' +
      (ahora.getHours() >= 12 ? 'PM' : 'AM');

    const titulo = await page.title();
    const pageUrl = page.url();
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
      + '<td style="text-align:left;width:75%;">' + pageUrl + '</td>'
      + '<td style="text-align:right;width:25%;">'
      + '<span class="pageNumber"></span>/<span class="totalPages"></span>'
      + '</td></tr></table></div>';

    await page.pdf({
      path: out,
      format: 'A4',
      printBackground: true,
      displayHeaderFooter: true,
      headerTemplate: header,
      footerTemplate: footer,
      margin: { top: '15mm', bottom: '15mm', left: '10mm', right: '10mm' }
    });

    return JSON.stringify({ cedula, nombre, archivo: out, estado: estadoFinal });
  } catch (e) {
    return error((e && e.message ? e.message : String(e)).slice(0, 300));
  }
}
