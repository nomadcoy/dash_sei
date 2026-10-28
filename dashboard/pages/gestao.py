from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import streamlit as st

from cfg import unidades
from dashboard.auth import exigir_autenticacao
from dashboard.boletim_dados import PRC, meses_disponiveis, rotulo_mes, serie_mensal
from dashboard.components import charts
from dashboard.gestao_dados import (
    SNAP_ABERTOS,
    SNAP_FECHADOS,
    anos_disponiveis,
    balanco_unidades,
    snapshot_por_tipo,
    suspeitos,
    tempos_medios_resumo,
    tempos_medios_tipos,
)
from dashboard.queries import estatisticas_df
from dashboard.style import descricao_box

exigir_autenticacao()

st.title("Indicadores de Gestão")
st.caption(
    "Indicadores de **fluxo** e **tempo** extraídos das Estatísticas da Unidade do SEI "
    "(processos abertos, fechados, em tramitação, tempos médios e gerados por mês). "
    "São os números que o próprio SEI informa — sem estimativas."
)

est = estatisticas_df()
if est is None or est.empty:
    st.info("Banco sem estatísticas — rode a extração com `--estatisticas`.")
    st.stop()

un_meta = [u["sigla"] for u in unidades()]
anos_disp = anos_disponiveis(est)

f1, f2 = st.columns([2, 1])
with f1:
    unidades_sel = st.multiselect("Diretorias", un_meta, default=un_meta, key="gestao_un")
with f2:
    anos_sel = st.multiselect("Período (anos)", anos_disp, default=anos_disp, key="gestao_anos")

if not unidades_sel:
    st.warning("Selecione ao menos uma diretoria.")
    st.stop()
if not anos_sel:
    st.warning("Selecione ao menos um período (ano).")
    st.stop()

st.divider()

# ---------------------------------------------------------------------------
# Balanço de processos
# ---------------------------------------------------------------------------
st.subheader("Balanço de processos")
descricao_box(
    "Como o SEI classifica os processos da unidade: <b>abertos</b>, "
    "<b>em tramitação</b> e <b>fechados</b>, no período escolhido. A taxa de "
    "conclusão é fechados ÷ (fechados + abertos).",
    "#1D4E89",
)
bal = balanco_unidades(est, unidades_sel, anos_sel)
if bal.empty:
    st.caption("Sem dados de balanço.")
else:
    c1, c2 = st.columns([1, 1.2])
    with c1:
        st.dataframe(
            bal.rename(columns={"unidade": "Diretoria"}).set_index("Diretoria"),
            use_container_width=True,
        )
    with c2:
        st.plotly_chart(charts.fig_barras_balanco(bal, unidades()), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Processos gerados por mês
# ---------------------------------------------------------------------------
st.subheader("Processos gerados por mês")
st.caption(
    "Série mensal de **processos gerados** declarada pelo SEI, por diretoria. "
    "À esquerda o total das diretorias escolhidas; à direita o detalhe por diretoria."
)
meses = [m for m in meses_disponiveis(est) if m[:4] in anos_sel]
if not meses:
    st.caption("Sem série mensal para as diretorias/período escolhidos.")
else:
    de, ate = min(meses), max(meses)
    serie = serie_mensal(est, PRC, de, ate, unidades_sel)
    if serie.empty:
        st.caption("Sem série mensal para as diretorias/período escolhidos.")
    else:
        serie = serie.copy()
        serie["mes_txt"] = serie["mes"].map(rotulo_mes)
        tot = serie.groupby("mes", as_index=False)["quantidade"].sum().sort_values("mes")
        tot["mes_txt"] = tot["mes"].map(rotulo_mes)
        c1, c2 = st.columns([1, 1.3])
        with c1:
            st.plotly_chart(charts.fig_linha_total(tot), use_container_width=True)
        with c2:
            st.plotly_chart(charts.fig_serie_producao_unidades(serie), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# Tempo médio de tramitação
# ---------------------------------------------------------------------------
st.subheader("Tempo médio de tramitação")
st.caption(
    "Tempo médio informado pelo SEI na tabela **'Tempos médios'**, por tipo de "
    "processo, no período escolhido. Valores ≥ 300 dias são tratados como "
    "**suspeitos** (aparentam truncamento no próprio SEI) e ficam fora do resumo."
)
res = tempos_medios_resumo(est, unidades_sel, anos_sel)
if not res.empty:
    st.dataframe(
        res.rename(columns={
            "unidade": "Diretoria", "tipos": "Tipos com tempo",
            "mediana_dias": "Mediana (dias)", "media_dias": "Média (dias)",
        }).set_index("Diretoria"),
        use_container_width=True,
    )
    st.caption(
        "Suspeitos (≥300 dias) por diretoria: "
        + " · ".join(f"**{u}**: {suspeitos(est, u, anos_sel)}" for u in unidades_sel)
    )

detalhe = st.selectbox("Detalhar tempos por tipo — diretoria", unidades_sel, key="gestao_tempo_un")
tmed = tempos_medios_tipos(est, detalhe, anos_sel, incluir_suspeitos=False)
if tmed.empty:
    st.caption("Sem tempos médios para esta diretoria.")
else:
    top = tmed.head(15)
    st.plotly_chart(
        charts.fig_hbar(top, y="tipo", x="dias", cor="#B45309", rotulo_x="dias (média)"),
        use_container_width=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# Tipos por volume
# ---------------------------------------------------------------------------
st.subheader("Tipos de processo por volume")
st.caption("Volume por tipo de processo, conforme o SEI (fechados e abertos), no período escolhido.")
tipo_un = st.selectbox("Diretoria", unidades_sel, key="gestao_tipo_un")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**Fechados (por tipo)**")
    f = snapshot_por_tipo(est, SNAP_FECHADOS, tipo_un, anos_sel).head(15)
    if f.empty:
        st.caption("Sem dados.")
    else:
        st.plotly_chart(
            charts.fig_hbar(
                f.rename(columns={"tipo": "rotulo", "total": "n"}),
                y="rotulo", x="n", cor="#2E7D32", rotulo_x="processos", height=440,
            ),
            use_container_width=True,
        )
with c2:
    st.markdown("**Abertos (por tipo)**")
    a = snapshot_por_tipo(est, SNAP_ABERTOS, tipo_un, anos_sel).head(15)
    if a.empty:
        st.caption("Sem dados.")
    else:
        st.plotly_chart(
            charts.fig_hbar(
                a.rename(columns={"tipo": "rotulo", "total": "n"}),
                y="rotulo", x="n", cor="#B45309", rotulo_x="processos", height=440,
            ),
            use_container_width=True,
        )

st.caption(
    "Fonte: Estatísticas da Unidade — SEI-MG (extração automática). Onde o SEI não "
    "informa, não exibimos."
)
