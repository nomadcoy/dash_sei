from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import streamlit as st

from cfg import limiar_padrao, nome_unidade, unidades
from dashboard.auth import exigir_autenticacao
from dashboard.components import charts
from dashboard.queries import criticos_df, pontos_por_fator, processos_df

exigir_autenticacao()

st.title("Processos Críticos e Prioritários")
st.caption(
    "Índice composto 0–100: prioridade SEI · marcador crítico · tempo sem "
    "andamento · idade vs. pares do tipo · idas e vindas entre unidades"
)

df = processos_df()
if df.empty:
    st.info("Banco vazio.")
    st.stop()

siglas = [u["sigla"] for u in unidades()]
tipos = sorted(df["tipo_processo"].dropna().unique())

st.divider()

with st.container(border=True):
    f1, f2, f3, f4 = st.columns([1, 2, 1.4, 1.2])
    with f1:
        limiar = st.slider("Limiar de criticidade", 0, 100, limiar_padrao(), 5)
    with f2:
        sel_un = st.multiselect("Diretorias", siglas, default=siglas)
    with f3:
        sel_tipo = st.selectbox("Tipo de processo", ["(todos)"] + tipos)
    with f4:
        so_abertos = st.toggle("Somente em aberto", value=True)

crit = criticos_df(
    df,
    limiar=limiar,
    siglas=sel_un,
    tipo=None if sel_tipo == "(todos)" else sel_tipo,
    somente_abertos=so_abertos,
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Processos no ranking", len(crit))
k2.metric("Crítica média", f"{crit['criticidade'].mean():.0f} pts" if len(crit) else "—")
k3.metric("Com prioridade SEI", int(crit["prioridade"].sum()) if len(crit) else 0)
k4.metric("Parados â¥ 30 dias", int((crit["ultima_movimentacao"].notna()).sum() and
    ((crit["criticidade_fatores"].str.contains("sem_andamento")).sum())) if len(crit) else 0)

if len(crit):
    c1, c2 = st.columns([1, 1])
    with c1:
        st.subheader("O que está puxando a criticidade")
        fatores = pontos_por_fator(crit)
        st.plotly_chart(charts.fig_pontos_fator(fatores), use_container_width=True)
    with c2:
        st.subheader("Distribuição por diretoria")
        cont = crit.groupby("unidade").size()
        cores = [next(u["cor"] for u in unidades() if u["sigla"] == s) for s in cont.index]
        st.plotly_chart(charts.fig_donut(cont, cores), use_container_width=True)

    st.subheader(f"Ranking ({len(crit)} processos)")
    mostra = crit[[
        "numero", "unidade", "tipo_processo", "criticidade", "prioridade",
        "situacao", "responsavel", "ultima_movimentacao", "marcadores",
        "assunto", "link_sei",
    ]].copy()
    mostra["ultima_movimentacao"] = mostra["ultima_movimentacao"].dt.strftime("%d/%m/%Y")
    mostra["marcadores"] = mostra["marcadores"].map(lambda m: ", ".join(m) if m else "—")
    mostra["prioridade"] = mostra["prioridade"].map({1: "Sim", 0: "—"})
    mostra = mostra.rename(columns={
        "numero": "Processo", "unidade": "Diretoria", "tipo_processo": "Tipo",
        "criticidade": "Pts", "situacao": "Situação", "responsavel": "Resp.",
        "ultima_movimentacao": "Últ. movim.", "marcadores": "Marcadores",
        "assunto": "Assunto", "link_sei": "SEI",
    })
    st.dataframe(
        mostra, use_container_width=True, hide_index=True, height=480,
        column_config={
            "SEI": st.column_config.LinkColumn("Abrir", display_text="abrir"),
            "Pts": st.column_config.ProgressColumn(
                "Crítica.", min_value=0, max_value=100, format="%d"
            ),
        },
    )
    csv = crit.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Exportar ranking (CSV)",
        data=csv,
        file_name="processos_criticos.csv",
        mime="text/csv",
    )
else:
    st.success("Nenhum processo acima do limiar com os filtros atuais.")

with st.expander("Como o índice é calculado"):
    st.markdown(
        """
| Critério | Pontos |
|---|---|
| Marcado como **prioridade** no SEI | +30 |
| **Marcador crítico** (URGENTE, VENCENDO PRAZO, PRAZO VENCIDO, CRÍTICO…) | +25 |
| **Parado** na unidade além do prazo do tipo (padrão: 21 dias) | +20 |
| **Idade** acima do percentil 90 dos processos do mesmo tipo | +15 |
| **Idas e vindas** entre unidades (≥ 2 reprocessamentos) | +10 |

Pesos editáveis em `config/criterios.yaml`; prazos por tipo em `config/prazos.yaml`.
"""
    )
