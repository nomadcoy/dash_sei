from __future__ import annotations

import subprocess
import sys
import threading
import time
from pathlib import Path

_RAIZ = Path(__file__).resolve().parent.parent.parent
if str(_RAIZ) not in sys.path:
    sys.path.insert(0, str(_RAIZ))

import streamlit as st

from cfg import RAIZ, unidades
from dashboard.auth import exigir_autenticacao
from dashboard.queries import (
    extracao_atual,
    extracao_em_andamento,
    extracoes_recentes,
    processos_df,
)

exigir_autenticacao()

st.title("Dados & Extração")
st.caption("Saúde da extração, auditoria de contagens e comandos úteis")

ext = extracao_atual()

c1, c2, c3, c4 = st.columns(4)
with c1:
    if ext is None:
        st.error("Sem extrações")
    elif ext["fonte"] == "sei":
        st.success("Fonte: **SEI-MG (real)**")
    else:
        st.warning("Fonte: **sintética** (dev)")
with c2:
    st.metric("Última extração", ext["ts_local"] if ext else "—")
with c3:
    idade = ext.get("idade_min") if ext else None
    st.metric(
        "Idade dos dados",
        f"{int(idade)} min" if idade is not None else "—",
    )
with c4:
    st.metric("Processos na base", ext.get("total_processos", 0) if ext else 0)

if ext and ext.get("status") != "sucesso":
    st.error(f"Última extração: {ext.get('status')} — {ext.get('detalhe')}")

st.subheader("Histórico de extrações")
hist = extracoes_recentes(10)
if hist.empty:
    st.caption("Nenhuma extração registrada.")
else:
    st.dataframe(
        hist.rename(columns={
            "id": "ID", "fonte": "Fonte", "ts_inicio": "Início (UTC)",
            "ts_fim": "Fim (UTC)", "status": "Status",
            "detalhe": "Detalhe", "total_processos": "Processos",
        }),
        use_container_width=True,
        hide_index=True,
    )

st.subheader("Auditoria de contagens")
df = processos_df()
if not df.empty:
    col1, col2 = st.columns(2)
    with col1:
        cont = (
            df.groupby(["unidade", "situacao"]).size()
            .reset_index(name="qtd")
            .rename(columns={"unidade": "Diretoria", "situacao": "Situação", "qtd": "Qtd"})
        )
        st.dataframe(cont, use_container_width=True, hide_index=True)
    with col2:
        cont2 = (
            df.groupby("tipo_processo").size().reset_index(name="qtd")
            .sort_values("qtd", ascending=False)
            .rename(columns={"tipo_processo": "Tipo de processo", "qtd": "Qtd"})
        )
        st.dataframe(cont2, use_container_width=True, hide_index=True, height=300)

    st.subheader("Atualização")

    modo = "só painel" if st.toggle("Modo rápido: atualizar só o Painel de Controle", value=False) else "completa"

    ja_rodando = extracao_em_andamento()
    if ja_rodando:
        st.warning(
            "Já existe uma extração **em andamento** (registro `status=em_andamento`). "
            "Enquanto ela não terminar (ou for cancelada), o botão fica bloqueado para "
            "evitar duas extrações simultâneas — que é o que causava as falhas de troca de unidade."
        )

    botao_ok = st.button(
        "Atualizar dados do SEI agora", type="primary", use_container_width=True,
        disabled=ja_rodando,
    )
    if botao_ok:
        cmd = [sys.executable, "-m", "extractor.main"]
        if modo == "só painel":
            cmd.append("--somente-painel")

        status = st.empty()
        logs = st.empty()
        status.info(f"Extração **{modo}** iniciada — pode levar alguns minutos (Playwright abrindo o SEI)...")
        inicio = time.time()
        resultado: dict = {}

        def _run() -> None:
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True, encoding="utf-8",
                    errors="replace", timeout=1800,
                )
                resultado["ok"] = proc.returncode == 0
                resultado["out"] = (proc.stdout or "")[-3000:]
                resultado["err"] = (proc.stderr or "")[-3000:]
            except subprocess.TimeoutExpired:
                resultado["ok"] = False
                resultado["out"] = ""
                resultado["err"] = "Tempo esgotado (30 min)."
            except Exception as exc:  # noqa: BLE001
                resultado["ok"] = False
                resultado["out"] = ""
                resultado["err"] = str(exc)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        while t.is_alive():
            decorrido = int(time.time() - inicio)
            status.info(
                f"Extração **{modo}** em andamento... **{decorrido}s** decorridos. "
                "Acompanhe o espelhamento do SEI no log abaixo."
            )
            time.sleep(2)

        t.join(timeout=10)
        st.cache_data.clear()

        if resultado.get("ok"):
            status.success(
                f"Extração **{modo}** concluída com sucesso ({(time.time() - inicio):.0f}s). "
                "Cache limpo. A página recarregou com os dados novos."
            )
        else:
            status.error(
                f"Extração falhou após {(time.time() - inicio):.0f}s. "
                "Veja o trecho de erro abaixo e o arquivo `data/logs/extracao.log`."
            )
            logs.code(resultado.get("err") or resultado.get("out") or "Sem saída.", language="log")
        st.rerun()

    if st.button("Limpar cache do dashboard"):
        st.cache_data.clear()
        st.success("Cache limpo. Recarregue a página.")
    st.caption(
        "O botão roda `python -m extractor.main` (ou `--somente-painel`) no mesmo "
        "ambiente. Requer as credenciais do SEI no `.env` e a rede interna liberada."
    )

st.subheader("Logs da extração")
log_path = RAIZ / "data" / "logs" / "extracao.log"
if log_path.exists():
    linhas = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    st.code("\n".join(linhas[-30:]), language="log")
else:
    st.caption("Sem log ainda.")

st.divider()
st.subheader("Comandos")
st.code(
    """# Extração do SEI (manual)
python -m extractor.main

# Regenerar base sintética (apaga dados reais? — exige --sim se houver SEI)
python synthetic/gerar_sinteticos.py

# Subir o dash
python -m streamlit run dashboard/app.py

# Testes
python -m pytest tests/ -q""",
    language="bash",
)
