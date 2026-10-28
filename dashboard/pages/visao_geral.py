from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import streamlit as st

from cfg import limiar_padrao, unidades
from dashboard.auth import exigir_autenticacao
from dashboard.components import charts
from dashboard.periodo import bloco_serie_producao, widget_periodo
from dashboard.queries import (
    comparativo_diretorias,
    criticos_df,
    painel_agregado,
    painel_kpis,
    painel_por_unidade,
    processos_df,
    processos_sem_atribuicao,
)
from dashboard.style import descricao_box

exigir_autenticacao()

st.title("Visão Geral da Superintendência")
st.caption("Gestão à vista dos 4 diretórios — DGTI · DGTM · DRTC · STIM")
st.info(
    "Cartões e tabelas vêm do **Painel de Controle do SEI** (por diretoria). O "
    "**sem responsável/dono** é calculado no Controle de Processos: processos da "
    "unidade sem usuário atribuído — é o que importa para distribuir trabalho."
)

painel = painel_por_unidade()
df = processos_df()
if painel.empty or df.empty:
    st.info("Banco vazio. Rode a extração do SEI (`python -m extractor.main`).")
    st.stop()

k = painel_kpis(painel)
total_criticos = int(
    (df["em_aberto"] & (df["criticidade"] >= limiar_padrao())).sum()
)
sem_all = processos_sem_atribuicao(df)
total_sem_resp = len(sem_all)
share_sem_resp = round(total_sem_resp / len(df) * 100) if len(df) else 0


def _fmt(v: int) -> str:
    return f"{v:,}".replace(",", ".")


# ---------------------------------------------------------------------------
# Cartões clicáveis → mostram os processos a que se referem
# ---------------------------------------------------------------------------
if "vg_sel" not in st.session_state:
    st.session_state["vg_sel"] = None

LINHAS = [
    [
        ("total", "Total de processos (SEI)", _fmt(k["total"])),
        ("recebidos", "Recebidos", _fmt(k["recebidos"])),
        ("gerados", "Gerados", _fmt(k["gerados"])),
        ("nao_visualizados", "Não visualizados", _fmt(k["nao_visualizados"])),
    ],
    [
        ("sem_resp", "Sem responsável/dono", _fmt(total_sem_resp)),
        ("prioritarios", "Prioritários", _fmt(k["prioritarios"])),
        ("alterados", "Alterados", _fmt(k["alterados"])),
        ("criticos", "Críticos (criticidade)", _fmt(total_criticos)),
    ],
]

st.caption("Clique em um cartão para ver os processos a que ele se refere.")
for linha in LINHAS:
    cols = st.columns(4)
    for col, (chave, nome, valor) in zip(cols, linha):
        ativo = st.session_state["vg_sel"] == chave
        if col.button(
            f"{nome}\n\n**{valor}**",
            key=f"vgcard_{chave}",
            use_container_width=True,
            type="primary" if ativo else "secondary",
        ):
            st.session_state["vg_sel"] = None if ativo else chave
            st.rerun()

_detalhar = st.session_state.get("vg_sel")
if _detalhar:
    st.divider()
    COLUNAS = {
        "numero": "Processo", "unidade": "Diretoria", "tipo_processo": "Tipo",
        "situacao": "Situação", "responsavel": "Responsável", "link_sei": "SEI",
    }

    def _render_lista(sub, titulo: str, nota: str = "") -> None:
        st.subheader(f"{titulo} — {len(sub)} processo(s)")
        if nota:
            st.caption(nota)
        if sub.empty:
            st.caption("Nenhum processo neste cartão.")
            return
        cols = [
            c for c in
            ["numero", "unidade", "tipo_processo", "situacao", "responsavel", "link_sei"]
            if c in sub.columns
        ]
        mostra = sub[cols].copy()
        mostra["responsavel"] = mostra["responsavel"].fillna("sem responsável")
        st.dataframe(
            mostra.rename(columns=COLUNAS),
            use_container_width=True, hide_index=True, height=420,
            column_config={"SEI": st.column_config.LinkColumn("Abrir", display_text="abrir")},
        )

    if _detalhar == "sem_resp":
        _render_lista(
            sem_all, "Sem responsável/dono",
            "Processos do Controle de Processos sem usuário atribuído no SEI.",
        )
    elif _detalhar == "prioritarios":
        _render_lista(
            df[df["prioridade"].astype(int).eq(1)], "Prioritários",
            "Marcados como prioridade no SEI (Controle de Processos). O cartão do Painel "
            "conta por regra própria do SEI; aqui listamos o que está no Controle.",
        )
    elif _detalhar == "criticos":
        _render_lista(
            criticos_df(df, limiar_padrao()), "Críticos (criticidade)",
            f"Criticidade ≥ {limiar_padrao()} pontos — prioridade, marcadores, "
            "prazo vencido e imobilidade.",
        )
    elif _detalhar == "total":
        _render_lista(
            df, "Processos na base (Controle de Processos)",
            "O cartão mostra o total do Painel do SEI; a lista abaixo é a base do Controle "
            "de Processos — os dois números podem divergir.",
        )
    else:
        _nome = {c[0]: c[1] for linha in LINHAS for c in linha}[_detalhar]
        st.subheader(_nome)
        st.warning(
            "O Painel de Controle do SEI informa apenas o **número agregado** deste cartão. "
            "A lista individual dos processos não vem na extração — consulte o "
            "**Painel de Controle** da diretoria para o detalhe que o SEI oferece."
        )

st.divider()

st.subheader("Período da série histórica")
de, ate = widget_periodo("visao_geral")
st.caption(
    "O período abaixo filtra a **série histórica de produção** (Estatísticas da "
    "Unidade). Os cartões acima refletem o retrato atual do SEI."
)
bloco_serie_producao(de, ate, titulo="Produção no período (Estatísticas da Unidade)")

st.divider()

st.subheader("Sem responsável/dono — por diretoria")
base_counts = df.groupby("unidade").size()
sem_counts = sem_all.groupby("unidade").size()
cols = st.columns(4)
for col, u in zip(cols, [x["sigla"] for x in unidades()]):
    n = int(sem_counts.get(u, 0))
    base = int(base_counts.get(u, 0))
    pct = round(n / base * 100) if base else 0
    col.metric(u, _fmt(n), delta=f"{pct}% de {base}", delta_color="inverse")

st.subheader("Comparativo por diretoria (cartões do painel)")
comp = comparativo_diretorias(painel, df, limiar_padrao())
c1, c2 = st.columns([1.2, 1])
with c1:
    st.dataframe(comp.set_index("unidade").T, use_container_width=True)
with c2:
    st.subheader("Total × sem acompanhamento")
    graf = comp.set_index("unidade")[["Total", "Sem acompanhamento", "Prioritários"]]
    st.plotly_chart(charts.fig_barras_painel(graf, unidades()), use_container_width=True)

st.divider()

c1, c2, c3 = st.columns(3)
with c1:
    st.subheader("Controles de Prazo")
    st.dataframe(
        painel_agregado(painel, "prazos"),
        use_container_width=True, hide_index=True,
    )
with c2:
    st.subheader("Retornos Programados")
    st.dataframe(
        painel_agregado(painel, "retornos"),
        use_container_width=True, hide_index=True,
    )
with c3:
    st.subheader("Blocos de Assinatura")
    st.dataframe(
        painel_agregado(painel, "blocos"),
        use_container_width=True, hide_index=True,
    )

st.subheader("Top processos críticos (Controle de Processos)")
descricao_box(
    "Criticidade ≥ " + str(limiar_padrao()) + " pontos com base em prioridade, "
    "marcadores, prazo vencido e imobilidade. Abaixo, os 8 mais altos.",
    "#EF4444",
)
crit = criticos_df(df, limiar_padrao()).head(8)
if crit.empty:
    st.success("Nenhum processo acima do limiar.")
else:
    mostra = crit[[
        "numero", "unidade", "tipo_processo", "criticidade", "responsavel",
        "situacao", "assunto", "link_sei",
    ]].rename(columns={
        "numero": "Processo", "unidade": "Diretoria", "tipo_processo": "Tipo",
        "criticidade": "Pts", "responsavel": "Responsável", "situacao": "Situação",
        "assunto": "Assunto", "link_sei": "SEI",
    })
    st.dataframe(
        mostra, use_container_width=True, hide_index=True,
        column_config={
            "SEI": st.column_config.LinkColumn("Abrir", display_text="abrir"),
            "Pts": st.column_config.ProgressColumn(
                "Crític.", min_value=0, max_value=100, format="%d"
            ),
        },
    )

st.caption("Fonte: Painel de Controle e Controle de Processos do SEI-MG (extração automática).")
