from __future__ import annotations

import hmac
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import streamlit as st

from cfg import dash_credenciais, limiar_padrao, unidades
from dashboard.queries import extracao_atual
from dashboard.style import cabecalho_institucional, chips_unidades, injetar_css

st.set_page_config(
    page_title="Painel de Controle de Processos — Gestão à Vista · SEINFRA/SEI-MG",
    layout="wide",
    initial_sidebar_state="expanded",
)

injetar_css()


def _tela_login() -> None:
    _usuario, _senha = dash_credenciais()
    cabecalho_institucional()
    st.html(
        """<style>
        [data-testid="stSidebarNav"] { display: none !important; }
        [data-testid="stAppDeployButton"] { display: none !important; }
        </style>"""
    )
    st.title("Painel de Controle de Processos — Gestão à Vista")
    st.caption("Acesso restrito · SEINFRA / SEI-MG")
    _, meio, _ = st.columns([1, 1.2, 1])
    with meio:
        with st.form("login"):
            u = st.text_input("Usuário")
            s = st.text_input("Senha", type="password")
            ok = st.form_submit_button("Entrar", type="primary")
        if ok:
            valido = bool(_usuario) and hmac.compare_digest(
                u.strip(), _usuario
            ) and hmac.compare_digest(s, _senha)
            if valido:
                st.session_state["dash_autenticado"] = True
                st.rerun()
            else:
                st.error("Usuário ou senha incorretos.")
    st.stop()


if not st.session_state.get("dash_autenticado"):
    _tela_login()

cabecalho_institucional()
chips_unidades()

paginas = [
    st.Page("pages/visao_geral.py", title="Visão Geral", default=True),
    st.Page("pages/painel.py", title="Painel de Controle", url_path="painel"),
    st.Page("pages/diretorias.py", title="Diretorias"),
    st.Page("pages/gestao.py", title="Indicadores de Gestão", url_path="gestao"),
    st.Page("pages/criticos.py", title="Processos Críticos"),
    st.Page("pages/panorama.py", title="Panorama das Diretorias", url_path="panorama"),
    st.Page("pages/boletim.py", title="Boletim de Produtividade", url_path="boletim"),
    st.Page("pages/relatorio.py", title="Transição de Governo", url_path="transicao"),
    st.Page("pages/dados.py", title="Dados & Extração"),
]
navegacao = st.navigation(paginas)

with st.sidebar:
    if st.button("Sair (encerrar sessão)", use_container_width=True):
        st.session_state["dash_autenticado"] = False
        st.rerun()
    st.markdown("### Status dos dados")
    ext = extracao_atual()
    if ext is None:
        st.warning("Nenhuma extração registrada.")
        st.caption("Rode: `python synthetic/gerar_sinteticos.py`")
    else:
        fonte = ext.get("fonte")
        if fonte == "sei":
            st.success("Sincronizado com o SEI")
        else:
            st.warning("Base sintética (desenvolvimento)")
        st.caption(f"Última extração: **{ext.get('ts_local')}** · {ext.get('total_processos', 0)} processos")
        idade = ext.get("idade_min")
        if fonte == "sei" and idade is not None and idade > 120:
            st.error(f"Dados com {int(idade // 60)}h de atraso")
    st.divider()
    st.caption(
        f"**Escopo:** DGTI · DGTM · DRTC · STIM\n\n"
        f"**Limiar de críticos:** {limiar_padrao()} pts\n\n"
        f"Fonte: SEI-MG / {unidades() and 'SEINFRA'}"
    )

navegacao.run()
