"""Inspeciona a tela de pesquisa do SEI: despeja campos do formulário em data/debug.

Uso:  python -m extractor.inspecionar
"""
import asyncio
import io
import logging
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from extractor.cfg_ext import sei_base  # noqa: E402
from extractor.scraping import achar_pesquisa  # noqa: E402
from extractor.session import DEBUG_DIR, SessaoSei, rodar  # noqa: E402

REPORTE = DEBUG_DIR / "inspecao_relatorio.txt"


async def principal() -> None:
    buf = io.StringIO()
    p = lambda *a, **k: print(*a, file=buf, **k)

    sess = SessaoSei()
    await sess.iniciar()
    await sess.garantir_login()

    try:
        await sess.page.goto(sei_base() + "/sei/", wait_until="domcontentloaded")
        await sess.page.wait_for_timeout(1500)
        await sess.dump("inspecao_home.html")
        p("URL home:", sess.page.url)
    except Exception as exc:
        p("erro ao abrir home:", exc)

    url = await achar_pesquisa(sess.page)
    p("URL pesquisa:", url)
    await sess.dump("inspecao_pesquisa.html")

    page = sess.page
    forms = page.locator("form")
    nf = await forms.count()
    p(f"\nFORMULÁRIOS: {nf}")
    for i in range(nf):
        f = forms.nth(i)
        fname = (await f.get_attribute("name")) or await f.get_attribute("id")
        p(f"\n===== form {i}: name/id={fname!r} action={await f.get_attribute('action')} =====")

        seletores = f.locator("select")
        ns = await seletores.count()
        p(f"-- SELECTS ({ns})")
        for s in range(ns):
            sel = seletores.nth(s)
            nome = (await sel.get_attribute("name")) or (await sel.get_attribute("id"))
            multi = await sel.get_attribute("multiple")
            opts_texto = await sel.locator("option").all_inner_texts()
            opts_val = await sel.locator("option").evaluate_all("els => els.map(e => e.value)")
            sel_atual = await sel.input_value() if not multi else "(multi)"
            p(f"   [{s}] {nome or '(sem nome)'} multiple={bool(multi)} atual={sel_atual}")
            for o, v in zip(opts_texto, opts_val):
                p(f"        {v!r:<10} {o.strip()[:90]!r}")

        texts = f.locator("input[type='text']")
        nt = await texts.count()
        p(f"-- INPUTS TEXT ({nt})")
        for t in range(nt):
            ipt = texts.nth(t)
            p(f"   [{t}] name={await ipt.get_attribute('name')} id={await ipt.get_attribute('id')} "
              f"title={await ipt.get_attribute('title')} class={await ipt.get_attribute('class')}")

        btns = f.locator("button")
        nb = await btns.count()
        p(f"-- BUTTONS ({nb})")
        for b in range(nb):
            btn = btns.nth(b)
            p(f"   [{b}] text={(await btn.inner_text()).strip()!r} onclick={await btn.get_attribute('onclick')} "
              f"type={await btn.get_attribute('type')} class={await btn.get_attribute('class')}")

        subs = f.locator("input[type='submit']")
        p(f"-- SUBMITS ({await subs.count()})")
        for s in range(await subs.count()):
            p("   ", await subs.nth(s).get_attribute("value"), await subs.nth(s).get_attribute("onclick"))

        bots = f.locator("a", has_text=re.compile("Selecionar|Pesquisar", re.I))
        p(f"-- LINKS-BOTÃO ({await bots.count()})")
        for b in range(await bots.count()):
            p(f"   [{b}] text={(await bots.nth(b).inner_text()).strip()!r} onclick={await bots.nth(b).get_attribute('onclick')}")

        p("-- HIDDENS:")
        for h in range(await f.locator("input[type='hidden']").count()):
            hd = f.locator("input[type='hidden']").nth(h)
            p(f"   {await hd.get_attribute('name')}={await hd.get_attribute('value')}")

    REPORTE.write_text(buf.getvalue(), encoding="utf-8")
    print("relatório gravado em", REPORTE)
    await sess.fechar()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    rodar(principal())