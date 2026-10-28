"""Inspeciona a tela de troca de unidade do SEI e o Controle de Processos.

Uso:  python -m extractor.inspecionar_troca
"""
import io
import logging
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from extractor.session import DEBUG_DIR, SessaoSei, rodar  # noqa: E402

REPORTE = DEBUG_DIR / "inspecao_troca.txt"
BASE_SEI = "https://www.sei.mg.gov.br"


def _href_troca(page_url: str, onclick: str | None) -> str | None:
    if not onclick:
        return None
    m = re.search(r"['\"]([^'\"]+)['\"]", onclick)
    return m.group(1) if m else None


async def principal() -> None:
    buf = io.StringIO()
    p = lambda *a, **k: print(*a, file=buf, **k)

    sess = SessaoSei()
    await sess.iniciar()
    await sess.garantir_login()

    page = sess.page
    await page.goto(BASE_SEI + "/sei/", wait_until="domcontentloaded")
    await page.wait_for_timeout(1500)

    try:
        onclick = await page.locator("#lnkInfraUnidade").first.get_attribute("onclick")
        p("home URL:", page.url)
        p("lnkInfraUnidade onclick:", onclick)
        href = _href_troca(page.url, onclick)
        p("href troca:", href)
        await sess.dump("inspecao_home2.html")
    except Exception as exc:
        p("erro ao achar lnkInfraUnidade:", exc)
        await sess.dump("inspecao_home2.html")
        href = None

    # Determina base do SEI a partir da URL atual
    base_atual = re.match(r"^(https?://[^/]+)", page.url)
    raiz_sei = base_atual.group(1) if base_atual else BASE_SEI

    async def navega_troca(href: str) -> None:
        await page.goto(urljoin(page.url, href), wait_until="domcontentloaded")
        await page.wait_for_timeout(2000)
        p("\n== URL:", page.url)
        await sess.dump("inspecao_troca.html")

        sel = page.locator("select#selUnidade, select[name='selUnidade']")
        nsel = await sel.count()
        p(f"select#selUnidade: {nsel}")
        if nsel:
            s = sel.first
            opts = await s.locator("option").all_inner_texts()
            vals = await s.locator("option").evaluate_all("els => els.map(e => e.value)")
            p(f"opções ({len(opts)}):")
            for o, v in zip(opts, vals):
                p(f"   {v!r:<15} {o.strip()[:100]!r}")
            cur = await s.input_value()
            p("atual:", cur)

        radios = page.locator("input[type='radio']")
        p(f"radios: {await radios.count()}")
        for i in range(await radios.count()):
            r = radios.nth(i)
            p("   radio", await r.get_attribute("name"), await r.get_attribute("value"),
              (await r.locator("..").inner_text()).strip()[:80] if await r.locator("..").count() else "")

        # qualquer elemento com nome parecido com unidade
        for nome in ("selUnidade", "txtSiglaUnidade", "chkSubordinadas",
                     "hdnIdUnidade", "selTipoUnidade"):
            el = page.locator(f"#{nome}, [name='{nome}']")
            if await el.count():
                p(f"campo {nome}: presente (n={await el.count()})")

        p("\n-- botões formulário troca:")
        for f in range(await page.locator("form").count()):
            frm = page.locator("form").nth(f)
            p(f"  form {f} id={await frm.get_attribute('id')} action={await frm.get_attribute('action')}")
            for b in range(await frm.locator("button").count()):
                btn = frm.locator("button").nth(b)
                p("    button", (await btn.inner_text()).strip()[:50], await btn.get_attribute("onclick"),
                  await btn.get_attribute("type"))
            for b in range(await frm.locator("input[type='submit']").count()):
                btn = frm.locator("input[type='submit']").nth(b)
                p("    submit", await btn.get_attribute("value"), await btn.get_attribute("onclick"))

    if href:
        await navega_troca(href)
    else:
        p("\n! sem href de troca — tenta URL padrão")
        for base in (raiz_sei, BASE_SEI):
            try:
                await page.goto(base + "/sei/controlador.php?acao=infra_trocar_unidade",
                                wait_until="domcontentloaded")
                await page.wait_for_timeout(2000)
                p("tentativa URL:", page.url)
                if await page.locator("select#selUnidade, input[type='radio']").count():
                    await sess.dump("inspecao_troca.html")
                    break
            except Exception as exc:
                p("   erro:", exc)

    # Controle de Processos da unidade atual
    p("\n-- Controle de Processos (unidade atual):")
    try:
        await page.goto(base + "/sei/", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        await page.locator("#linkMenu6").click()
        await page.wait_for_timeout(2000)
        await sess.dump("inspecao_controle.html")
        p("URL controle:", page.url)
        p("colunas data-label:", [c for c in await page.locator("td[data-label]").evaluate_all(
            "els => [...new Set(els.map(e => e.getAttribute('data-label')))]")])
        p("lInhas de dados:", await page.locator("tbody tr").count())
    except Exception as exc:
        p("erro controle:", exc)

    REPORTE.write_text(buf.getvalue(), encoding="utf-8")
    print("relatório gravado em", REPORTE)
    await sess.fechar()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    rodar(principal())