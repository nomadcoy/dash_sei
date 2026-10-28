from __future__ import annotations

import logging
import os
import sys
import traceback
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pandas as pd

_log = logging.getLogger("extractor")


def _classificar_eixo(r: dict) -> str | None:
    """Eixo temático a partir do texto que o SEI entrega no Controle."""
    try:
        import eixos

        return eixos.classificar(
            r.get("tipo_processo"), r.get("especificacao"), r.get("assunto")
        )
    except Exception:
        return None


def processar(
    coletadas: list[dict],
    unidade: str,
    hoje: date | None = None,
) -> pd.DataFrame:
    """Converte registros crus do SEI para o formato do banco.

    - data de autuação/conclusão quando detalhadas
    - marcadores normalizados
    - criticidade recalculada
    """
    import etl

    hoje = hoje or date.today()
    linhas = []
    for r in coletadas:
        situacao = (r.get("situacao") or "").strip() or "Em andamento"
        aut = etl.parse_data(r.get("data_autuacao"))
        mov = etl.parse_data(r.get("ultima_movimentacao"))
        conclusao = etl.parse_data(r.get("data_conclusao"))
        if conclusao is None and "conclu" in situacao.lower() and mov:
            conclusao = mov

        marcadores = [m.strip() for m in (r.get("marcadores") or []) if m.strip()]
        interessados = [i for i in (r.get("interessados") or []) if str(i).strip()]
        venc = etl.parse_data(r.get("prazo_vencimento"))
        responsavel = (r.get("responsavel") or "").strip() or None
        sem_atrib = int(r.get("sem_atribuicao") or 0) or (1 if not responsavel else 0)

        linhas.append({
            "numero": r["numero"],
            "unidade": unidade,
            "tipo_processo": (r.get("tipo_processo") or "").strip() or None,
            "assunto": " | ".join(interessados) if interessados else None,
            "especificacao": (r.get("especificacao") or "").strip() or None,
            "situacao": situacao,
            "prioridade": int(r.get("prioridade") or 0),
            "marcadores": marcadores,
            "prioridade_nivel": (r.get("prioridade_nivel") or "").strip() or None,
            "controle_prazo": (r.get("controle_prazo") or "").strip() or None,
            "prazo_vencimento": venc.isoformat() if venc else None,
            "dias_atraso": int(r.get("dias_atraso") or 0) or None,
            "para_devolver": (r.get("para_devolver") or "").strip() or None,
            "sem_atribuicao": sem_atrib,
            "eixo": _classificar_eixo(r),
            "data_autuacao": aut.isoformat() if aut else None,
            "data_conclusao": conclusao.isoformat() if conclusao else None,
            "ultima_movimentacao": mov.isoformat() if mov else None,
            "unidade_atual": unidade,
            "responsavel": responsavel,
            "idas_vindas": 0,
            "link_sei": r.get("link_sei"),
        })
    df = pd.DataFrame(linhas)
    if df.empty:
        return df
    return etl.calcular_criticidades(df, hoje=hoje)


def _busca_data(celulas: list[str], chave: str = "") -> str | None:
    """Em tabelas sem coluna de data, tenta extrair dd/mm/yyyy da linha."""
    resto = [c for c in (celulas or []) if "/" in c and not any(k in c.lower() for k in ("http", "sei"))]
    for c in resto:
        import re

        m = re.search(r"\b(\d{2}/\d{2}/\d{4})\b", c)
        if m:
            return m.group(1)
    return None


def gravar(db_con, df: pd.DataFrame, extracao_id: int, unidade: str) -> int:
    import etl

    if df.empty:
        return 0
    return etl.upsert_processos(db_con, df, extracao_id, datetime.now().isoformat(timespec="seconds"))