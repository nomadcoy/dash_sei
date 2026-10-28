from __future__ import annotations

import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import streamlit as st

from dashboard.auth import exigir_autenticacao
from dashboard.boletim_dados import meses_disponiveis, rotulo_mes
from dashboard.queries import estatisticas_df
from dashboard.relatorio_dados import ORDEM, montar
from dashboard.relatorio_pdf import gerar_pdf_relatorio
from dashboard.relatorio_textos import (
    CREDITO,
    analise_diretoria,
    destaques,
    o_que_e_a_stim,
)
from dashboard.style import descricao_box

exigir_autenticacao()

st.title("Relatório de Transição de Governo")
st.caption(
    "Documento gerencial para a transição da gestão: panorama da produção de "
    "**janeiro de 2024 até o mês mais recente**, com foco no ano corrente, "
    "o que a STIM faz, o volume de trabalho por diretoria e uma síntese técnica. "
    "Tudo derivado das **Estatísticas da Unidade** e do **Controle de Processos** "
    "do SEI-MG — sem métricas inventadas."
)

est = estatisticas_df()
if est is None or est.empty:
    st.info("Banco sem estatísticas — rode a extração com `--estatisticas`.")
    st.stop()

meses = meses_disponiveis(est)
if not meses:
    st.info("Sem meses registrados no banco.")
    st.stop()

# ---------------------------------------------------------------------------
# Filtros
# ---------------------------------------------------------------------------
c1, c2, c3, c4 = st.columns([1, 1, 1.4, 1.6])
de = c1.selectbox("Período — de", meses, index=0, format_func=rotulo_mes)
ate = c2.selectbox("Período — até", meses, index=len(meses) - 1, format_func=rotulo_mes)
unidades_sel = st.multiselect(
    "Unidades", ORDEM, default=ORDEM, key="rel_unidades"
)
incluir_fluxos = st.checkbox(
    "Incluir anexo com os fluxos de processo (STIM)",
    value=True,
    help="Tabela com entrada, etapas e saída de cada tipo de processo, do config/stim_map.yaml.",
)
excluir_auto = st.checkbox(
    "Excluir documentos automáticos do SEI da contagem principal",
    value=True,
    help="Recibo Eletrônico de Protocolo e Certidão de Intimação Cumprida são gerados "
    "pelo próprio sistema. O total com eles continua aparecendo no resumo.",
)

if not unidades_sel:
    st.warning("Selecione ao menos uma unidade.")
    st.stop()
if de > ate:
    st.error("O início do período não pode ser depois do fim.")
    st.stop()

# ---------------------------------------------------------------------------
# Dados + números
# ---------------------------------------------------------------------------
dados = montar(de, ate, unidades_sel, excluir_auto=excluir_auto)
k = dados["kpis"]


def fmt(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


k1, k2, k3, k4, k5 = st.columns(5)
k1.metric("Documentos", f"{k['doc_sem_auto']:,}".replace(",", "."))
k2.metric("Com automáticos", f"{k['doc_com_auto']:,}".replace(",", "."))
k3.metric("Processos gerados", f"{k['proc']:,}".replace(",", "."))
k4.metric("Documentos externos", f"{k['ext']:,}".replace(",", "."))
k5.metric("Tipos de documento", f"{k['n_tipos']}")

st.divider()

# ---------------------------------------------------------------------------
# Sumário executivo
# ---------------------------------------------------------------------------
st.subheader("Sumário executivo")
for frase in destaques(montar("2024-01", meses[-1])):
    descricao_box(frase)

st.divider()

# ---------------------------------------------------------------------------
# Foco no ano corrente
# ---------------------------------------------------------------------------
ano = meses[-1][:4]
dados_ano = montar(f"{ano}-01", meses[-1], ORDEM, excluir_auto)
st.subheader(f"Foco no ano corrente — {ano}")
st.caption(
    f"Produção de janeiro até {rotulo_mes(meses[-1])}. O ano ainda está em curso: "
    "os números refletem apenas o registrado até a extração."
)
ka = dados_ano["kpis"]
c1, c2, c3 = st.columns(3)
c1.metric(f"Documentos em {ano}", f"{ka['doc_sem_auto']:,}".replace(",", "."))
c2.metric(f"Processos em {ano}", f"{ka['proc']:,}".replace(",", "."))
c3.metric(f"Documentos externos em {ano}", f"{ka['ext']:,}".replace(",", "."))
st.dataframe(
    dados_ano["comparativo"].set_index("Unidade"),
    use_container_width=True,
)

st.divider()

# ---------------------------------------------------------------------------
# O que a STIM faz
# ---------------------------------------------------------------------------
st.subheader("O que a STIM faz")
for p in o_que_e_a_stim():
    st.markdown(p)

st.divider()

# ---------------------------------------------------------------------------
# Análise por diretoria
# ---------------------------------------------------------------------------
st.subheader("Análise por diretoria")
dados_full = montar("2024-01", meses[-1])
for u in ORDEM:
    info = dados_full["por_unidade"][u]
    rotulo = f"{u} — {info['nome']} · {info['docs_total']:,} documentos".replace(",", ".")
    with st.expander(rotulo):
        for p in analise_diretoria(u, dados_full):
            st.markdown(p)
        t = info["top_docs"].head(10).rename(
            columns={"tipo": "Tipo de documento", "total": "Quantidade"}
        )
        st.dataframe(t, use_container_width=True, hide_index=True)

st.divider()

# ---------------------------------------------------------------------------
# Geração do PDF
# ---------------------------------------------------------------------------
st.subheader("Gerar o relatório em PDF")
c = st.columns([1.2, 2, 1.2])
if c[1].button("Gerar PDF do Relatório de Transição", type="primary", use_container_width=True):
    with st.spinner("Montando o relatório e convertendo em PDF..."):
        dados_pdf = montar("2024-01", meses[-1], ORDEM, excluir_auto=True)
        pdf = gerar_pdf_relatorio(dados_pdf)
        st.session_state["_rel_pdf"] = pdf

if st.session_state.get("_rel_pdf"):
    st.download_button(
        "Baixar o PDF gerado",
        data=st.session_state["_rel_pdf"],
        file_name=f"relatorio_transicao_{meses[-1].replace('-', '_')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

st.caption(
    "O PDF cobre **jan/2024 até o mês mais recente** e inclui todas as unidades, "
    "independente dos filtros acima (que afetam apenas o que é exibido na tela). "
    "Fonte: Estatísticas da Unidade e Controle de Processos — SEI-MG."
)
st.caption(CREDITO)