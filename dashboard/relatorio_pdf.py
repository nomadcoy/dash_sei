from __future__ import annotations











"""Relatório Gerencial de Transição de Governo — HTML e PDF.











Reaproveita o motor de PDF do boletim (Playwright/Chromium) e seus helpers de





imagem, mudando o nome e ampliando a estrutura: panorama, volume de trabalho,





o que é a STIM, análise por diretoria e síntese para a transição.





"""











import base64





import re





from datetime import date











import pandas as pd











from cfg import cor_unidade, nome_unidade





from dashboard.boletim_pdf import _logo_stim, _img_serie, gerar_pdf





from dashboard.relatorio_textos import (





    CREDITO,





    _fmt,





    analise_diretoria,





    conclusao,





    destaques,





    fluxos_por_tipo,





    metodologia,





    o_que_e_a_stim,





    rotulo,





    sintese_transicao,





)











TITULO = "Relatório Gerencial de Transição de Governo"





SUBTITULO = "Transporte Coletivo Intermunicipal e Metropolitano — SEINFRA / STIM"

















def _md(txt: str) -> str:





    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", str(txt))

















def _img_anual(anual: pd.DataFrame, unidades: list[str]) -> str:





    """Barras agrupadas por ano (uma série por unidade)."""





    if anual is None or anual.empty:





        return ""





    piv = (





        anual.pivot(index="ano", columns="unidade", values="quantidade")





        .reindex(columns=[u for u in unidades])





        .fillna(0)





    )





    import matplotlib  # noqa: PLC0415











    matplotlib.use("Agg")





    import matplotlib.pyplot as plt  # noqa: PLC0415











    cores = [cor_unidade(u) for u in piv.columns]





    fig, ax = plt.subplots(figsize=(10.5, 1.7))





    piv.plot(kind="bar", ax=ax, color=cores, width=0.78, rot=0)





    ax.set_xlabel("")





    ax.set_ylabel("documentos gerados")





    ax.grid(axis="y", linestyle=":", alpha=0.5)





    ax.set_axisbelow(True)





    for lbl in ax.get_xticklabels():





        lbl.set_fontsize(10)





    ax.legend(title="", fontsize=9, frameon=False)





    for spine in ("top", "right"):





        ax.spines[spine].set_visible(False)





    plt.tight_layout()





    import io











    buf = io.BytesIO()





    plt.savefig(buf, format="png", dpi=140)





    plt.close()





    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")

















def _card(rotulo_txt: str, valor: str) -> str:





    return (





        f"<div class='card'><div class='card-r'>{rotulo_txt}</div>"





        f"<div class='card-v'>{valor}</div></div>"





    )

















def _cards(itens: list[tuple[str, str]]) -> str:





    return "<div class='cards'>" + "".join(_card(r, v) for r, v in itens) + "</div>"

















def _tabela(df: pd.DataFrame, cols: list[str] | None = None) -> str:





    if df is None or df.empty:





        return "<p class='vazio'>Sem dados.</p>"





    d = df[cols] if cols else df





    th = "".join(f"<th>{c}</th>" for c in d.columns)





    linhas = ""





    for _, r in d.iterrows():





        linhas += "<tr>" + "".join(f"<td>{r[c]}</td>" for c in d.columns) + "</tr>"





    return f"<table><thead><tr>{th}</tr></thead><tbody>{linhas}</tbody></table>"

















def _bloco_diretoria(sigla: str, dados: dict) -> str:





    u = dados["por_unidade"][sigla]





    cor = cor_unidade(sigla)





    paragrafos = "".join(f"<p>{_md(p)}</p>" for p in analise_diretoria(sigla, dados))





    cards = _cards([





        ("Documentos", _fmt(u["docs_total"])),





        ("Processos gerados", _fmt(u["prc_total"])),





        ("Documentos externos", _fmt(u["ext_total"])),





        ("Processos (retrato)", _fmt(u["n_proc"])),





    ])





    top_docs = u["top_docs"].head(8).rename(





        columns={"tipo": "Tipo de documento", "total": "Quantidade"}





    )





    tab_docs = _tabela(top_docs)





    eixos = u["eixos"].rename(columns={"eixo": "Eixo (retrato atual)", "processos": "Processos"})





    tab_eixos = _tabela(eixos.head(8))





    img = _img_serie(u["serie_mensal"], [sigla], altura=1.7) if not u["serie_mensal"].empty else ""





    img_html = f"<img class='grafico' src='{img}'>" if img else ""





    return f"""





    <div class="secao">





      <h2 style="border-color:{cor};color:{cor}">{sigla} — {nome_unidade(sigla)}</h2>





      {cards}





      {paragrafos}





      <h3>Documentos mais frequentes (período)</h3>





      {tab_docs}





      {img_html}





      <h3>Processos por eixo (retrato atual do SEI)</h3>





      {tab_eixos if not u['eixos'].empty else "<p class='vazio'>Sem eixos classificados.</p>"}





    </div>





    """

















def _bloco_fluxos() -> str:





    fluxos = fluxos_por_tipo()





    if not fluxos:





        return ""





    linhas = ""





    for f in fluxos:





        etapas = "<br>".join(f"• {_md(e)}" for e in (f.get("etapas") or []))





        linhas += (





            f"<tr><td><b>{f.get('nome','')}</b><br>"





            f"<span class='sig'>{f.get('diretoria','')}</span></td>"





            f"<td>{_md(f.get('entrada',''))}</td>"





            f"<td>{etapas}</td>"





            f"<td>{_md(f.get('saida',''))}</td></tr>"





        )





    return (





        "<table><thead><tr><th>Fluxo</th><th>Entrada</th><th>Etapas</th>"





        f"<th>Saída</th></tr></thead><tbody>{linhas}</tbody></table>"





    )

















def _ano_corrente(dados: dict) -> tuple[str, list[tuple], tuple[int, int, int]]:





    """Números do ano mais recente do recorte, por unidade (parcial se for o atual)."""





    ano = dados["anos"][-1] if dados["anos"] else ""











    def _map(tabela: str) -> dict:





        s = dados["anual"][tabela]





        s = s[s["ano"] == ano]





        return {u: int(round(v)) for u, v in zip(s["unidade"], s["quantidade"])}











    d, p, e = _map("doc"), _map("prc"), _map("ext")





    linhas = [(u, d.get(u, 0), p.get(u, 0), e.get(u, 0)) for u in dados["unidades"]]





    return ano, linhas, (sum(d.values()), sum(p.values()), sum(e.values()))

















def _foco_ano_corrente(dados: dict) -> str:





    ano, linhas, (td, tp, te) = _ano_corrente(dados)





    if not ano:





        return ""





    parcial = ano == dados["ate"][:4]





    ref = f"de janeiro até {rotulo(dados['ate'])}" if parcial else "no ano"





    corpo = "".join(





        f"<tr><td><b>{u}</b></td><td>{_fmt(d)}</td><td>{_fmt(p)}</td>"





        f"<td>{_fmt(e)}</td></tr>"





        for u, d, p, e in linhas





    )





    nota = (





        " O ano corrente está em curso: os números refletem apenas o que foi "





        "registrado até a data da extração."





        if parcial





        else ""





    )





    return (





        f"<div class='secao'><h2>Foco no ano corrente — {ano}</h2>"





        f"<p>Produção {ref}, por diretoria.{nota}</p>"





        + _cards([





            ("Documentos em " + ano, _fmt(td)),





            ("Processos em " + ano, _fmt(tp)),





            ("Docs externos em " + ano, _fmt(te)),





        ])





        + "<table><tr><th>Unidade</th><th>Documentos</th><th>Processos</th>"





          "<th>Docs externos</th></tr>"





        + corpo





        + f"<tr><td><b>Total</b></td><td><b>{_fmt(td)}</b></td>"





          f"<td><b>{_fmt(tp)}</b></td><td><b>{_fmt(te)}</b></td></tr></table>"





          "</div>"





    )

















def _retrato_tabela(dados: dict) -> str:





    linhas = ""





    for s in dados["unidades"]:





        p = dados["por_unidade"][s]["painel"] or {}





        linhas += (





            f"<tr><td><b>{s}</b></td>"





            f"<td>{_fmt(p.get('total') or 0)}</td>"





            f"<td>{_fmt(p.get('recebidos') or 0)}</td>"





            f"<td>{_fmt(p.get('gerados') or 0)}</td>"





            f"<td>{_fmt(p.get('sem_acompanhamento') or 0)}</td>"





            f"<td>{_fmt(dados['por_unidade'][s]['n_proc'])}</td>"





            f"<td>{_fmt(dados['por_unidade'][s]['criticos'])}</td>"





            f"<td>{_fmt(dados['por_unidade'][s]['sem_resp'])}</td></tr>"





        )





    return (





        "<table><thead><tr><th>Unidade</th><th>Total (SEI)</th><th>Recebidos</th>"





        "<th>Gerados</th><th>Sem acompanhamento</th><th>No controle</th>"





        "<th>Críticos</th><th>Sem responsável</th></tr></thead>"





        f"<tbody>{linhas}</tbody></table>"





    )

















_CSS = """





@page { size: A4; margin: 16mm 14mm; }





* { box-sizing: border-box; }





body { font-family: Arial, Helvetica, sans-serif; color: #0f172a; font-size: 12px; line-height: 1.5; }





h1 { color: #1D4E89; font-size: 22px; margin: 0 0 4px; }





h2 { color: #1D4E89; font-size: 16px; border-bottom: 2px solid #1D4E89; padding-bottom: 4px; margin: 14px 0 8px; }





h3 { font-size: 13px; margin: 10px 0 5px; color: #334155; }





p { margin: 5px 0; }





.secao { margin-top: 14px; }





.secao:first-of-type { margin-top: 6px; }





h2, h3 { page-break-after: avoid; break-after: avoid; }





.cards, img.grafico, .cabecalho, .destaque { page-break-inside: avoid; break-inside: avoid; }





table { page-break-inside: auto; }





thead { display: table-header-group; }





tr { page-break-inside: auto; break-inside: auto; }





.credito { font-size: 10px; color: #475569; margin: 6px 0 2px; }





.conclusao { background: #f1f5f9; border: 1px solid #d6dee8; border-left: 4px solid #1D4E89;





             border-radius: 0 10px 10px 0; padding: 12px 16px; margin-top: 10px; }





.cabecalho { display: flex; align-items: center; gap: 16px; background: #1D4E89; color: #fff; border-radius: 10px; padding: 16px 18px; margin-bottom: 14px; }





.logo { height: 58px; width: auto; border-radius: 8px; background: #fff; padding: 4px; }





.cabecalho-titulos { flex: 1; }





.cabecalho-org { font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; opacity: .85; }





.cabecalho-titulo { font-size: 19px; font-weight: 800; margin: 3px 0; }





.cabecalho-sub { font-size: 10.5px; opacity: .92; }





.cabecalho-gerado { text-align: right; font-size: 9px; line-height: 1.5; opacity: .95; border-left: 1px solid rgba(255,255,255,.35); padding-left: 14px; }





.periodo { background: #eef2f7; border: 1px solid #d6dee8; border-radius: 6px; padding: 6px 10px; font-size: 11px; margin-bottom: 12px; }





.cards { display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 12px; }





.card { flex: 1 1 130px; border: 1px solid #e5eaf1; border-radius: 10px; padding: 7px 10px; }





.card-r { font-size: 9.5px; color: #334155; text-transform: uppercase; letter-spacing: .04em; font-weight: 700; }





.card-v { font-size: 17px; font-weight: 800; color: #0f172a; margin-top: 2px; }





table { border-collapse: collapse; width: 100%; margin: 6px 0 8px; }





th, td { border: 1px solid #e2e8f0; padding: 4px 8px; text-align: left; font-size: 10.5px; vertical-align: top; }





th { background: #1D4E89; color: #fff; font-weight: 700; }





tr:nth-child(even) td { background: #f8fafc; }





img.grafico { width: 100%; border: 1px solid #e5eaf1; border-radius: 8px; margin: 4px 0 2px; }





.destaque { background: #f8fafc; border-left: 4px solid #1D4E89; border-radius: 0 8px 8px 0; padding: 7px 12px; margin: 5px 0; font-size: 11.5px; }





.vazio { color: #64748b; font-style: italic; }





.sig { color: #64748b; font-size: 9px; }





.rodape { margin-top: 18px; font-size: 9px; color: #64748b; border-top: 1px solid #e5eaf1; padding-top: 6px; }





"""

















def html_relatorio(dados: dict, incluir_fluxos: bool = True) -> str:





    de, ate = dados["de"], dados["ate"]





    k = dados["kpis"]





    logo = _logo_stim()











    resumo = "<div class='secao'>" + f"<h2>Sumário executivo</h2>" + _cards([





        ("Documentos (sem autom.)", _fmt(k["doc_sem_auto"])),





        ("Documentos (total SEI)", _fmt(k["doc_com_auto"])),





        ("Processos gerados", _fmt(k["proc"])),





        ("Documentos externos", _fmt(k["ext"])),





        ("Tipos de documento", _fmt(k["n_tipos"])),





    ])





    resumo += "".join(f"<div class='destaque'>{_md(d)}</div>" for d in destaques(dados)) + "</div>"











    metod = "<div class='secao'><h2>Como ler este relatório</h2>"





    metod += "".join(f"<p>{_md(p)}</p>" for p in metodologia(dados)) + "</div>"











    stim = "<div class='secao'><h2>O que é a STIM</h2>"





    stim += "".join(f"<p>{_md(p)}</p>" for p in o_que_e_a_stim())





    stim += "</div>"











    panorama = "<div class='secao'><h2>Panorama da produção (2024–2026)</h2>"





    panorama += "<h3>Comparativo por diretoria (período)</h3>"





    comp = dados["comparativo"].rename(columns={





        "Unidade": "Unidade", "Documentos gerados": "Documentos gerados",





        "Processos gerados": "Processos gerados", "Documentos externos": "Documentos externos",





        "Tipos de doc.": "Tipos de documento",





    })





    panorama += _tabela(comp)





    img_anual = _img_anual(dados["anual"]["doc"], dados["unidades"])





    if img_anual:





        panorama += "<h3>Documentos gerados por ano e por diretoria</h3>"





        panorama += f"<img class='grafico' src='{img_anual}'>"





    if not dados["serie_mensal"].empty:





        img_mes = _img_serie(dados["serie_mensal"], dados["unidades"])





        panorama += "<h3>Produção mensal de documentos</h3>"





        panorama += f"<img class='grafico' src='{img_mes}'>"





    panorama += "</div>"











    volume = "<div class='secao'><h2>Volume de trabalho — documentos por tipo</h2>"





    volume += (





        "<p>Os tipos abaixo somam o que o SEI registra como <b>documentos gerados</b> no "





        "período, já sem os automáticos. É a medida mais direta do esforço documental "





        "da área: cada linha representa um ato, uma análise, uma comunicação ou um "





        "registro produzido por servidores.</p>"





    )





    volume += _tabela(





        dados["tipos_doc"].head(18).rename(





            columns={"tipo": "Tipo de documento", "total": "Quantidade"}





        )





    ) + "</div>"











    dirs = "".join(_bloco_diretoria(s, dados) for s in dados["unidades"])











    criticos_total = sum(dados["por_unidade"][s]["criticos"] for s in dados["unidades"])





    sem_resp_total = sum(dados["por_unidade"][s]["sem_resp"] for s in dados["unidades"])





    retrato = "<div class='secao'><h2>Retrato atual do SEI (última extração)</h2>"





    retrato += (





        "<p>Números do Painel de Controle do SEI no momento da coleta: o que está "





        "sob a unidade, o que chegou de outras unidades e o que foi gerado ali. "





        "As colunas <b>No controle</b>, <b>Críticos</b> e <b>Sem responsável</b> vêm "





        "do Controle de Processos.</p>"





    )





    retrato += _retrato_tabela(dados)





    retrato += (





        f"<p><b>Pontos de atenção no retrato atual:</b> {_fmt(criticos_total)} processos "





        f"críticos e {_fmt(sem_resp_total)} sem responsável atribuído no controle.</p></div>"





    )











    sintese = "<div class='secao'><h2>Síntese para a transição de governo</h2>"





    sintese += "".join(f"<p>{_md(p)}</p>" for p in sintese_transicao(dados))











    fluxos = ""





    if incluir_fluxos:





        fluxos = (





            "<div class='secao'><h2>Anexo - fluxos de processo da área</h2>"





            "<p>Descrição de como cada tipo de processo tramita, da entrada à saída.</p>"





            + _bloco_fluxos() + "</div>"





        )











    conclusao_sec = (





        "<div class='secao'><h2>Conclusão</h2><div class='conclusao'>"





        + "".join(f"<p>{_md(p)}</p>" for p in conclusao(dados))





        + "</div></div>"





    )











    cabecalho = f"""





    <div class="cabecalho">





      <img src="{logo}" class="logo">





      <div>





        <div class="cabecalho-org">Secretaria de Estado de Infraestrutura, Mobilidade e Parcerias</div>





        <div class="cabecalho-titulo">{TITULO}</div>





        <div class="cabecalho-sub">{SUBTITULO}</div>





      </div>





      <div class="cabecalho-gerado">Gerado em {date.today().strftime('%d/%m/%Y')}</div>





    </div>





    """





    rodape = (





        f"<p class='rodape'>{CREDITO} Documento gerado a partir dos dados do SEI-MG "





        f"em {date.today().strftime('%d/%m/%Y')}. Fonte: Estatísticas da Unidade e "





        f"Controle de Processos. Os valores são informados pelo próprio SEI; este "





        f"relatório apenas os organiza e compara. Documentos automáticos (Recibo "





        f"Eletrônico de Protocolo e Certidão de Intimação Cumprida) são produzidos "





        f"pelo sistema no protocolo/peticionamento; a contagem principal os exclui.</p>"





    )











    return (





        "<!DOCTYPE html><html lang='pt-BR'><head><meta charset='utf-8'>"





        f"<style>{_CSS}</style></head><body>"





        + cabecalho





        + f"<div class='periodo'>Período: <b>{rotulo(de)} a {rotulo(ate)}</b> · "





          f"Unidades: <b>{', '.join(dados['unidades'])}</b> · "





          f"Fonte: Estatísticas da Unidade e Controle de Processos (SEI-MG)</div>"





        + f"<div class='credito'>{CREDITO}</div>"





        + resumo





        + metod





        + panorama





        + _foco_ano_corrente(dados)





        + volume





        + stim





        + dirs





        + retrato





        + sintese





        + fluxos





        + conclusao_sec





        + rodape





        + "</body></html>"





    )

















def gerar_pdf_relatorio(dados: dict, incluir_fluxos: bool = True) -> bytes:





    return gerar_pdf(html_relatorio(dados, incluir_fluxos=incluir_fluxos))