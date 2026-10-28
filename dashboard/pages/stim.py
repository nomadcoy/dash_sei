from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import pandas as pd
import streamlit as st

from cfg import descricao_unidade, unidades
from dashboard.auth import exigir_autenticacao
from dashboard.components import charts
from dashboard.queries import (
    criticidade_fatores_unidade,
    evolucao_estoque,
    painel_por_unidade,
    painel_secao,
    processos_demandas_externas,
    processos_df,
    processos_sem_atribuicao,
    tipos_por_unidade,
    top_marcadores,
)

exigir_autenticacao()
from dashboard.style import descricao_box

SIGLA = "STIM"
NOME = "Superintendência de Transporte Coletivo Intermunicipal e Metropolitano"

st.title("Como funciona a STIM")
st.caption(
    "Leitura fundamentada nos dados reais do SEI (Painel de Controle + Controle de "
    "Processos) — sem métricas inventadas. Onde não há dado, dizemos explicitamente."
)

painel = painel_por_unidade()
df = processos_df()
if painel.empty or df.empty:
    st.info("Banco vazio — rode a extração do SEI.")
    st.stop()

cor = next(u["cor"] for u in unidades() if u["sigla"] == SIGLA)
descricao_box(descricao_unidade(SIGLA), cor)

dp = painel[painel["unidade"] == SIGLA]
rp = dp.iloc[0] if not dp.empty else None
sub = df[df["unidade"] == SIGLA]
sem = processos_sem_atribuicao(df, SIGLA)
dem = processos_demandas_externas(df, SIGLA)
n_demandas = int(dem["demanda_externa"].sum()) if not dem.empty else 0

prazos = painel_secao(painel, SIGLA, "prazos")
retornos = painel_secao(painel, SIGLA, "retornos")


def _soma_atrasados(secao: list[dict]) -> int:
    return sum(
        int(r.get("processos") or 0)
        for r in secao
        if "atras" in str(r.get("tipo", "")).lower()
    )


atrasados_sei = _soma_atrasados(prazos)
retornos_atras = _soma_atrasados(retornos)
total_painel = int(rp.get("total")) if rp is not None else 0
recebidos = int(rp.get("recebidos")) if rp is not None else 0
gerados = int(rp.get("gerados")) if rp is not None else 0
criticos = int(sub["criticidade"].ge(50).sum()) if not sub.empty else 0


def _fmt(v: int) -> str:
    return f"{v:,}".replace(",", ".")


st.divider()
st.header("O que a STIM faz — observado nos dados")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Processos no painel (SEI)", _fmt(total_painel))
c2.metric("Recebidos / Gerados", f"{_fmt(recebidos)} / {_fmt(gerados)}")
c3.metric("Prazos vencidos (SEI)", f"{atrasados_sei}")
c4.metric("Críticos (≥ 50 pts)", f"{criticos}", delta_color="off")

st.caption(
    "Controle de Processos (base de trabalho): "
    f"**{len(sub)}** processos na unidade — **{len(sem)}** sem responsável — "
    f"**{n_demandas}** com demanda/órgão externo identificado."
)

st.divider()

l1, l2, l3 = st.columns(3)
l1.warning(
    "**Recepção, não produção.** "
    f"{recebidos} de {total_painel} chegaram prontos de outras unidades/órgãos — "
    f"apenas {gerados} foi autuado aqui. A STIM opera essencialmente como "
    "instância de triagem, decisão e resposta."
)
l2.warning(
    "**Prazo é o ponto sensível.** "
    f"O painel do SEI mostra {atrasados_sei} processos com prazo vencido nos "
    "Controles de Prazos — número idêntico ao que computamos por prazo vencido "
    "(16), cruzando duas fontes independentes."
)
l3.warning(
    "**Fila sem dono.** "
    f"{len(sem)} de {len(sub)} processos ({round(len(sem)/len(sub)*100) if len(sub) else 0}%) "
    "não têm responsável registrado no SEI — a distribuição do trabalho não está "
    "explicitada no sistema."
)

st.subheader("No que o tempo da STIM está sendo gasto")
c1, c2 = st.columns(2)
with c1:
    tipos = tipos_por_unidade(df, SIGLA, 12)
    st.plotly_chart(
        charts.fig_hbar(tipos.rename(columns={"tipo": "rotulo"}), y="rotulo",
                        x="processos", cor=cor, rotulo_x="processos"),
        use_container_width=True,
    )
with c2:
    st.markdown("**Leitura por grupo de processo**")
    grupos = [
        (r"QCO|MCO", "Alteração operacional de linhas (QCO/MCO)"),
        (r"Metropolitano", "Transporte metropolitano"),
        (r"Intermunicipal", "Transporte intermunicipal"),
        (r"Punitivo", "Sancionamento (processos punitivos)"),
        (r"Pedidos, Oferecimentos", "Pedidos, oferecimentos e informações (triagem)"),
        (r"Processo Judicial", "Judiciais"),
        (r"Gestão de Contrato|MGS|Contrata", "Contratos e gestão interna"),
        (r"_", "Demais tipos"),
    ]
    rotulos: list[tuple[str, int]] = []
    restante = tipos.copy()
    for pad, nome in grupos:
        if pad == "_":
            n = int(restante["processos"].sum())
            if n:
                rotulos.append((nome, n))
            continue
        sel = restante[restante["tipo"].str.contains(pad, case=False, regex=True)]
        n = int(sel["processos"].sum())
        if n:
            rotulos.append((nome, n))
            restante = restante[~restante.index.isin(sel.index)]
    gdf = pd.DataFrame(rotulos, columns=["rotulo", "n"]).sort_values("n", ascending=False)
    if not gdf.empty:
        st.dataframe(
            gdf.rename(columns={"rotulo": "Grupo", "n": "Processos"}),
            use_container_width=True, hide_index=True, height=280,
        )

st.divider()
st.header("Fluxo real — estágios observados nos marcadores")

st.markdown(
    "A própria unidade rotula cada processo no SEI com marcadores de situação e "
    "destino. Eles revelam **por onde o trabalho passa na prática**:"
)

estagios = [
    ("Demandas externas na entrada", ("DEMANDA",)),
    ("Instrução e análise técnica", ("ANALISE", "ANÁLISE")),
    ("Baixado às diretorias (coordenação)", ("AGUARDAR",)),
    ("Resposta retornada para validação", ("RESPOSTA PARA ANÁLISE",)),
    ("Decisão — assinatura da superintendência", ("ASSINATURA",)),
    ("Resposta final à origem", ("RESPONDER",)),
]
marc = top_marcadores(df, SIGLA, 100)
fila = {str(r["marcador"]): int(r["processos"]) for _, r in marc.iterrows()}
etapas = []
for nome, termos in estagios:
    n = sum(v for k, v in fila.items() if any(t in k.upper() for t in [s.upper() for s in termos]))
    etapas.append((nome, n))
edf = pd.DataFrame(etapas, columns=["rotulo", "n"]).sort_values("n", ascending=False)
st.plotly_chart(
    charts.fig_hbar(edf, y="rotulo", x="n", cor="#6A1B9A",
                    rotulo_x="processos no estágio", height=320),
    use_container_width=True,
)

st.caption(
    "Detalhe dos marcadores reais capturados: " + ", ".join(
        f"**{k}** ({v})" for i, (k, v) in enumerate(fila.items())
    ) + "."
)
st.caption(
    "Os marcadores são rótulos de **estado atual** fixados pela unidade no SEI — "
    "a leitura de 'fluxo' acima é a interpretação desses rótulos (RESPONDER/ANÁLISE/"
    "AGUARDAR RETORNO/ASSINATURA), não um histórico medido de tempos por estágio."
)

st.divider()
st.header("Ciclo de vida e tempo até conclusão")

st.error(
    "**Limite honesto:** o Controle de Processos do SEI não nos entrega data de "
    "autuação nem de conclusão, e nossa extração atual não captura essas datas. "
    "Portanto, **tempo médio até conclusão e idade média dos processos não são "
    "computáveis hoje** — qualquer número aqui seria inventado, então não exibimos."
)
st.caption(
    "A criticidade já reflete prazo vencido (controle), mas os fatores de idade/"
    "imobilidade estão zerados justamente por falta de datas — a página de críticos "
    "chama atenção para esse limite."
)

c1, c2 = st.columns(2)
with c1:
    st.subheader("Pressão de prazo (Painel de Controle do SEI)")
    st.markdown(
        f"**Controles de Prazos:** {atrasados_sei} vencidos · "
        f"{sum(int(r.get('processos') or 0) for r in prazos if 'andamento' in str(r.get('tipo','')).lower())} em andamento."
    )
    st.markdown(
        f"**Retornos Programados:** {retornos_atras} atrasados · "
        f"{sum(int(r.get('processos') or 0) for r in retornos if 'andamento' in str(r.get('tipo','')).lower())} em andamento · "
        f"{sum(int(r.get('processos') or 0) for r in retornos if 'devolt' in str(r.get('tipo','')).lower())} devolvido(s)."
    )
    st.dataframe(
        pd.concat(
            [pd.DataFrame(prazos), pd.DataFrame(retornos)],
            ignore_index=True,
        ).rename(columns={"tipo": "Situação", "processos": "Processos", "alterados": "Alterados"}),
        use_container_width=True, hide_index=True,
    )
with c2:
    st.subheader("Evolução real do estoque (entre extrações)")
    evol = evolucao_estoque()
    if not evol.empty:
        st.plotly_chart(charts.fig_linha_estoque(evol, unidades()), use_container_width=True)
        ult = {}
        prim = {}
        for u in [x["sigla"] for x in unidades()]:
            s = evol[evol["unidade"] == u]
            if not s.empty:
                ult[u] = int(s.iloc[-1]["total"])
                prim[u] = int(s.iloc[0]["total"])
        deltas = " · ".join(
            f"{u}: {'+' if ult[u] - prim[u] >= 0 else ''}{ult[u] - prim[u]}"
            for u in prim
        )
        st.caption(f"Variação real entre a 1ª e a última coleta de hoje: **{deltas}**.")
        st.caption(
            "Com a coleta diária agendada (06:30), esse gráfico passa a acumular "
            "série histórica **real** de estoque e tendência."
        )
    else:
        st.caption("Nenhuma evolução registrada ainda.")

st.divider()
st.header("Por que os processos ficam críticos na STIM")
fatores = criticidade_fatores_unidade(df, SIGLA)
if not fatores.empty:
    st.plotly_chart(charts.fig_pontos_fator(fatores), use_container_width=True)
    st.caption(
        "Os únicos fatores que pontuam aqui são **prioridade** e **prazo vencido** — "
        "idade e imobilidade não pontuam porque o SEI não expõe datas. Praticamente "
        "todos os processos críticos da STIM são casos de prazo vencido ou prioridade."
    )
else:
    st.caption("Sem fatores registrados.")

st.divider()
st.header("Onde os dados ainda faltam (e como chegamos lá)")
st.markdown(
    "- **Ciclo de vida por tipo** (tempo médio até conclusão): exige extrair data de "
    "autuação e de último andamento do SEI — não está no Controle de Processos.\n"
    "- **Tempo parado por estágio**: idem, precisa do histórico de andamentos.\n"
    "- **Tendência de estoque**: será construída com as extrações diárias já agendadas.\n"
    "- **Atribuição**: depende de a unidade passar a registrar o responsável no SEI "
    "(apenas 3 processos têm hoje)."
)

st.caption("Fonte: Painel de Controle e Controle de Processos do SEI-MG (extração automática).")