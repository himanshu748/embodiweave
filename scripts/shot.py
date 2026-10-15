import asyncio, sys
from playwright.async_api import async_playwright
async def main(out, tab=None, w=1500, h=1000, scheme="dark"):
    async with async_playwright() as p:
        b = await p.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome")
        pg = await b.new_page(viewport={"width": w, "height": h}, color_scheme=scheme)
        errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.on("pageerror", lambda e: errs.append(str(e)))
        await pg.goto("http://127.0.0.1:8000/", wait_until="networkidle")
        await pg.wait_for_timeout(1500)
        await pg.click("#play"); await pg.wait_for_timeout(2500)
        if tab:
            await pg.click(f'[data-tab="{tab}"]'); await pg.wait_for_timeout(1500)
        await pg.screenshot(path=out, full_page=True)
        print("errors:", errs)
        await b.close()
asyncio.run(main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None))
