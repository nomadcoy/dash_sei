from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import pandas as pd
import streamlit as st

from cfg import descricao_unidade, limiar_padrao, unidades
from dashboard.auth import exigir_autenticacao
from dashboard.components import charts
from dashboard.queries import (
    comparativo_diretorias,
    criticos_df,
    painel_atrasos,
    painel_por_unidade,
    processos_df,
    processos_sem_atribuicao,
)

exigir_autenticacao()

st.title("Diretorias")
st.caption("Comparativo entre as diretorias, com os cartões reais do Painel de Controle do SEI.")

painel = painel_por_unidade()
df = processos_df()
if painel.empty or df.empty:
    st.info("Banco vazio. Rode a extração do SEI.")
    st.stop()

comp = comparativo_diretorias(painel, df, limiar_padrao())
atras = painel_atrasos(painel)

st.subheader("Cartões do painel × criticidade")
st.dataframe(comp.set_index("unidade").T, use_container_width=True)

c1, c2 = st.columns(2)
with c1:
    st.subheader("Total × sem acompanhamento × prioritários")
    st.plotly_chart(
        charts.fig_barras_painel(
            comp.set_index("unidade"),
            unidades(),
            ["Total", "Sem acompanhamento", "Prioritários"],
        ),
        use_container_width=True,
    )
with c2:
    st.subheader("Atrasos de prazo por diretoria")
    st.dataframe(
        pd.DataFrame(
            [{"Diretoria": u, "Atrasados/Devolvidos": atras.get(u, 0)} for u in comp["unidade"]]
        ).set_index("Diretoria"),
        use_container_width=True,
    )

st.divider()

siglas = [u["sigla"] for u in unidades()]
selecionada = st.radio(
    "Diretoria (detalhe)", siglas, horizontal=True,
    format_func=lambda s: f"{s} - {descricao_unidade(s).split('.')[0][:40]}",
)
cor = next(u["cor"] for u in unidades() if u["sigla"] == selecionada)

sub = df[df["unidade"] == selecionada]
abertos = sub[sub["em_aberto"]]
sem = processos_sem_atribuicao(df, selecionada)

c1, c2 = st.columns(2)
with c1:
    quadro_base = int(sub.shape[0])
    st.subheader("Sem responsável/dono")
    st.metric(
        "Sem responsável/dono",
        f"{len(sem)}",
        delta=f"{round(len(sem) / quadro_base * 100) if quadro_base else 0}% dos {quadro_base} do controle",
        delta_color="inverse",
    )
    if not sem.empty:
        mostra = sem[["numero", "tipo_processo", "especificacao", "marcadores"]].head(30).copy()
        mostra["marcadores"] = mostra["marcadores"].map(lambda m: ", ".join(m) if m else "")
        mostra["especificacao"] = mostra["especificacao"].fillna("").astype(str).str.slice(0, 50)
        st.dataframe(mostra, use_container_width=True, hide_index=True)
with c2:
    st.subheader("Processos críticos da diretoria")
    crit = criticos_df(df, limiar_padrao(), siglas=[selecionada])
    st.metric("Críticos", f"{len(crit)}")
    if not crit.empty:
        mostra = crit[["numero", "tipo_processo", "criticidade", "responsavel", "situacao"]].head(30).copy()
        mostra["responsavel"] = mostra["responsavel"].fillna("sem responsável")
        st.dataframe(mostra, use_container_width=True, hide_index=True)

st.caption(f"Total na base da diretoria: **{len(sub)}** processos (Controle de Processos do SEI); "
           f"cartões acima são os do Painel de Controle do SEI.")