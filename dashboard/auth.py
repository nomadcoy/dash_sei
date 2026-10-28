from __future__ import annotations



import streamlit as st





def exigir_autenticacao() -> None:

    """Garante que a página não renderize sem sessão autenticada.



    Redireciona para o script principal (que exibe a tela de login) e

    interrompe a execução da página.

    """

    if not st.session_state.get("dash_autenticado"):

        st.session_state["dash_autenticado"] = False

        st.switch_page("app.py")

        st.stop()





def esta_autenticado() -> bool:

    return bool(st.session_state.get("dash_autenticado"))