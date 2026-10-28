from __future__ import annotations

import asyncio
import logging
import random
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

from extractor.cfg_ext import pausa_max, pausa_min, sei_base

log = logging.getLogger("extractor.scraping")

NUMERO_SEI = re.compile(r"\b\d{2,3}(\.\s|\s*\.\s*)?\d{1,9}(\.\s|\s*\.\s*)?\d{1,3}-\d{1,2}\b")
NUMERO_SEI_CONTROLE = re.compile(r"\b\d{2,6}\.\d{1,2}\.\d{4,8}/\d{4}-\d{2}\b")
LESS_PROXIMA = re.compile(r"pr[oó]xima", re.I)

DATA_BR = re.compile(r"(\d{2})/(\d{2})/(\d{4})")

from extractor.session import DEBUG_DIR  # noqa: E402


async def pausa() -> None:
    await asyncio.sleep(random.uniform(pausa_min(), pausa_max()))


async def achar_pesquisa(page) -> str:
    candidatos = [
        "/sei/modulos/pesquisa/geral/pesquisa_processos_exibir.php",
        "/sei/md_pesq_processo_pesquisar_exibir.php?acao_origem=sistema",
    ]
    for url in candidatos:
        try:
            await page.goto(sei_base() + url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_timeout(1500)
            if (await page.locator("form").count()) > 0 and "Not Found" not in await page.inner_text("body"):
                log.info("pesquisa aberta (URL direta): %s", page.url)
                return page.url
        except Exception:
            continue

    # Caminho padrão: home → item de menu "Pesquisa" (hash CSRF gerado pela tela)
    await page.goto(sei_base() + "/sei/", wait_until="domcontentloaded", timeout=45000)
    await page.wait_for_timeout(1500)
    links = page.locator("a", has_text=re.compile("Pesquis"))
    n = await links.count()
    for i in range(n):
        txt = (await links.nth(i).inner_text()).strip()
        if "pública" in txt.lower() or "publica" in txt.lower():
            continue
        try:
            await links.nth(i).click()
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1800)
            corpo = await page.inner_text("body")
            if (await page.locator("form").count()) > 0 and "not found" not in corpo.lower():
                log.info("pesquisa aberta (menu): %s", page.url)
                return page.url
        except Exception:
            continue

    raise RuntimeError("não encontrei a tela de pesquisa de processos")


async def achar_tabela_resultado(page):
    tabelas = page.locator("table")
    n = await tabelas.count()
    for i in range(n):
        t = tabelas.nth(i)
        try:
            txt = (await t.inner_text()).lower()
        except Exception:
            continue
        tem_processo = "processo" in txt
        tem_tipo_situa = ("tipo" in txt) or ("situa" in txt) or ("unidade" in txt and "data" in txt)
        if tem_processo and tem_tipo_situa:
            return t
    return None


async def ler_cabecalho(tabela) -> list[str]:
    linhas = tabela.locator("tr")
    n = await linhas.count()
    for i in range(n):
        celulas = await linhas.nth(i).locator("th, td").all_inner_texts()
        limpos = [_limpar(c) for c in celulas if c.strip()]
        if limpos and any("processo" in c.lower() for c in limpos):
            return limpos
    return []


def _limpar(texto: str) -> str:
    return " ".join(str(texto).replace("\n", " ").replace("\t", " ").split()).strip()


def _col(txt: list[str], cabecalho: list[str], chave: str) -> str:
    if not cabecalho:
        return ""
    idx = None
    for j, h in enumerate(cabecalho):
        if chave.lower() in h.lower():
            idx = j
            break
    if idx is None or idx >= len(txt):
        return ""
    return txt[idx]


async def coletar_processos(page, unidade: str, max_paginas: int) -> list[dict]:
    resultados: dict[str, dict] = {}
    pagina = 1
    while True:
        tabela = await achar_tabela_resultado(page)
        if tabela is None:
            log.warning("unidade %s página %d sem tabela de resultado", unidade, pagina)
            break

        if pagina == 1:
            html = await page.content()
            (DEBUG_DIR / f"pesquisa_{unidade}_p1.html").write_text(
                html, encoding="utf-8", errors="replace"
            )

        cabecalho = await ler_cabecalho(tabela)
        novas = await _parse_linhas(tabela, cabecalho)
        novos_n = 0
        for r in novas:
            if r["numero"] and r["numero"] not in resultados:
                resultados[r["numero"]] = r
                novos_n += 1
        log.info(
            "unidade %s: página %d → %d linhas (%d novas) | cabeçalho: %s",
            unidade, pagina, len(novas), novos_n, cabecalho,
        )

        if pagina >= max_paginas or not await _proxima_pagina(page):
            break
        pagina += 1

    return list(resultados.values())


async def _parse_linhas(tabela, cabecalho: list[str]) -> list[dict]:
    linhas = tabela.locator("tr")
    n = await linhas.count()
    saida: list[dict] = []
    for i in range(n):
        linha = linhas.nth(i)
        celulas = await linha.locator("th, td").all_inner_texts()
        if not celulas:
            continue
        txt = [_limpar(c) for c in celulas]
        if txt and any("processo" in (c or "").lower() for c in txt):
            continue  # linha de cabeçalho

        numero = None
        for c in txt:
            m = NUMERO_SEI.search(c)
            if m:
                numero = _normalizar_numero(m.group(0))
                break
        if not numero:
            continue

        links = linha.locator("a[href]")
        href = None
        if await links.count():
            href = await links.first.get_attribute("href")

        if cabecalho and len(txt) != len(cabecalho) and len(txt) > len(cabecalho):
            # primeira célula costuma ser checkbox/imagem
            txt = txt[-len(cabecalho):]

        prioridade = _col(txt, cabecalho, "prioridade")
        saida.append({
            "numero": numero,
            "tipo": _col(txt, cabecalho, "tipo"),
            "situacao": _col(txt, cabecalho, "situa"),
            "unidade_txt": _col(txt, cabecalho, "unidade"),
            "prioridade": 1 if prioridade and prioridade.lower() not in ("", "não", "nao", "n") else 0,
            "marcadores_txt": _col(txt, cabecalho, "marcador"),
            "link_sei": urljoin(sei_base(), href) if href else None,
            "celulas": txt,
            "cabecalho": cabecalho,
        })
    return saida


def _normalizar_numero(valor: str) -> str:
    return re.sub(r"\s+", "", valor)


async def _proxima_pagina(page) -> bool:
    candidatos = [
        page.locator("a[title='Próxima']"),
        page.locator("a[title='Proxima']"),
        page.locator("a[title='próxima']"),
        page.locator("a", has_text=LESS_PROXIMA).last,
    ]
    for loc in candidatos:
        try:
            if await loc.count() and await loc.first.is_visible():
                await loc.first.click()
                await page.wait_for_load_state("domcontentloaded")
                await pausa()
                return True
        except Exception:
            continue
    return False


# ---------------------------------------------------------------------------
# Extração via "Controle de Processos" (procedimento_controlar)
# ---------------------------------------------------------------------------

def _extrair_href_onclick(onclick: str | None) -> str | None:
    if not onclick:
        return None
    m = re.search(r"['\"]([^'\"]+)['\"]", onclick)
    return m.group(1) if m else None


async def _unidade_atual(page) -> str | None:
    """Sigla atual (DGTI/DGTM/DRTC/STIM) exibida no seletor de unidade."""
    try:
        el = page.locator("#lnkInfraUnidade").first
        if not await el.count():
            return None
        txt = (await el.inner_text()).strip()
        if "/" in txt:
            return txt.split("/", 1)[1].strip()
    except Exception:
        pass
    return None


async def trocar_unidade(page, sigla: str) -> int:
    """Troca a unidade de trabalho do SEI para SEINFRA/<sigla>.

    Retorna o id da unidade (ex.: 110001770 para DGTI).
    """
    atual = await _unidade_atual(page)
    if atual and atual.upper() == sigla.upper():
        return _id_unidade_url(page.url)

    def _href_da_pagina():
        try:
            return page.locator("#lnkInfraUnidade").first.get_attribute("onclick")
        except Exception:
            return None

    onclick = None
    for _ in range(3):
        onclick = await _href_da_pagina()
        if onclick:
            break
        await page.wait_for_timeout(800)
    href = _extrair_href_onclick(onclick) if onclick else None
    if not href:
        await page.goto(sei_base() + "/sei/", wait_until="domcontentloaded")
        await page.wait_for_timeout(1200)
        onclick = None
        for _ in range(3):
            onclick = await _href_da_pagina()
            if onclick:
                break
            await page.wait_for_timeout(800)
        href = _extrair_href_onclick(onclick)
    if not href:
        raise RuntimeError("não encontrei o link de troca de unidade")

    await page.goto(urljoin(sei_base() + "/sei/", href), wait_until="domcontentloaded")
    # espera a tela de seleção de unidade carregar (não é imediata sob lentidão)
    radio = page.locator(f"input[name='chkInfraItem'][title='SEINFRA/{sigla}']")
    try:
        await radio.first.wait_for(state="attached", timeout=20000)
    except Exception:
        raise RuntimeError(f"unidade SEINFRA/{sigla} não disponível para o usuário")
    valor = await radio.first.get_attribute("value")
    try:
        await radio.first.check(force=True)
    except Exception:
        await radio.first.evaluate("el => el.click()")
    await page.wait_for_load_state("domcontentloaded")
    await page.wait_for_timeout(3000)

    if "trocar_unidade" in page.url:
        await page.goto(sei_base() + "/sei/", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)

    nova = await _unidade_atual(page)
    if nova and nova.upper() != sigla.upper():
        raise RuntimeError(f"troca falhou: unidade atual é {nova!r}, esperado {sigla!r}")
    log.info("unidade trocada para SEINFRA/%s (id %s, url unit id=%s)",
             sigla, valor, _id_unidade_url(page.url))
    return int(valor)


def _id_unidade_url(url: str) -> int:
    m = re.search(r"infra_unidade_atual=(\d+)", url or "")
    return int(m.group(1)) if m else 0


async def abrir_controle(page) -> None:
    """Abre a tela 'Controle de Processos' da unidade atual pelo menu."""
    try:
        if await page.locator("#linkMenu6").count():
            await page.locator("#linkMenu6").click()
            await page.wait_for_load_state("domcontentloaded")
            await page.wait_for_timeout(1800)
            return
    except Exception:
        pass
    # fallback: link da barra superior
    try:
        onclick = await page.locator("#lnkControleProcessos").first.get_attribute("onclick")
        href = _extrair_href_onclick(onclick)
        if href:
            await page.goto(urljoin(sei_base() + "/sei/", href), wait_until="domcontentloaded")
            await page.wait_for_timeout(1800)
            return
    except Exception:
        pass
    raise RuntimeError("não consegui abrir a tela de Controle de Processos")


async def coletar_controle(page, unidade: str, max_paginas: int) -> list[dict]:
    """Lê a lista de processos do Controle de Processos da unidade atual.

    Campos ricos: nº, tipo, especificação, prioridade (Alta/Média), marcadores,
    Controle de Prazo (dias/atraso), Para Devolver, responsável e link.
    """
    await abrir_controle(page)
    resultados: dict[str, dict] = {}
    pagina = 1
    anterior_prim = None

    while True:
        tabela = page.locator("#tblProcessosDetalhado")
        if not await tabela.count():
            tabela = page.locator("table.tabelaControle")
        if not await tabela.count():
            log.warning("unidade %s: sem tabela de controle na página %d", unidade, pagina)
            break

        linhas = tabela.locator("tr[id^='P']")
        n = await linhas.count()
        novas = 0
        prim_num = None
        for i in range(n):
            r = await _parse_linha_controle(linhas.nth(i), unidade)
            if not r or not r["numero"]:
                continue
            if prim_num is None:
                prim_num = r["numero"]
            if r["numero"] not in resultados:
                resultados[r["numero"]] = r
                novas += 1

        if pagina == 1:
            html = await page.content()
            (DEBUG_DIR / f"controle_{unidade}_p1.html").write_text(
                html, encoding="utf-8", errors="replace"
            )

        log.info("unidade %s: página %d -> %d linhas (%d novas) | 1º %s",
                 unidade, pagina, n, novas, prim_num)

        if prim_num is not None and prim_num == anterior_prim:
            log.warning("unidade %s: página não avançou (1º %s repetido)", unidade, prim_num)
            break
        anterior_prim = prim_num or anterior_prim

        if pagina >= max_paginas or not await _proxima_pagina_controle(page):
            break
        pagina += 1

    return list(resultados.values())


async def _proxima_pagina_controle(page) -> bool:
    """Pagina no Controle de Processos via link 'Próxima' (Ajax)."""
    links = [
        page.locator("#lnkDetalhadoProximaPaginaSuperior"),
        page.locator("#lnkDetalhadoProximaPaginaInferior"),
    ]
    for loc in links:
        try:
            if await loc.count() and await loc.first.is_visible():
                await loc.first.click()
                await page.wait_for_timeout(2200)
                return True
        except Exception as exc:
            log.warning("falha ao paginar: %s", exc)
            return False
    # fallback: último (botão paginação clássico) sem mudar
    return False


async def _parse_linha_controle(linha, unidade: str) -> dict | None:
    chk = linha.locator("input.infraCheckboxInput")
    if not await chk.count():
        return None

    numero = (await chk.first.get_attribute("title") or "").strip()
    if not numero or not NUMERO_SEI_CONTROLE.fullmatch(numero):
        # confere no texto da célula Processo (fallback)
        texto = await linha.inner_text()
        m = NUMERO_SEI_CONTROLE.search(texto)
        if m:
            numero = m.group(0)
        else:
            return None
    id_proc = (await chk.first.get_attribute("value") or "").strip()
    chk_aria = (await chk.first.get_attribute("aria-label") or "").strip()

    contexto = {
        "numero": numero,
        "id_procedimento": id_proc,
        "unidade_origem": unidade,
        "tipo_processo": None,
        "especificacao": None,
        "prioridade": 0,
        "prioridade_nivel": None,
        "marcadores": [],
        "controle_prazo": None,
        "prazo_vencimento": None,
        "dias_atraso": 0,
        "para_devolver": None,
        "responsavel": None,
        "interessados": [],
        "link_sei": None,
        "data_autuacao": None,
        "ultima_movimentacao": None,
        "data_conclusao": None,
    }

    tds = linha.locator("td")
    nt = await tds.count()
    for i in range(nt):
        td = tds.nth(i)
        try:
            label = await td.get_attribute("data-label")
            txt = (await td.inner_text()).strip()
        except Exception:
            continue

        if label == "Processo":
            link = td.locator("a[href]").first
            if await link.count():
                href = await link.get_attribute("href")
                if href:
                    contexto["link_sei"] = urljoin(sei_base() + "/sei/", href)
                aria = await link.get_attribute("aria-label")
                tipo, esp = _desdobra_aria(aria or "")
                contexto["tipo_processo"] = tipo or contexto["tipo_processo"]
                contexto["especificacao"] = esp or contexto["especificacao"]
                if not contexto["numero"]:
                    m = NUMERO_SEI_CONTROLE.search(txt)
                    if m:
                        contexto["numero"] = m.group(0)
        elif label == "Atribuição":
            atr = td.locator("a[title]").first
            if await atr.count():
                t = await atr.get_attribute("title")
                if t and "atribu" in t.lower():
                    contexto["responsavel"] = re.sub(
                        r"(?i)atribu[íi]do para\s*:?\s*", "", t
                    ).strip() or t
            contexto["responsavel"] = contexto["responsavel"] or (texto_sigla_atribuicao(txt) or None)
        elif label == "Tipo":
            if txt and txt not in ("&nbsp;", ""):
                contexto["tipo_processo"] = contexto["tipo_processo"] or txt
        elif label == "Interessados":
            nomes = await td.locator(".divRotuloItemCelula").all_inner_texts()
            contexto["interessados"] = [n.strip() for n in nomes if n.strip()]
        elif label and "\u00a0" in label:
            # célula de ícones de status (prioridade, marcadores, prazos)
            await _parse_status_icons(td, contexto)
        else:
            # célula numérica de prazos (sem data-label)
            m = re.search(r"^-?\d+$", txt)
            if m and contexto["dias_atraso"] == 0:
                v = int(m.group(0))
                contexto["dias_atraso"] = -v if v < 0 else 0
                if v < 0 and not contexto["controle_prazo"]:
                    contexto["controle_prazo"] = f"atrasado {-v} dia(s)"

    # tipo/esp fallback via aria do checkbox
    if not contexto["tipo_processo"]:
        tipo, esp = _desdobra_aria_check(chk_aria)
        contexto["tipo_processo"] = tipo or None
        contexto["especificacao"] = esp or contexto["especificacao"]

    contexto["marcadores"] = list(dict.fromkeys(contexto["marcadores"]))
    return contexto


def _desdobra_aria(aria: str) -> tuple[str, str]:
    if not aria:
        return "", ""
    partes = [p.strip() for p in aria.split("/")]
    if len(partes) >= 2:
        return partes[0], " / ".join(partes[1:])
    return partes[0] if partes else "", ""


def _desdobra_aria_check(aria: str) -> tuple[str, str]:
    """'Não recebido / Tipo X / Especificação Y' → (X, Y)."""
    if not aria:
        return "", ""
    partes = [p.strip() for p in aria.split("/")]
    partes = [p for p in partes if p]
    if partes and partes[0].lower().startswith("não recebido"):
        partes = partes[1:]
    tipo = ""
    esp = ""
    if partes and partes[0].replace("Tipo", "").strip() != partes[0]:
        tipo = partes[0].split("Especificação", 1)[0].replace("Tipo", "").strip()
        resto = partes[0].split("Especificação", 1)
        if len(resto) > 1 and resto[1].strip():
            esp = resto[1].strip()
    elif partes:
        tipo = partes[0].replace("Tipo", "").strip()
        if len(partes) > 1 and not partes[1].replace("Especificação", "").strip().startswith(partes[0][:6]):
            candidato = partes[1].replace("Especificação", "").strip()
            if candidato and not candidato.lower().startswith(("memorando", "aguardando")):
                esp = candidato
    return tipo, esp


async def _parse_status_icons(td, contexto: dict) -> None:
    els = td.locator("[aria-label]")
    n = await els.count()
    for k in range(n):
        aria = (await els.nth(k).get_attribute("aria-label") or "").strip()
        if not aria:
            continue
        if aria.startswith("Prioritário /"):
            nivel = aria.split("/", 1)[1].strip()
            contexto["prioridade"] = 1
            contexto["prioridade_nivel"] = nivel
        elif aria.startswith("Marcador /"):
            nome = aria.split("/", 1)[1].strip()
            nome = nome.split("/", 1)[0].strip()
            if nome:
                contexto["marcadores"].append(nome)
        elif aria.startswith("Controle de Prazo /"):
            contexto["controle_prazo"] = aria.split("/", 1)[1].strip()
            m_data = DATA_BR.search(aria)
            if m_data:
                contexto["prazo_vencimento"] = f"{m_data.group(3)}-{m_data.group(2)}-{m_data.group(1)}"
            m_atraso = re.search(r"atrasado\s+(\d+)\s+dias", aria, re.I)
            if m_atraso:
                contexto["dias_atraso"] = max(contexto["dias_atraso"], int(m_atraso.group(1)))
        elif aria.startswith("Para Devolver /"):
            contexto["para_devolver"] = aria.split("/", 1)[1].strip()

    # Peticionamento eletrônico: datas vêm no tooltip do <img> (onmouseover),
    # "Processo Novo: DD/MM/YYYY" (autuação) e "Intercorrente: DD/MM/YYYY"
    # (última intercorrência = movimento externo no processo).
    imgs = td.locator("img[onmouseover]")
    ni = await imgs.count()
    for k in range(ni):
        ov = (await imgs.nth(k).get_attribute("onmouseover") or "").replace("&quot;", '"')
        m = re.search(r"Processo Novo:\s*(\d{2}/\d{2}/\d{4})", ov)
        if m and not contexto["data_autuacao"]:
            contexto["data_autuacao"] = _iso_br(m.group(1))
        m = re.search(r"Intercorrente:\s*(\d{2}/\d{2}/\d{4})", ov)
        if m and not contexto["ultima_movimentacao"]:
            contexto["ultima_movimentacao"] = _iso_br(m.group(1))


def _iso_br(dd_mm_aaaa: str) -> str:
    d, m, a = dd_mm_aaaa.split("/")
    return f"{a}-{m}-{d}"


def texto_sigla_atribuicao(txt: str) -> str | None:
    t = (txt or "").replace("&nbsp;", "").strip()
    return t or None


# ---------------------------------------------------------------------------
# Painel de Controle (cartões + tabelas por unidade)
# ---------------------------------------------------------------------------

async def coletar_painel(page, unidade: str, dump: bool = True) -> dict:
    """Extrai os cartões e tabelas do Painel de Controle da unidade atual."""
    onclick = None
    try:
        onclick = await page.locator("#linkMenu19").first.get_attribute("onclick")
    except Exception:
        pass
    href = None
    if onclick:
        m = re.search(r"['\"]([^'\"]+)['\"]", onclick)
        href = m.group(1) if m else None
    if not href:
        try:
            href = await page.locator("#linkMenu19").first.get_attribute("href")
        except Exception:
            href = None
    if not href:
        try:
            href = await page.locator("#lnkPainelControle").first.get_attribute("href")
        except Exception:
            href = None
    if not href:
        raise RuntimeError("não encontrei o link do Painel de Controle")

    await page.goto(urljoin(sei_base() + "/sei/", href), wait_until="domcontentloaded")
    await page.wait_for_timeout(5000)

    if dump:
        html = await page.content()
        (DEBUG_DIR / f"painel_{unidade}.html").write_text(
            html, encoding="utf-8", errors="replace"
        )

    cartoes: dict[str, int | None] = {}
    cards = page.locator("a.card-block")
    ncards = await cards.count()
    for i in range(ncards):
        card = cards.nth(i)
        try:
            titulo = await card.get_attribute("title") or ""
            txt = (await card.inner_text()).strip()
        except Exception:
            continue
        partes = txt.split()
        if len(partes) >= 2 and partes[0].isalpha() and partes[-1].isdigit():
            chave = _normaliza_card(partes[0] if len(partes) == 2 else " ".join(partes[:-1]))
            valor = int(partes[-1])
            cartoes[chave] = valor
        elif titulo and partes and partes[-1].isdigit():
            chave = _normaliza_card(" ".join(partes[:-1]))
            cartoes[chave] = int(partes[-1])

    tabelas = await _parse_tabelas_painel(page)
    log.info("unidade %s: painel carregado (cartões=%s)", unidade, cartoes or "vazio")
    return {"cartoes": cartoes, "tabelas": tabelas}


def _normaliza_card(nome: str) -> str:
    mapa = {
        "Total": "total", "Recebidos": "recebidos", "Gerados": "gerados",
        "Nao": "nao_visualizados", "Nao_Visualizados": "nao_visualizados",
        "Atribuidos": "atribuidos_a_mim", "Atribuidos_a_mim": "atribuidos_a_mim",
        "Sem": "sem_acompanhamento", "Sem_Acompanhamento": "sem_acompanhamento",
        "Alterados": "alterados",
        "Prioritarios": "prioritarios",
        "Reaberturas": "reaberturas", "Reaberturas_Programadas": "reaberturas",
    }
    sem_acento = unicodedata.normalize("NFD", nome)
    chave = "".join(c for c in sem_acento if unicodedata.category(c) != "Mn")
    chave_limpa = chave.strip().replace("  ", " ").replace(" ", "_")
    if chave_limpa in mapa:
        return mapa[chave_limpa]
    if chave_limpa.startswith("Nao"):
        return "nao_visualizados"
    if chave_limpa.startswith("Atribuidos"):
        return "atribuidos_a_mim"
    if chave_limpa.startswith("Sem"):
        return "sem_acompanhamento"
    if chave_limpa.startswith("Priorit"):
        return "prioritarios"
    if chave_limpa.startswith("Reabert"):
        return "reaberturas"
    return chave_limpa.lower() or ""


async def _parse_tabelas_painel(page) -> dict:
    saida: dict[str, list] = {"prazos": [], "retornos": [], "blocos": [], "grupos": [], "tipos": []}
    tabelas = page.locator("table")
    n = await tabelas.count()
    for i in range(n):
        tbl = tabelas.nth(i)
        try:
            caption = (await tbl.locator("caption .divCaptionLeft").first.inner_text()).strip()
        except Exception:
            caption = ""
        if not caption:
            try:
                caption = (await tbl.locator("caption").first.inner_text()).strip()
            except Exception:
                continue
        caption = caption.replace(":", "").strip()
        if not caption:
            continue
        chave = None
        for k, alias in (
            ("grupos", ("grupo",)),
            ("blocos", ("bloco",)),
            ("prazos", ("controle", "prazo")),
            ("retornos", ("retorno",)),
            ("tipos", ("tipo", "aberto")),
        ):
            if any(a in caption.lower() for a in alias):
                chave = k
                break
        if chave is None:
            continue
        linhas = await _linhas_tabela_painel(tbl)
        if chave in ("blocos", "grupos"):
            for ln in linhas:
                if "processos" in ln:
                    ln["blocos"] = ln.pop("processos")
                if "alterados" in ln:
                    ln["documentos"] = ln.pop("alterados")
                if "sem_assinatura" not in ln and "documentos" in ln:
                    ln["sem_assinatura"] = 0
        if linhas:
            saida[chave] = saida[chave] + linhas
    return saida


async def _linhas_tabela_painel(tbl) -> list[dict]:
    linhas = []
    trs = tbl.locator("tr")
    n = await trs.count()
    for i in range(n):
        tr = trs.nth(i)
        try:
            rotulo_el = tr.locator("span.celulaComImagem").first
            if not await rotulo_el.count():
                rotulo_el = await _primeira_td_visivel(tr)
            rotulo = (await rotulo_el.inner_text()).strip()
        except Exception:
            rotulo = ""
        if not rotulo:
            continue
        vals: list[int] = []
        num = tr.locator("a[aria-label]")
        m = await num.count()
        for j in range(m):
            aria = (await num.nth(j).get_attribute("aria-label")) or ""
            g = re.match(r"^(\d+)", aria.strip())
            if g:
                vals.append(int(g.group(1)))
        if vals:
            linha: dict = {"tipo": rotulo}
            nomes = ["processos", "alterados", "documentos", "sem_assinatura"]
            for k, v in enumerate(vals):
                linha[nomes[k] if k < 4 else f"col{k + 1}"] = v
            linhas.append(linha)
    return linhas


async def _primeira_td_visivel(tr):
    """Primeira célula <td> que não esteja oculta (ignora checkbox display:none)."""
    tds = tr.locator("td")
    n = await tds.count()
    for j in range(n):
        caixa = tds.nth(j)
        try:
            style = (await caixa.get_attribute("style") or "").lower()
            if "display:none" in style or "visibility:hidden" in style:
                continue
        except Exception:
            pass
        return caixa
    return tds.first


# ---------------------------------------------------------------------------
# Estatísticas da Unidade (menu Estatísticas > Unidade, linkMenu7/linkMenu8)
# ---------------------------------------------------------------------------

TABELAS_ESTATISTICAS = {
    "Processos gerados no período": "processos_gerados",
    "Processos com tramitação no período": "processos_tramitacao",
    "Processos com andamento fechado na unidade ao final do período": "processos_fechados",
    "Processos com andamento aberto na unidade ao final do período": "processos_abertos",
    "Tempos médios de tramitação no período": "tempos_medios",
    "Documentos gerados no período": "documentos_gerados",
    "Documentos externos no período": "documentos_externos",
}

ABREV_MESES = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}


async def coletar_estatisticas(page, unidade: str, de: str, ate: str, dump: bool = True) -> dict:
    """Abre Estatísticas > Unidade, preenche o período e extrai as 7 tabelas.

    de/ate em formato DD/MM/AAAA. Retorna lista de registros normalizados:
    {tabela, tipo, mes (YYYY-MM | "__total__" | None), valor}.
    """
    try:
        await page.locator("#linkMenu7").first.evaluate("(el) => el.click()")
        await page.wait_for_timeout(800)
        await page.locator("#linkMenu8").first.evaluate("(el) => el.click()")
        await page.wait_for_timeout(5000)
    except Exception as exc:
        raise RuntimeError(f"não consegui abrir Estatísticas da Unidade: {exc}")

    try:
        await page.locator("#txtPeriodoDe").first.fill(de)
        await page.locator("#txtPeriodoA").first.fill(ate)
        await page.locator("#sbmPesquisar").first.click()
        await page.wait_for_timeout(12000)
    except Exception as exc:
        raise RuntimeError(f"falha ao preencher período ({de} a {ate}) e pesquisar: {exc}")

    html = await page.content()
    if dump:
        ano = de[-4:]
        (DEBUG_DIR / f"estat_{unidade}_{ano}.html").write_text(html, encoding="utf-8", errors="replace")

    registros = _parse_html_estatisticas(html)
    if not registros:
        # falhou silenciosamente (período inválido, tela não renderizou): confere aviso
        texto = re.sub(r"<[^>]+>", " ", html)
        texto = re.sub(r"\s+", " ", texto)
        aviso = re.search(r"não pode ser superior a\s*([^\.]{0,40})", texto)
        if aviso:
            raise RuntimeError(f"período rejeitado pelo SEI: {aviso.group(0).strip()}")
    log.info("unidade %s: estatísticas carregadas (%s registros)", unidade, len(registros))
    return {"registros": registros}


def _parse_html_estatisticas(html: str) -> list[dict]:
    """Parseia todas as tabelas de estatísticas de um dump HTML (regex, testável off-line)."""
    saida: list[dict] = []
    for summary, chave in TABELAS_ESTATISTICAS.items():
        # cada tabela começa com <table ... summary="...">
        padrao = re.compile(
            r'<table[^>]*summary="Tabela de\s+' + re.escape(summary) + r'"[^>]*>(.*?)</table>',
            re.S,
        )
        for m in padrao.finditer(html):
            seg = m.group(1)
            for linha in _linhas_tabela_estat(seg, chave):
                saida.append(linha)
    return saida


def _linhas_tabela_estat(seg: str, chave: str) -> list[dict]:
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", seg, re.S)
    headers = [t for t in trs if "<th" in t]
    dados = [t for t in trs if "<th" not in t and "<td" in t]

    mensal = len(headers) >= 2  # tabelas mensais têm linha de anos + linha de meses
    colunas_mes: list[str] = []
    eh_total = False
    if mensal:
        colunas_mes, eh_total = _colunas_mensais(headers)

    linha: list[dict] = []
    for tr in dados:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tr, re.S)
        if not tds:
            continue
        tipo = _texto_limpo(tds[0])
        if not tipo:
            continue
        if tipo.upper().startswith("TOTAL"):
            continue
        if not mensal:
            valor = _valor_celula(tds[1]) if len(tds) >= 2 else 0
            detalhe = _texto_limpo(tds[1]) if len(tds) >= 2 and not isinstance(valor, int) else None
            if isinstance(valor, str) and tempo_para_dias(valor):
                valor = tempo_para_dias(valor)
                detalhe = _texto_limpo(tds[1]) if len(tds) >= 2 else None
            linha.append({"tabela": chave, "tipo": tipo, "mes": None, "valor": valor, "detalhe": detalhe})
            continue
        for idx, mes in enumerate(colunas_mes):
            valor = _valor_celula(tds[idx + 1]) if idx + 1 < len(tds) else 0
            linha.append({"tabela": chave, "tipo": tipo, "mes": mes, "valor": valor, "detalhe": None})
        if eh_total and len(tds) >= len(colunas_mes) + 2:
            valor_total = _valor_celula(tds[len(colunas_mes) + 1])
            linha.append({
                "tabela": chave, "tipo": tipo, "mes": "__total__",
                "valor": valor_total,
                "detalhe": None,
            })
    return linha


def _colunas_mensais(headers: list[str]) -> tuple[list[str], bool]:
    """Retorna (lista [YYYY-MM, ...], tem_coluna_total) a partir das 2 linhas de header."""
    anos: list[tuple[int, int]] = []  # (colspan, ano)
    for span in re.finditer(r'<th[^>]*colspan="(\d+)"[^>]*>\s*(\d{4})\s*</th>', headers[0]):
        anos.append((int(span.group(1)), int(span.group(2))))
    meses: list[int] = []
    for mes in re.finditer(r"<th[^>]*>\s*(Jan|Fev|Mar|Abr|Mai|Jun|Jul|Ago|Set|Out|Nov|Dez)\s*</th>", headers[1], re.I):
        meses.append(ABREV_MESES[mes.group(1).lower()])
    eh_total = bool(re.search(r"<th[^>]*rowspan=\"2\"[^>]*>\s*&nbsp;\s*</th>", headers[0], re.I))
    colunas: list[str] = []
    rel = 0
    for colspan, ano in anos:
        for _i in range(colspan):
            mes = meses[rel] if rel < len(meses) else 0
            if mes:
                colunas.append(f"{ano}-{mes:02d}")
            rel += 1
    return colunas, eh_total


def _texto_limpo(celula: str) -> str:
    txt = re.sub(r"<[^>]+>", "", celula)
    txt = txt.replace("&nbsp;", " ").replace("&amp;", "&")
    return " ".join(txt.split())


def _valor_celula(celula: str):
    m = re.search(r">\s*([\d.,]+)\s*</a>", celula)
    if m:
        num = m.group(1).replace(".", "").replace(",", ".")
        try:
            return int(float(num))
        except ValueError:
            return 0
    txt = _texto_limpo(celula)
    if txt.isdigit():
        return int(txt)
    return txt if txt else 0


def tempo_para_dias(detalhe) -> float | None:
    """Converte '15d 3h 52m 5s' (tempos médios do SEI) em dias. Retorna None se vazio."""
    if not detalhe or not isinstance(detalhe, str):
        return None
    dx = re.search(r"(\d+)d", detalhe)
    hx = re.search(r"(\d+)h", detalhe)
    mx = re.search(r"(\d+)m", detalhe)
    sx = re.search(r"(\d+)s", detalhe)
    if not (dx or hx or mx or sx):
        return None
    dias = int(dx.group(1)) if dx else 0
    dias += (int(hx.group(1)) if hx else 0) / 24
    dias += (int(mx.group(1)) if mx else 0) / (24 * 60)
    dias += (int(sx.group(1)) if sx else 0) / (24 * 3600)
    return round(dias, 3)