from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import pandas as pd
import streamlit as st

from cfg import unidades
from dashboard.auth import exigir_autenticacao
from dashboard.boletim_analise import CORES_TIPO, sintese_final, texto_analitico
from dashboard.boletim_dados import (
    AUTOMATICOS,
    DOC,
    EXT,
    PRC,
    comparativo_unidades,
    excluidos_automaticos,
    meses_disponiveis,
    por_categoria,
    por_categoria_unidade,
    rotulo_mes,
    serie_mensal,
    totais_por_tipo,
    total_periodo,
)
from dashboard.boletim_pdf import gerar_pdf, html_boletim
from dashboard.components import charts
from dashboard.gestao_dados import balanco_unidades, suspeitos, tempos_medios_resumo
from dashboard.queries import estatisticas_df
from dashboard.style import descricao_box

exigir_autenticacao()

st.title("Boletim de Produtividade")
st.caption(
    "Documentos e processos gerados por unidade, mês a mês, a partir das "
    "**Estatísticas da Unidade** do SEI (menu Estatísticas > Unidade). "
    "Os valores são informados pelo próprio SEI — o painel apenas organiza e compara "
    "o que ele entrega, sem cálculos inventados."
)

df = estatisticas_df()
if df.empty:
    st.info("Banco sem estatísticas — rode a extração com `--estatisticas`.")
    st.stop()

un_meta = [u["sigla"] for u in unidades()]
meses = meses_disponiveis(df)
if not meses:
    st.info("Sem meses registrados no banco.")
    st.stop()

# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------
f1, f2, f3, f4 = st.columns([1.1, 1.1, 1.6, 1.6])
de = f1.selectbox("Período — de", meses, index=0, format_func=rotulo_mes)
ate = f2.selectbox("Período — até", meses, index=len(meses) - 1, format_func=rotulo_mes)
unidades_sel = f3.multiselect("Unidades", un_meta, default=un_meta)
excluir_auto = f4.checkbox(
    "Excluir documentos automáticos do SEI",
    value=True,
    help="Recibo Eletrônico de Protocolo e Certidão de Intimação Cumprida são gerados "
    "pelo próprio sistema (protocolo e peticionamento), não por ação humana na unidade.",
)
if not unidades_sel:
    st.warning("Selecione ao menos uma unidade.")
    st.stop()
if de > ate:
    st.error("O início do período não pode ser depois do fim.")
    st.stop()

excluir: set[str] = set(AUTOMATICOS) if excluir_auto else set()
UN = unidades_sel


def fmt(n: float) -> str:
    return f"{int(n):,}".replace(",", ".")


# ---------------------------------------------------------------------------
# Números do período
# ---------------------------------------------------------------------------
analise = texto_analitico(df, de, ate, UN, excluir)
sintese = sintese_final(df, de, ate, UN, excluir)
doc_total = total_periodo(df, DOC, de, ate, UN, excluir)
prc_total = total_periodo(df, PRC, de, ate, UN, None)
ext_total = total_periodo(df, EXT, de, ate, UN, None)
tipos_doc = int(totais_por_tipo(df, DOC, de, ate, UN, excluir)["total"].size)
excluidos_v = excluidos_automaticos(df, de, ate, UN)

serie = serie_mensal(df, DOC, de, ate, UN, excluir)
n_meses = int(serie["mes"].nunique()) if not serie.empty else 0
media_mensal = doc_total / n_meses if n_meses else 0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Documentos gerados", fmt(doc_total))
k2.metric("Processos gerados", fmt(prc_total))
k3.metric("Documentos externos", fmt(ext_total))
k4.metric("Tipos de documento", f"{tipos_doc}")

if excluir_auto:
    st.caption(
        f"Documentos automáticos do SEI **excluídos** desta contagem: "
        f"**{fmt(excluidos_v)}** (Recibo Eletrônico de Protocolo e Certidão de "
        f"Intimação Cumprida). Inclua-os desmarcando a caixa acima."
    )
st.caption(
    f"Período: **{rotulo_mes(de)} a {rotulo_mes(ate)}** ({n_meses} "
    f"{'meses' if n_meses != 1 else 'mês'}) · média de **{fmt(media_mensal)}** "
    f"documentos/mês · Unidades: **{', '.join(UN)}**."
)

# ---------------------------------------------------------------------------
# PDF
# ---------------------------------------------------------------------------
col_botao, col_aviso = st.columns([2.2, 4.8])
with col_botao:
    gerar = st.button("Gerar boletim em PDF", type="primary", use_container_width=True)
if gerar:
    with st.spinner("Gerando PDF..."):
        html = html_boletim(
            de=de,
            ate=ate,
            unidades=UN,
            excluir_auto=excluir_auto,
            kpis={
                "Documentos gerados": fmt(doc_total),
                "Processos gerados": fmt(prc_total),
                "Documentos externos": fmt(ext_total),
                "Tipos de documento": f"{tipos_doc}",
            },
            comparativo=comparativo_unidades(df, de, ate, UN, excluir),
            serie=serie,
            por_tipo={
                u: totais_por_tipo(df, DOC, de, ate, [u], excluir)
                for u in UN
            },
            excluidos=excluidos_v,
            analise=analise,
            categorias=por_categoria(df, de, ate, UN, excluir),
            top_documentos=totais_por_tipo(df, DOC, de, ate, UN, excluir).head(20),
            externos=totais_por_tipo(df, EXT, de, ate, UN).head(20),
            processos=totais_por_tipo(df, PRC, de, ate, UN).head(20),
            eficiencia=tempos_medios_resumo(
                df, UN, [str(a) for a in range(int(de[:4]), int(ate[:4]) + 1)]
            ),
            sintese=sintese,
        )
        st.session_state["boletim_pdf"] = gerar_pdf(html)
if st.session_state.get("boletim_pdf") is not None:
    with col_aviso:
        st.download_button(
            "Baixar PDF",
            data=st.session_state["boletim_pdf"],
            file_name=f"boletim_{de}_{ate}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )

st.divider()

# ---------------------------------------------------------------------------
# Leitura analítica — frases geradas dos números (sem IA externa)
# ---------------------------------------------------------------------------
st.subheader("Leitura analítica do período")
for item in analise:
    descricao_box(item["texto"], cor=CORES_TIPO.get(item["tipo"], "#1D4E89"))

st.divider()

# ---------------------------------------------------------------------------
# Perfil da produção por categoria de documento
# ---------------------------------------------------------------------------
st.subheader("O que as diretorias produzem — por categoria de documento")
st.caption(
    "Agrupamento dos tipos de documento informados pelo SEI em categorias "
    "(comunicações oficiais, notas/relatórios técnicos, despachos e decisões, "
    "termos e contratos, certidões, RH, requerimentos). O agrupamento é uma "
    "classificação nossa sobre os tipos reais — não altera os números."
)
cat_un = por_categoria_unidade(df, de, ate, UN, excluir)
cat = por_categoria(df, de, ate, UN, excluir)
if cat.empty:
    st.caption("Sem documentos no período.")
else:
    c1, c2 = st.columns([1.3, 1])
    with c1:
        st.plotly_chart(charts.fig_barras_categorias(cat_un, unidades()), use_container_width=True)
    with c2:
        st.dataframe(
            cat.rename(columns={"categoria": "Categoria", "total": "Documentos"}).set_index("Categoria"),
            use_container_width=True,
        )

st.divider()

# ---------------------------------------------------------------------------
# Documentos mais produzidos
# ---------------------------------------------------------------------------
st.subheader("Documentos mais produzidos (por tipo)")
top_doc = totais_por_tipo(df, DOC, de, ate, UN, excluir).head(18)
if top_doc.empty:
    st.caption("Sem documentos no período.")
else:
    st.plotly_chart(
        charts.fig_hbar(
            top_doc.rename(columns={"tipo": "rotulo", "total": "n"}),
            y="rotulo", x="n", cor="#1D4E89", rotulo_x="documentos", height=520,
        ),
        use_container_width=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# Documentos externos e tipos de processo
# ---------------------------------------------------------------------------
c1, c2 = st.columns(2)
with c1:
    st.subheader("Documentos externos (interface com outros órgãos/cidadão)")
    st.caption("Documentos de origem externa registrados no SEI e tratados nas unidades.")
    ext_top = totais_por_tipo(df, EXT, de, ate, UN).head(15)
    if ext_top.empty:
        st.caption("Sem documentos externos no período.")
    else:
        st.dataframe(
            ext_top.rename(columns={"tipo": "Tipo", "total": "Quantidade"}),
            use_container_width=True, hide_index=True, height=430,
        )
with c2:
    st.subheader("Tipos de processo gerados")
    st.caption("Processos autuados pelas unidades no período, por tipo informado pelo SEI.")
    prc_top = totais_por_tipo(df, PRC, de, ate, UN).head(15)
    if prc_top.empty:
        st.caption("Sem processos gerados no período.")
    else:
        st.dataframe(
            prc_top.rename(columns={"tipo": "Tipo de processo", "total": "Quantidade"}),
            use_container_width=True, hide_index=True, height=430,
        )

st.divider()

# ---------------------------------------------------------------------------
# Série histórica em linha
# ---------------------------------------------------------------------------
st.subheader("Série histórica (linha)")
st.caption(
    "Evolução mês a mês de **documentos gerados** — à esquerda o total das unidades "
    "escolhidas, à direita o detalhe por diretoria."
)
if serie.empty:
    st.caption("Sem série mensal para exibir.")
else:
    tot = serie.groupby("mes", as_index=False)["quantidade"].sum().sort_values("mes")
    tot["mes_txt"] = tot["mes"].map(rotulo_mes)
    du = serie.copy()
    du["mes_txt"] = du["mes"].map(rotulo_mes)
    c1, c2 = st.columns([1, 1.25])
    with c1:
        st.plotly_chart(charts.fig_linha_total(tot), use_container_width=True)
    with c2:
        st.plotly_chart(charts.fig_serie_producao_unidades(du), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Comparativo por diretoria (total do período)
# ---------------------------------------------------------------------------
st.subheader("Comparativo por diretoria")
st.dataframe(
    comparativo_unidades(df, de, ate, UN, excluir).set_index("Unidade"),
    use_container_width=True,
)

st.divider()

# ---------------------------------------------------------------------------
# Eficiência — tempo médio de tramitação e conclusão (dados do SEI)
# ---------------------------------------------------------------------------
st.subheader("Eficiência — tempo médio e conclusão")
st.caption(
    "Tempo médio de tramitação informado pelo SEI ('Tempos médios') e balanço de "
    "processos (abertos/fechados) do período. Valores ≥ 300 dias são tratados como "
    "suspeitos (truncamento do SEI) e ficam fora da mediana."
)
anos = [str(a) for a in range(int(de[:4]), int(ate[:4]) + 1)]
res = tempos_medios_resumo(df, UN, anos)
bal = balanco_unidades(df, UN, anos)
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Tempo médio de tramitação (dias)**")
    if res.empty:
        st.caption("Sem dados.")
    else:
        st.dataframe(
            res.rename(columns={
                "unidade": "Diretoria", "tipos": "Tipos com tempo",
                "mediana_dias": "Mediana", "media_dias": "Média",
            }).set_index("Diretoria"),
            use_container_width=True,
        )
        st.caption("Suspeitos (≥300d): " + " · ".join(f"**{u}**: {suspeitos(df, u, anos)}" for u in UN))
with c2:
    st.markdown("**Balanço de processos (SEI)**")
    if bal.empty:
        st.caption("Sem dados.")
    else:
        st.dataframe(
            bal.rename(columns={
                "unidade": "Diretoria", "Taxa de conclusão (%)": "Conclusão (%)",
            }).set_index("Diretoria"),
            use_container_width=True,
        )

st.divider()

# ---------------------------------------------------------------------------
# Documentos gerados por tipo (por unidade)
# ---------------------------------------------------------------------------
st.subheader("Documentos gerados por tipo — detalhe por unidade")
for u in UN:
    t = totais_por_tipo(df, DOC, de, ate, [u], excluir)
    if t.empty:
        continue
    with st.expander(f"{u} — documentos gerados por tipo"):
        st.dataframe(
            t.rename(columns={"tipo": "Tipo de documento", "total": "Quantidade"}).set_index("Tipo de documento"),
            use_container_width=True,
        )

st.divider()

# ---------------------------------------------------------------------------
# Síntese do conjunto — leitura da totalidade (STIM + diretorias)
# ---------------------------------------------------------------------------
st.subheader("Síntese do período — leitura do conjunto")
st.caption(
    "Leitura automática da totalidade (STIM e diretorias), gerada apenas dos números "
    "do SEI — para compreensão rápida do período. Sem estimativas."
)
for item in sintese:
    descricao_box(item["texto"], cor=CORES_TIPO.get(item["tipo"], "#1D4E89"))

st.caption(
    "Fonte: Estatísticas da Unidade — SEI-MG (extração automática). Compare sempre com "
    "o período declarado acima. O SEI não detalha o que classifica como 'documento "
    "externo'; a marcação é feita por ele, não por nós. Documentos automáticos "
    "(Recibo Eletrônico de Protocolo e Certidão de Intimação Cumprida) são produzidos "
    "pelo próprio SEI no protocolo e no peticionamento."
)
