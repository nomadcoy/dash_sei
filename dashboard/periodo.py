from __future__ import annotations

import pandas as pd
import streamlit as st

from dashboard.boletim_dados import (
    AUTOMATICOS,
    DOC,
    EXT,
    PRC,
    meses_disponiveis,
    rotulo_mes,
    serie_mensal,
)
from dashboard.components import charts
from dashboard.queries import estatisticas_df


def _sem_automaticos(est: pd.DataFrame) -> pd.DataFrame:
    """Remove RECIBO ELETRÔNICO DE PROTOCOLO e CERTIDÃO DE INTIMAÇÃO CUMPRIDA
    da contagem de documentos gerados (mesma convenção do boletim)."""
    return est[~est["tipo"].astype(str).str.upper().isin(AUTOMATICOS)]


def _fmt(v: int) -> str:
    return f"{v:,}".replace(",", ".")


def meses() -> list[str]:
    est = estatisticas_df()
    if est is None or est.empty:
        return []
    return meses_disponiveis(est)


def widget_periodo(chave: str) -> tuple[str | None, str | None]:
    """Seletor De/Até em meses das Estatísticas da Unidade. Chave única por página."""
    todos = meses()
    if not todos:
        st.info("Sem dados mensais de Estatísticas da Unidade ainda.")
        return None, None
    nomes = [rotulo_mes(m) for m in todos]
    pad = {nome: mes for nome, mes in zip(nomes, todos)}
    c1, c2, _ = st.columns([1, 1, 3])
    de_nome = c1.selectbox("Período de", nomes, index=0, key=f"{chave}__de")
    ate_nome = c2.selectbox("até", nomes, index=len(nomes) - 1, key=f"{chave}__ate")
    de, ate = pad[de_nome], pad[ate_nome]
    if ate < de:
        st.warning("Período inválido: o mês final é anterior ao inicial.")
        return None, None
    return de, ate


def serie_producao_total(
    de: str, ate: str, unidades: list[str] | None = None
) -> pd.DataFrame:
    """Série (mes → documentos/processos/externos) somando as unidades escolhidas."""
    est = estatisticas_df()
    todos = [m for m in meses() if de <= m <= ate]
    colunas = {"documentos": DOC, "processos": PRC, "externos": EXT}
    base = pd.DataFrame({"mes": todos})
    for col, tabela in colunas.items():
        fonte = est if tabela != DOC else _sem_automaticos(est)
        s = serie_mensal(fonte, tabela, de, ate, unidades)
        s_total = s.groupby("mes")["quantidade"].sum()
        base[col] = base["mes"].map(s_total).fillna(0).astype(int)
    base["mes_txt"] = base["mes"].map(rotulo_mes)
    return base


def serie_producao_por_unidade(
    tabela: str, de: str, ate: str, unidades: list[str] | None = None
) -> pd.DataFrame:
    """Linha por unidade: (mes, unidade, quantidade) de uma tabela no período."""
    est = estatisticas_df()
    fonte = est if tabela != DOC else _sem_automaticos(est)
    s = serie_mensal(fonte, tabela, de, ate, unidades)
    if s.empty:
        return s
    s = s.copy()
    s["mes_txt"] = s["mes"].map(rotulo_mes)
    return s.sort_values(["mes", "unidade"])


def bloco_serie_producao(
    de: str | None,
    ate: str | None,
    unidades: list[str] | None = None,
    titulo: str = "Série histórica de produção",
    mostrar_por_unidade: bool = True,
) -> None:
    """Cartões + gráficos de produção mensal (Estatísticas da Unidade)."""
    if not de or not ate:
        st.caption("Selecione um período para visualizar a série histórica.")
        return
    base = serie_producao_total(de, ate, unidades)
    if base.empty:
        st.caption("Sem dados de Estatísticas da Unidade no período selecionado.")
        return
    n = max(1, len(base))
    st.subheader(titulo)
    c1, c2, c3 = st.columns(3)
    c1.metric("Documentos gerados", _fmt(int(base["documentos"].sum())))
    c2.metric("Processos gerados", _fmt(int(base["processos"].sum())))
    c3.metric("Docs externos", _fmt(int(base["externos"].sum())))

    du = (
        serie_producao_por_unidade(DOC, de, ate, unidades)
        if mostrar_por_unidade
        else pd.DataFrame()
    )
    if not du.empty:
        c4, c5 = st.columns([1.15, 1])
        with c4:
            st.plotly_chart(charts.fig_serie_producao(base), use_container_width=True)
        with c5:
            st.plotly_chart(charts.fig_serie_producao_unidades(du), use_container_width=True)
    else:
        st.plotly_chart(charts.fig_serie_producao(base), use_container_width=True)
    st.caption(
        f"Totais de **{rotulo_mes(de)}** a **{rotulo_mes(ate)}** ({n} meses). "
        "Documentos gerados **sem** os automáticos do SEI (Recibo Eletrônico de "
        "Protocolo e Certidão de Intimação Cumprida), como no Boletim. "
        "Fonte: Estatísticas da Unidade (SEI-MG) — última extração de cada unidade."
    )