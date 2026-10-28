from __future__ import annotations



"""Camada de dados do Relatório Gerencial de Transição de Governo.



Tudo é derivado das Estatísticas da Unidade e do Controle de Processos do SEI

já extraídos para o banco local (``sei.db``). Nenhum número é inventado: quando

não há dado, a ausência é explicitada no texto.

"""



from datetime import datetime



import pandas as pd



from cfg import descricao_unidade, limiar_padrao, nome_unidade

from dashboard.boletim_dados import (

    AUTOMATICOS,

    DOC,

    EXT,

    PRC,

    comparativo_unidades,

    excluidos_automaticos,

    serie_mensal,

    totais_por_tipo,

    total_periodo,

)

from dashboard.queries import estatisticas_df, painel_por_unidade, processos_df



ORDEM = ["DGTI", "DGTM", "DRTC", "STIM"]



_MES_RE = r"^\d{4}-\d{2}$"





def _anos(df: pd.DataFrame) -> list[str]:

    m = df["mes"].astype(str)

    m = m[m.str.match(_MES_RE, na=False)]

    return sorted(m.str[:4].unique().tolist())





def serie_anual(

    df: pd.DataFrame,

    tabela: str,

    de: str,

    ate: str,

    unidades: list[str] | None = None,

    excluir: set[str] | None = None,

) -> pd.DataFrame:

    """Soma anual (ano, unidade) de uma tabela dentro do intervalo [de, ate]."""

    sub = df[df["tabela"].eq(tabela)].copy()

    sub = sub[sub["mes"].astype(str).str.match(_MES_RE, na=False)]

    sub = sub[(sub["mes"] >= de) & (sub["mes"] <= ate)]

    if unidades:

        sub = sub[sub["unidade"].isin(unidades)]

    if excluir:

        sub = sub[~sub["tipo"].astype(str).str.upper().isin(excluir)]

    if sub.empty:

        return pd.DataFrame(columns=["ano", "unidade", "quantidade"])

    sub["ano"] = sub["mes"].astype(str).str[:4]

    return (

        sub.groupby(["ano", "unidade"], as_index=False)["valor"].sum()

        .rename(columns={"valor": "quantidade"})

    )





def serie_anual_total(

    df: pd.DataFrame,

    tabela: str,

    de: str,

    ate: str,

    unidades: list[str] | None = None,

    excluir: set[str] | None = None,

) -> pd.DataFrame:

    s = serie_anual(df, tabela, de, ate, unidades, excluir)

    if s.empty:

        return pd.DataFrame(columns=["ano", "quantidade"])

    return s.groupby("ano", as_index=False)["quantidade"].sum()





def _por_ano_dict(s: pd.DataFrame, unidade: str) -> dict[str, int]:

    sub = s[s["unidade"] == unidade]

    return {str(a): int(round(v)) for a, v in zip(sub["ano"], sub["quantidade"])}





def _port_por_ano(df: pd.DataFrame, tabela: str, de: str, ate: str,

                  unidade: str, excluir: set[str] | None = None) -> dict[str, int]:

    s = serie_anual(df, tabela, de, ate, [unidade], excluir)

    return {str(a): int(round(v)) for a, v in zip(s["ano"], s["quantidade"])}





def montar(

    de: str,

    ate: str,

    unidades_sel: list[str] | None = None,

    excluir_auto: bool = True,

    limiar: int | None = None,

) -> dict:

    """Reúne tudo que o relatório precisa a partir dos dados reais do SEI."""

    est = estatisticas_df()

    proc = processos_df()

    painel = painel_por_unidade()

    UN = [u for u in (unidades_sel or ORDEM) if u in ORDEM]

    limiar = int(limiar if limiar is not None else limiar_padrao())

    excluir: set[str] = set(AUTOMATICOS) if excluir_auto else set()



    anos = _anos(est)

    anos = [a for a in anos if de[:4] <= a <= ate[:4]]



    # ---- KPIs globais (perï¿½odo) ------------------------------------------

    doc_sem = total_periodo(est, DOC, de, ate, UN, excluir)

    doc_com = total_periodo(est, DOC, de, ate, UN, None)

    prc = total_periodo(est, PRC, de, ate, UN, None)

    ext = total_periodo(est, EXT, de, ate, UN, None)

    exclu_un = excluidos_automaticos(est, de, ate, UN)

    tipos = totais_por_tipo(est, DOC, de, ate, UN, excluir)



    # ---- Sï¿½rie por ano ---------------------------------------------------

    anual_doc = serie_anual(est, DOC, de, ate, UN, excluir)

    anual_prc = serie_anual(est, PRC, de, ate, UN, None)

    anual_ext = serie_anual(est, EXT, de, ate, UN, None)

    anual_doc_total = serie_anual_total(est, DOC, de, ate, UN, excluir)



    # ---- Comparativo por unidade (perï¿½odo) ------------------------------

    comparativo = comparativo_unidades(est, de, ate, UN, excluir)



    # ---- Sï¿½rie mensal (docs sem automï¿½ticos) ----------------------------

    serie = serie_mensal(est, DOC, de, ate, UN, excluir)



    # ---- Painel (retrato atual do SEI) ----------------------------------

    painel_map = {r["unidade"]: r for _, r in painel.iterrows()}



    # ---- Bloco por unidade ----------------------------------------------

    por_unidade: dict[str, dict] = {}

    for u in UN:

        sub = proc[proc["unidade"] == u]

        criticos = int((pd.to_numeric(sub["criticidade"], errors="coerce").fillna(0) >= limiar).sum()) if not proc.empty else 0

        em_aberto = int(sub["em_aberto"].sum()) if not proc.empty else 0

        top_proc = (

            proc[proc["unidade"] == u]["tipo_processo"].value_counts().head(8)

            .rename_axis("tipo").reset_index(name="processos")

            if not proc.empty else pd.DataFrame(columns=["tipo", "processos"])

        )

        eixos = pd.DataFrame(columns=["eixo", "processos"])

        if not proc.empty and "eixo" in proc:

            eixos = (

                proc[proc["unidade"] == u]["eixo"].dropna().value_counts().head(8)

                .rename_axis("eixo").reset_index(name="processos")

            )

        rp = painel[painel["unidade"] == u]

        painel_row = rp.iloc[0].to_dict() if not rp.empty else {}

        por_unidade[u] = {

            "sigla": u,

            "nome": nome_unidade(u),

            "descricao": descricao_unidade(u),

            "docs_ano": _por_ano_dict(anual_doc, u),

            "prc_ano": _port_por_ano(est, PRC, de, ate, u, None),

            "ext_ano": _por_ano_dict(anual_ext, u),

            "docs_total": int(round(sum(_por_ano_dict(anual_doc, u).values()))),

            "prc_total": int(round(sum(_port_por_ano(est, PRC, de, ate, u, None).values()))),

            "ext_total": int(round(sum(_por_ano_dict(anual_ext, u).values()))),

            "top_docs": totais_por_tipo(est, DOC, de, ate, [u], excluir),

            "serie_mensal": serie_mensal(est, DOC, de, ate, [u], excluir),

            "n_proc": int(len(proc[proc["unidade"] == u])),

            "top_tipos_proc": _top_tipos(proc, u),

            "eixos": eixos,

            "criticos": int(

                (proc[(proc["unidade"] == u) & (proc["criticidade"] >= limiar)]).shape[0]

            ),

            "sem_resp": int(proc[proc["unidade"] == u]["sem_atribuicao"].sum())

            if not proc.empty else 0,

            "painel": painel_row,

        }



    atual = datetime.now().strftime("%Y-%m")

    return {

        "de": de,

        "ate": ate,

        "unidades": UN,

        "excluir_auto": excluir_auto,

        "limiar": limiar,

        "anos": anos,

        "mes_atual": atual,

        "kpis": {

            "doc_sem_auto": int(round(doc_sem)),

            "doc_com_auto": int(round(doc_com)),

            "proc": int(round(prc)),

            "ext": int(round(ext)),

            "excluidos": int(round(exclu_un)),

            "n_tipos": int(tipos["total"].size) if not tipos.empty else 0,

            "automï¿½ticos": int(round(exclu_un)),

        },

        "tipos_doc": tipos,

        "anual": {

            "doc": anual_doc,

            "prc": anual_prc,

            "ext": anual_ext,

            "doc_total": anual_doc_total,

        },

        "comparativo": comparativo,

        "serie_mensal": serie,

        "por_unidade": por_unidade,

    }





def _top_tipos(proc: pd.DataFrame, unidade: str, n: int = 8) -> pd.DataFrame:

    sub = proc[proc["unidade"] == unidade]

    if sub.empty:

        return pd.DataFrame(columns=["tipo_processo", "processos"])

    return (

        sub["tipo_processo"].fillna("(nï¿½o informado)").value_counts().head(n)

        .rename_axis("tipo_processo").reset_index(name="processos")

    )





def mapa_processos() -> dict[str, dict]:

    """Tipos de processo do ``stim_map.yaml`` indexados pelo nome."""

    from cfg import stim_map



    m = stim_map() or {}

    return {t.get("nome", ""): t for t in (m.get("tipos_processo") or [])}





def visao_geral_stim() -> str:

    from cfg import stim_map



    return (stim_map() or {}).get("visao_geral", "").strip()