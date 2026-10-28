from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import pandas as pd
import streamlit as st

from cfg import unidades
from dashboard.analise import (
    dias_parados_unidade,
    eixo_do_processo,
    eixos_conjunto,
    eixos_unidade,
    envelhecimento_unidade,
    faixas_idade,
    fluxo_resumo,
    fluxo_unidades,
    idade_dias_serie,
    narrativa_conjunto,
    narrativa_eixos,
    narrativa_gargalos,
    narrativa_unidade,
    parados_ha_unidade,
    estagios_conjunto,
    estagios_unidade,
)
from dashboard.auth import exigir_autenticacao
from dashboard.queries import processos_df
from dashboard.style import descricao_box

exigir_autenticacao()

st.title("Panorama das Diretorias")
st.caption(
    "Leitura do **conjunto das diretorias** — não de uma unidade isolada. "
    "Tudo o que aparece aqui sai dos dados reais do SEI (Painel de Controle + "
    "Controle de Processos); onde não há dado, dizemos explicitamente."
)

un_meta = [u["sigla"] for u in unidades()]
df = processos_df()
if df.empty:
    st.info("Banco vazio — rode a extração do SEI.")
    st.stop()

total = int(len(df))
sem_resp = (
    int(df["sem_atribuicao"].fillna(0).sum()) if "sem_atribuicao" in df else 0
)
anos = int(df["data_autuacao"].notna().sum()) if "data_autuacao" in df else 0
prioritarios = (
    int(df["prioridade"].fillna(0).astype(int).eq(1).sum())
    if "prioridade" in df
    else 0
)

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total de processos (SEI)", f"{total:,}".replace(",", "."))
k2.metric("Sem responsável registrado", f"{sem_resp:,}".replace(",", "."))
k3.metric("Prioritários / urgência", f"{prioritarios:,}".replace(",", "."))
k4.metric("Com data de atividade (peticionamento)", f"{anos:,}".replace(",", "."))
st.caption(
    "A tela de Controle de Processos **não expõe data de autuação**; a idade é "
    "computada pela data de *atividade* que o SEI mostra (peticionamento eletrônico: "
    "'Processo Novo' e 'Intercorrente'). Onde não há ícone de peticionamento, não "
    "inventamos a idade."
)

st.divider()

# ---------------------------------------------------------------------------
# Narrativa automática do TODO (gerada a cada render, sem IA externa)
# ---------------------------------------------------------------------------
st.subheader("Leitura automática do conjunto")
itens = narrativa_conjunto(df, un_meta)
for item in itens:
    descricao_box(item["texto"], cor=item.get("tipo", "info"))

st.divider()

# ---------------------------------------------------------------------------
# Estoques e idade por diretoria — usando só o que o SEI entrega
# ---------------------------------------------------------------------------
st.subheader("Estoque e permanência por diretoria")
por_unidade = (
    df.groupby("unidade")
    .agg(total=("numero", "size"), sem_resp=("sem_atribuicao", "sum"))
    .reset_index()
    if "sem_atribuicao" in df
    else df.groupby("unidade").agg(total=("numero", "size")).reset_index()
)
linhas_idade = []
for sig in un_meta:
    sub = df[df["unidade"] == sig]
    idade = idade_dias_serie(sub["data_autuacao"])
    faixa = faixas_idade(idade)
    nde = int(faixa.notna().sum())
    idoso = int((faixa == "90d+").sum())
    linhas_idade.append(
        {"Diretoria": sig, "Processos": nde, "90+ dias": idoso}
    )
idade_df = pd.DataFrame(linhas_idade).set_index("Diretoria")
if "sem_resp" in por_unidade.columns:
    idade_df = idade_df.join(por_unidade.set_index("unidade")[["sem_resp"]].rename(
        columns={"sem_resp": "Sem responsável"}
    ))
st.dataframe(idade_df, use_container_width=True)

# ---------------------------------------------------------------------------
# Envelhecimento — distribuição de faixas por diretoria
# ---------------------------------------------------------------------------
st.subheader("Permanência na carteira")
st.caption(
    "Baseado na data de atividade do SEI (peticionamento eletrônico) — é o mais "
    "próximo de 'há quanto tempo o processo está com a diretoria' que essa tela entrega."
)
with st.expander("Quantos processos por faixa de permanência? (dados que existem)"):
    blocos = []
    for sig in un_meta:
        env = envelhecimento_unidade(df, sig)
        if env.empty:
            blocos.append({"Diretoria": sig, "motor": "sem dados"})
            continue
        linha = {"Diretoria": sig}
        for _, r in env.iterrows():
            linha[f"faixa {r['faixa']}"] = int(r["processos"])
        linha["sem_data_idade"] = int(env["sem_data"].sum())
        blocos.append(linha)
    if blocos:
        st.dataframe(
            pd.DataFrame(blocos).fillna(0).set_index("Diretoria"),
            use_container_width=True,
        )
    else:
        st.caption("Sem envelhecimento computável com os dados atuais.")

# ---------------------------------------------------------------------------
# Eixos de trabalho — distribuição por tema, com drill-down por diretoria
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Eixos de trabalho das diretorias")
itens_eixos = narrativa_eixos(df, un_meta)
for item in itens_eixos:
    descricao_box(item["texto"], cor=item.get("tipo", "info"))

eix = eixos_conjunto(df, un_meta)
st.dataframe(
    eix.rename(columns={
        "eixo": "Eixo de trabalho", "processos": "Processos",
        "criticos": "Críticos", "sem_responsavel": "Sem responsável",
    }),
    use_container_width=True,
    hide_index=True,
)
st.caption(
    "Eixo atribuído por regras sobre o texto do Controle de Processos "
    "(tipo + especificação + assunto) — classificação local, sem IA externa."
)

with st.expander("Comparar eixos por diretoria"):
    linhas_piv = []
    for sig in un_meta:
        for _, r in eixos_unidade(df, sig).iterrows():
            linhas_piv.append({"Diretoria": sig, "Eixo": r["eixo"], "Processos": int(r["processos"])})
    piv_df = pd.DataFrame(linhas_piv)
    if not piv_df.empty:
        tab = piv_df.pivot_table(
            index="Diretoria", columns="Eixo", values="Processos",
            aggfunc="sum", fill_value=0,
        )
        st.dataframe(tab, use_container_width=True)
        try:
            st.bar_chart(piv_df.groupby(["Eixo", "Diretoria"])["Processos"].sum().unstack())
        except Exception:
            st.caption("Gráfico indisponível para esta combinação.")

with st.expander("Abrir processos de um eixo específico"):
    lista_eixos = sorted(eix["eixo"].tolist())
    eixo_escolhido = st.selectbox("Eixo", lista_eixos, label_visibility="collapsed")
    sub = df[df["eixo"] == eixo_escolhido] if "eixo" in df else pd.DataFrame()
    if sub.empty:
        if "eixo" not in df:
            sub = df[df.apply(
                lambda r: eixo_do_processo(
                    r["tipo_processo"], r["especificacao"], r["assunto"]
                ) == eixo_escolhido,
                axis=1,
            )]
        else:
            sub = df[df["eixo"].fillna("") == eixo_escolhido]
    if sub.empty:
        st.caption("Nenhum processo neste eixo.")
    else:
        lista = sub[["numero", "unidade", "tipo_processo", "especificacao", "situacao"]].astype(str)
        st.dataframe(lista, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Gargalos — estágios do fluxo onde os processos estão empacados
# ---------------------------------------------------------------------------
st.divider()
st.subheader("Onde os processos emperram (estágios do fluxo)")
itens_garg = narrativa_gargalos(df)
for item in itens_garg:
    descricao_box(item["texto"], cor=item.get("tipo", "info"))

est = estagios_conjunto(df)
st.dataframe(
    est.rename(columns={
        "estagio": "Estágio / etapa", "processos": "Processos",
        "criticos": "Críticos", "sem_responsavel": "Sem responsável",
        "prazo_vencido": "Prazo vencido", "parados_7mais": "Parados 7+ dias",
    }),
    use_container_width=True,
    hide_index=True,
)
st.caption(
    "Etapa derivada dos **marcadores** que o SEI mostra no processo "
    "('AGUARDAR RETORNO', 'RESPONDER', 'ASSINATURA DA SUPERINTENDENTE'...). "
    "'Outros / sem etapa registrada' = processos sem marcador."
)

with st.expander("Comparar estágios por diretoria"):
    linhas_piv = []
    for sig in un_meta:
        for _, r in estagios_unidade(df, sig).iterrows():
            linhas_piv.append({"Diretoria": sig, "Estágio": r["estagio"], "Processos": int(r["processos"])})
    piv_df = pd.DataFrame(linhas_piv)
    if not piv_df.empty:
        tab = piv_df.pivot_table(
            index="Diretoria", columns="Estágio", values="Processos",
            aggfunc="sum", fill_value=0,
        )
        st.dataframe(tab, use_container_width=True)
        try:
            st.bar_chart(piv_df.groupby(["Estágio", "Diretoria"])["Processos"].sum().unstack())
        except Exception:
            st.caption("Gráfico indisponível para esta combinação.")

with st.expander("Processos em um estágio específico"):
    from dashboard.analise import estagio_do_processo

    lista_est = sorted(est["estagio"].tolist())
    est_escolhido = st.selectbox("Estágio", lista_est, label_visibility="collapsed")
    filtro = df[df["marcadores"].map(estagio_do_processo) == est_escolhido]
    if filtro.empty:
        st.caption("Nenhum processo neste estágio.")
    else:
        lista = filtro[["numero", "unidade", "tipo_processo", "especificacao", "situacao"]].astype(str)
        st.dataframe(lista, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Fluxo entre diretorias (o que vai para devolução e para onde)
# ---------------------------------------------------------------------------
st.subheader("Fluxo entre diretorias")
flx = fluxo_unidades(df)
if flx.empty:
    st.caption(
        "Sem fluxo de devolução legível no SEI — onde o dado não entra, não afirmamos."
    )
else:
    st.dataframe(
        flx.rename(columns={
            "unidade": "De", "destino": "Para", "processos": "Processos"
        }),
        use_container_width=True,
        hide_index=True,
    )

st.divider()
st.subheader("Leitura por diretoria")
para_sigla = st.selectbox(
    "Diretoria", un_meta, label_visibility="collapsed",
    format_func=lambda s: f"{s} — {next((u['nome'] for u in unidades() if u['sigla'] == s), s)}",
)
for item in narrativa_unidade(df, para_sigla):
    descricao_box(item["texto"], cor=item.get("tipo", "info"))

parados = parados_ha_unidade(df, para_sigla, 7)
st.caption(
    f"Processos da {para_sigla} parados há 7+ dias (pela última movimentação): "
    f"**{parados}**."
)

st.caption(
    "Fonte: Painel de Controle e Controle de Processos do SEI-MG (extração automática). "
    "Narrativa gerada localmente em PT-BR a partir dos números — sem afirmações inventadas."
)
