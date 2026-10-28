from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from extractor import session  # noqa: E402
from extractor.scraping import sei_base, urljoin  # noqa: E402

DEBUG = RAIZ / "data" / "debug"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")


async def principal() -> None:
    sess = session.SessaoSei()
    await sess.iniciar()
    await sess.garantir_login()

    page = sess.page

    # abrir Painel de Controle pelo menu
    onclick = None
    try:
        onclick = await page.locator("#linkMenu19").first.get_attribute("onclick")
    except Exception:
        pass
    href = None
    if onclick:
        import re
        m = re.search(r"['\"]([^'\"]+)['\"]", onclick)
        href = m.group(1) if m else None
    if not href:
        href = await page.locator("#linkMenu19").first.get_attribute("href")
    print("href painel:", href)

    if href:
        await page.goto(urljoin(sei_base() + "/sei/", href), wait_until="domcontentloaded")
    else:
        await page.locator("#linkMenu19").first.click()
        await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(6000)

    print("URL atual:", page.url)
    html = await page.content()
    (DEBUG / "painel_controle.html").write_text(html, encoding="utf-8", errors="replace")
    print("dump:", DEBUG / "painel_controle.html", f"({len(html)} bytes)")

    # iframes e containers
    iframes = page.locator("iframe")
    n = await iframes.count()
    print(f"iframes: {n}")
    for i in range(n):
        fr = iframes.nth(i)
        try:
            src = await fr.get_attribute("src")
            title = await fr.get_attribute("title") or ""
        except Exception:
            src = title = ""
        print(f"  iframe[{i}]: src={src[:160]} title={title[:60]}")

    # estrutura textual (cards)
    texto = await page.inner_text("body")
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    print("--- trecho do texto da página ---")
    print("\n".join(linhas[:80]))

    await sess.fechar()


if __name__ == "__main__":
    asyncio.run(principal())