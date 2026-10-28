from __future__ import annotations

import math

import streamlit as st

from cfg import unidades
from dashboard.auth import exigir_autenticacao
from dashboard.components import charts
from dashboard.queries import (
    painel_por_unidade,
    painel_secao,
    processos_df,
    processos_sem_atribuicao,
    top_marcadores,
)
from dashboard.style import descricao_box

st.set_page_config(page_title="Painel de Controle", layout="wide")

exigir_autenticacao()

siglas = [u["sigla"] for u in unidades()]
descs = {u["sigla"]: u.get("descricao", "") for u in unidades()}

st.title("Painel de Controle do SEI")
st.caption("Espelha os cartões e tabelas do Painel de Controle do SEI, por diretoria.")

painel = painel_por_unidade()
df = processos_df()

disponiveis = sorted(set(painel["unidade"])) if not painel.empty else []
selecao = st.radio(
    "Diretoria",
    disponiveis or siglas,
    horizontal=True,
    label_visibility="collapsed",
)
cor = next(u["cor"] for u in unidades() if u["sigla"] == selecao)
descricao_box(descs.get(selecao, ""), cor)

if painel.empty:
    st.warning("Nenhum dado de painel ainda. Rode a extração do SEI.")
    st.stop()

linha = painel[painel["unidade"] == selecao].iloc[0]


def _v(chave):
    v = linha.get(chave)
    if v is None:
        return "—"
    try:
        f = float(v)
    except (TypeError, ValueError):
        return "—"
    if not math.isfinite(f):
        return "—"
    return f"{int(f):,}".replace(",", ".")


k1, k2, k3, k4 = st.columns(4)
k1.metric("Total de processos", _v("total"))
k2.metric("Recebidos", _v("recebidos"))
k3.metric("Gerados", _v("gerados"))
k4.metric("Não visualizados", _v("nao_visualizados"))
k5, k6, k7 = st.columns(3)
k5.metric("Sem acompanhamento", _v("sem_acompanhamento"))
k6.metric("Alterados", _v("alterados"))
k7.metric("Prioritários", _v("prioritarios"))

st.divider()

c1, c2, c3 = st.columns(3)
with c1:
    st.subheader("Controles de Prazo")
    st.dataframe(painel_secao(painel, selecao, "prazos"), use_container_width=True, hide_index=True)
with c2:
    st.subheader("Retornos Programados")
    st.dataframe(painel_secao(painel, selecao, "retornos"), use_container_width=True, hide_index=True)
with c3:
    st.subheader("Blocos de Assinatura")
    st.dataframe(painel_secao(painel, selecao, "blocos"), use_container_width=True, hide_index=True)

st.divider()

sem = processos_sem_atribuicao(df, selecao)
quadro_base = int(df[df["unidade"] == selecao].shape[0])
share = round(len(sem) / quadro_base * 100) if quadro_base else 0
c1, c2 = st.columns([2, 1])
with c1:
    st.subheader(f"Processos sem responsável/dono ({len(sem)})")
    st.metric(
        "Sem responsável/dono",
        f"{len(sem)}",
        delta=f"{share}% dos {quadro_base} do controle",
        delta_color="inverse",
    )
    if sem.empty:
        st.caption("Nenhum processo sem responsável nesta diretoria.")
    else:
        mostra = sem[["numero", "tipo_processo", "especificacao", "marcadores", "link_sei"]].copy()
        mostra["marcadores"] = mostra["marcadores"].map(lambda m: ", ".join(m) if m else "")
        mostra["especificacao"] = mostra["especificacao"].fillna("").astype(str).str.slice(0, 60)
        n = min(len(mostra), 50)
        st.dataframe(
            mostra.head(n), use_container_width=True, hide_index=True,
            column_config={
                "link_sei": st.column_config.LinkColumn("SEI", display_text="abrir"),
            },
        )
        if len(mostra) > n:
            st.caption(f"Mostrando {n} de {len(mostra)}.")
with c2:
    st.subheader("Marcadores mais usados")
    marc = top_marcadores(df, selecao)
    if marc.empty:
        st.caption("Sem marcadores.")
    else:
        st.plotly_chart(charts.fig_top_marcadores(marc), use_container_width=True)

st.divider()

sub = df[df["unidade"] == selecao]
com_resp = sub[sub["responsavel"].notna()]
if not com_resp.empty:
    st.subheader("Processos por responsável")
    img = com_resp.groupby("responsavel").size().sort_values(ascending=False).reset_index(name="processos")
    img.columns = ["responsavel", "processos"]
    st.dataframe(img, use_container_width=True, hide_index=True)

st.caption("Fonte: Painel de Controle e Controle de Processos do SEI-MG (extração automática).")