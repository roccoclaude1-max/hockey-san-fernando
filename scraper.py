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

async def click_tab(page, name):
    tabs = await page.query_selector_all('[role="tab"]')
    for tab in tabs:
        t = (await tab.inner_text()).strip().lower()
        if name.lower() in t:
            await tab.click()
            await page.wait_for_timeout(1500)
            return True
    return False

async def scrape_fixture(page):
    fixture = []
    try:
        await click_tab(page, 'fixture')
        await page.wait_for_timeout(1000)
        btns = await page.query_selector_all('button')
        for btn in btns:
            t = (await btn.inner_text()).strip()
            if 'todas' in t.lower():
                await btn.click()
                await page.wait_for_timeout(2000)
                break
        containers = await page.query_selector_all('div.ms-sm12.mt-1')
        seen = set()
        for c in containers:
            fecha_el = await c.query_selector('span.mb-1')
            if not fecha_el:
                continue
            fecha = (await fecha_el.inner_text()).strip()
            if not re.search(r'\d{2}:\d{2}', fecha):
                continue
            local_el = await c.query_selector('span[class*="nombre-local"]')
            visita_el = await c.query_selector('span[class*="nombre-visitante"]')
            if not local_el or not visita_el:
                continue
            local = (await local_el.inner_text()).strip()
            visita = (await visita_el.inner_text()).strip()
            key = (fecha, local, visita)
            if key in seen:
                continue
            seen.add(key)
            score_divs = await c.query_selector_all('div.score')
            jugado = False
            score_local = score_visita = ''
            if len(score_divs) >= 2:
                s1 = (await score_divs[0].inner_text()).strip()
                s2 = (await score_divs[1].inner_text()).strip()
                if s1.isdigit() and s2.isdigit():
                    jugado = True
                    score_local, score_visita = s1, s2
            partido = {"local": local, "visita": visita, "fecha": fecha, "jugado": jugado}
            if jugado:
                partido["scoreLocal"] = score_local
                partido["scoreVisita"] = score_visita
            fixture.append(partido)
    except Exception as e:
        print(f"  Error fixture: {e}")
    return fixture

async def scrape_tabla(page, tab_name):
    headers = []
    rows = []
    try:
        if not await click_tab(page, tab_name):
            return {"headers": [], "rows": []}
        await page.wait_for_timeout(1500)
        ths = await page.query_selector_all('th')
        seen_h = set()
        for th in ths:
            t = (await th.inner_text()).strip()
            if t and t not in seen_h:
                headers.append(t)
                seen_h.add(t)
            elif t and t in seen_h:
                break
        trs = await page.query_selector_all('tr')
        seen_r = set()
        for tr in trs:
            tds = await tr.query_selector_all('td')
            if not tds:
                continue
            row = [(await td.inner_text()).strip() for td in tds]
            if not any(row):
                continue
            key = tuple(row)
            if key in seen_r:
                continue
            seen_r.add(key)
            rows.append(row)
    except Exception as e:
        print(f"  Error {tab_name}: {e}")
    return {"headers": headers, "rows": rows}

async def scrape_cat(page, cat):
    print(f"[{cat['id']}] {cat['url']}")
    await page.goto(cat['url'], wait_until='networkidle', timeout=60000)
    await page.wait_for_timeout(3000)
    fixture = await scrape_fixture(page)
    posiciones = await scrape_tabla(page, 'posicion')
    goleadores = await scrape_tabla(page, 'goleador')
    print(f"  [{cat['id']}] fix={len(fixture)} pos={len(posiciones['rows'])} gol={len(goleadores['rows'])}")
    return {"id": cat["id"], "nombre": cat["nombre"], "tipo": cat["tipo"],
            "fixture": fixture, "posiciones": posiciones, "goleadores": goleadores}

async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
        context = await browser.new_context(viewport={"width":1280,"height":900}, locale="es-AR")
        page = await context.new_page()
        datos = []
        for cat in CATEGORIAS:
            try:
                datos.append(await scrape_cat(page, cat))
            except Exception as e:
                print(f"ERROR {cat['id']}: {e}")
                datos.append({"id":cat["id"],"nombre":cat["nombre"],"tipo":cat["tipo"],
                               "fixture":[],"posiciones":{"headers":[],"rows":[]},"goleadores":{"headers":[],"rows":[]}})
        await browser.close()
    with open("datos.json","w",encoding="utf-8") as f:
        json.dump({"actualizado":datetime.now(timezone.utc).isoformat(),"datos":datos},f,ensure_ascii=False,indent=2)
    print("\ndatos.json guardado.")

asyncio.run(main())
