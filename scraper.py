import asyncio, json, re
from datetime import datetime, timezone
from playwright.async_api import async_playwright

CATEGORIAS = [
    {"id": "cab-a", "nombre": "Caballeros A", "tipo": "cab",
     "url": "https://tournamenttracker.buenosaireshockey.ar/RUdVX3ViflQ=?clubId=00000006"},
    {"id": "cab-b", "nombre": "Caballeros B", "tipo": "cab",
     "url": "https://tournamenttracker.buenosaireshockey.ar/RUdVX3Zhe10=?clubId=00000006"},
    {"id": "cab-c", "nombre": "Caballeros C", "tipo": "cab",
     "url": "https://tournamenttracker.buenosaireshockey.ar/RUdVX3ZheFU=?clubId=00000006"},
    {"id": "dam-a", "nombre": "Damas A", "tipo": "dam",
     "url": "https://tournamenttracker.buenosaireshockey.ar/RUdVX3VlfFw=?clubId=00000006"},
    {"id": "dam-b", "nombre": "Damas B", "tipo": "dam",
     "url": "https://tournamenttracker.buenosaireshockey.ar/RUdVX3Vle1M=?clubId=00000006"},
    {"id": "dam-c", "nombre": "Damas C", "tipo": "dam",
     "url": "https://tournamenttracker.buenosaireshockey.ar/RUdVX3VieVM=?clubId=00000006"},
    {"id": "dam-d", "nombre": "Damas D", "tipo": "dam",
     "url": "https://tournamenttracker.buenosaireshockey.ar/RUdVX3ZgfVY=?clubId=00000006"},
    {"id": "dam-e", "nombre": "Damas E", "tipo": "dam",
     "url": "https://tournamenttracker.buenosaireshockey.ar/RUdVX3ZgeVM=?clubId=00000006"},
]

SF = re.compile(r'san\s*fern', re.I)

async def scrape_cat(page, cat):
    print(f"[{cat['id']}] Cargando {cat['url']}")
    await page.goto(cat['url'], wait_until='networkidle', timeout=60000)
    await page.wait_for_timeout(3000)

    fixture = []
    posiciones = {"headers": [], "rows": []}
    goleadores = {"headers": [], "rows": []}

    # === FIXTURE ===
    try:
        # click en todas las fechas disponibles
        date_btns = await page.query_selector_all('button[data-automation-key]')
        date_keys = []
        for btn in date_btns:
            key = await btn.get_attribute('data-automation-key')
            text = (await btn.inner_text()).strip()
            if re.match(r'^\d+$', text):
                date_keys.append((int(text), btn))
        date_keys.sort(key=lambda x: x[0])

        if not date_keys:
            # intentar con botones numericos sin data-automation-key
            btns_all = await page.query_selector_all('button')
            for btn in btns_all:
                t = (await btn.inner_text()).strip()
                if re.match(r'^\d+$', t) and int(t) <= 30:
                    date_keys.append((int(t), btn))
            date_keys.sort(key=lambda x: x[0])

        print(f"  [{cat['id']}] {len(date_keys)} fechas encontradas")

        seen = set()
        for _, btn in date_keys:
            try:
                await btn.click()
                await page.wait_for_timeout(1500)
                rows = await page.query_selector_all('.ms-List-cell:not(.ms-hiddenSm)')
                for row in rows:
                    txt = await row.inner_text()
                    lines = [l.strip() for l in txt.strip().split('\n') if l.strip()]
                    if len(lines) < 3:
                        continue
                    # buscar score o 'vs'
                    score_pat = re.search(r'(\d+)\s*[-–]\s*(\d+)', txt)
                    local = lines[0] if lines else ''
                    visita = lines[-1] if lines else ''
                    fecha_raw = ''
                    for l in lines:
                        if re.search(r'\d{1,2}\s+[a-z]{3}', l, re.I) or re.search(r'\d{1,2}/\d{1,2}', l):
                            fecha_raw = l
                            break
                    key = (local, visita, fecha_raw)
                    if key in seen:
                        continue
                    seen.add(key)
                    partido = {"local": local, "visita": visita, "fecha": fecha_raw, "jugado": bool(score_pat)}
                    if score_pat:
                        partido["scoreLocal"] = score_pat.group(1)
                        partido["scoreVisita"] = score_pat.group(2)
                    if SF.search(local) or SF.search(visita):
                        fixture.append(partido)
            except Exception as e:
                print(f"  Error en fecha: {e}")
    except Exception as e:
        print(f"  [{cat['id']}] Error fixture: {e}")

    # === POSICIONES ===
    try:
        pos_tab = None
        tabs = await page.query_selector_all('[role="tab"]')
        for tab in tabs:
            t = (await tab.inner_text()).lower()
            if 'posici' in t or 'standing' in t or 'tabla' in t:
                pos_tab = tab
                break
        if pos_tab:
            await pos_tab.click()
            await page.wait_for_timeout(2000)
            headers = []
            rows = []
            ths = await page.query_selector_all('th, [role="columnheader"]')
            headers = [await th.inner_text() for th in ths if (await th.inner_text()).strip()]
            trs = await page.query_selector_all('tr, [role="row"]')
            for tr in trs:
                tds = await tr.query_selector_all('td, [role="gridcell"]')
                if tds:
                    row = [(await td.inner_text()).strip() for td in tds]
                    if any(row):
                        rows.append(row)
            if headers or rows:
                posiciones = {"headers": headers, "rows": rows}
    except Exception as e:
        print(f"  [{cat['id']}] Error posiciones: {e}")

    # === GOLEADORES ===
    try:
        gol_tab = None
        tabs = await page.query_selector_all('[role="tab"]')
        for tab in tabs:
            t = (await tab.inner_text()).lower()
            if 'gol' in t or 'scorer' in t or 'anotad' in t:
                gol_tab = tab
                break
        if gol_tab:
            await gol_tab.click()
            await page.wait_for_timeout(2000)
            headers = []
            rows = []
            ths = await page.query_selector_all('th, [role="columnheader"]')
            headers = [await th.inner_text() for th in ths if (await th.inner_text()).strip()]
            trs = await page.query_selector_all('tr, [role="row"]')
            for tr in trs:
                tds = await tr.query_selector_all('td, [role="gridcell"]')
                if tds:
                    row = [(await td.inner_text()).strip() for td in tds]
                    if any(row):
                        rows.append(row)
            if headers or rows:
                goleadores = {"headers": headers, "rows": rows}
    except Exception as e:
        print(f"  [{cat['id']}] Error goleadores: {e}")

    print(f"  [{cat['id']}] fixture={len(fixture)} pos_rows={len(posiciones['rows'])} gol_rows={len(goleadores['rows'])}")
    return {
        "id": cat["id"],
        "nombre": cat["nombre"],
        "tipo": cat["tipo"],
        "fixture": fixture,
        "posiciones": posiciones,
        "goleadores": goleadores,
    }

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
        context = await browser.new_context(viewport={"width": 1280, "height": 900}, locale="es-AR")
        page = await context.new_page()

        datos = []
        for cat in CATEGORIAS:
            try:
                result = await scrape_cat(page, cat)
                datos.append(result)
            except Exception as e:
                print(f"ERROR en {cat['id']}: {e}")
                datos.append({"id": cat["id"], "nombre": cat["nombre"], "tipo": cat["tipo"],
                              "fixture": [], "posiciones": {"headers": [], "rows": []},
                              "goleadores": {"headers": [], "rows": []}})

        await browser.close()

    output = {
        "actualizado": datetime.now(timezone.utc).isoformat(),
        "datos": datos
    }
    with open("datos.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print("\ndatos.json guardado.")

asyncio.run(main())
