from __future__ import annotations

import json
import re
from datetime import date, datetime

import pandas as pd

import cfg

DATA_BR = re.compile(r"^(\d{2})/(\d{2})/(\d{4})")


def parse_data(valor: object) -> date | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor).strip()
    if not texto:
        return None
    if DATA_BR.match(texto):
        try:
            return datetime.strptime(texto[:10], "%d/%m/%Y").date()
        except ValueError:
            return None
    try:
        return datetime.fromisoformat(texto[:10]).date()
    except ValueError:
        return None


def _marcadores_lista(valor: object) -> list[str]:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return []
    if isinstance(valor, list):
        return [str(v).strip().upper() for v in valor if str(v).strip()]
    texto = str(valor).strip()
    if not texto:
        return []
    if texto.startswith("["):
        try:
            return [str(v).strip().upper() for v in json.loads(texto) if str(v).strip()]
        except json.JSONDecodeError:
            pass
    return [t.strip().upper() for t in texto.split("|") if t.strip()]


def calcular_criticidades(df: pd.DataFrame, hoje: date | None = None) -> pd.DataFrame:
    """Acrescenta colunas criticidade (0-100), criticidade_fatores, idade_dias,
    dias_sem_andamento e eh_critico ao DataFrame."""
    hoje = hoje or date.today()
    criterios = cfg.criterios()
    pesos: dict[str, int] = criterios.get("pesos") or {}
    marc_crit = {m.upper() for m in criterios.get("marcadores_criticos") or []}

    df = df.copy()
    df["_autuacao"] = df["data_autuacao"].map(parse_data)
    df["_movim"] = df["ultima_movimentacao"].map(parse_data)
    df["_conclusao"] = df["data_conclusao"].map(parse_data)

    df["idade_dias"] = pd.to_numeric(
        df["_autuacao"].map(lambda d: (hoje - d).days if d else None), errors="coerce"
    )
    df["dias_sem_andamento"] = pd.to_numeric(
        [
            (hoje - (m or a)).days if (m or a) else None
            for m, a in zip(df["_movim"], df["_autuacao"])
        ],
        errors="coerce",
    )

    em_aberto = df["situacao"].str.lower().str.contains("andamento", na=False)
    p90_por_tipo: dict[str, float] = {}
    if em_aberto.any():
        idades = df.loc[em_aberto & df["idade_dias"].notna()]
        if not idades.empty:
            p90_por_tipo = (
                idades.groupby("tipo_processo")["idade_dias"].quantile(0.9).to_dict()
            )

    df["marcadores_norm"] = df["marcadores"].map(_marcadores_lista)

    pontuacoes: list[int] = []
    fatores_lista: list[dict] = []

    for _, r in df.iterrows():
        fatores: dict[str, int] = {}

        if int(r.get("prioridade") or 0) == 1:
            fatores["prioridade"] = int(pesos.get("prioridade", 30))

        if marc_crit & set(r["marcadores_norm"]):
            fatores["marcador_critico"] = int(pesos.get("marcador_critico", 25))

        limite = cfg.dias_limite_sem_andamento(r.get("tipo_processo") or "")
        dsa = r.get("dias_sem_andamento")
        if (
            r.get("situacao")
            and "andamento" in str(r.get("situacao")).lower()
            and dsa is not None
            and not pd.isna(dsa)
            and int(dsa) >= limite
        ):
            fatores["sem_andamento"] = int(pesos.get("sem_andamento", 20))

        atraso = r.get("dias_atraso")
        if (
            atraso is not None
            and not pd.isna(atraso)
            and int(atraso) > 0
        ):
            fatores["atraso_prazo"] = int(pesos.get("atraso_prazo", 25))

        idade = r.get("idade_dias")
        p90 = p90_por_tipo.get(r.get("tipo_processo") or "")
        if (
            p90 is not None
            and idade is not None
            and not pd.isna(idade)
            and float(idade) > float(p90)
        ):
            fatores["idade"] = int(pesos.get("idade", 15))

        if int(r.get("idas_vindas") or 0) >= 2:
            fatores["reprocessamento"] = int(pesos.get("reprocessamento", 10))

        pontuacoes.append(sum(fatores.values()))
        fatores_lista.append(fatores)

    df["criticidade"] = pontuacoes
    df["criticidade_fatores"] = [json.dumps(f, ensure_ascii=False) for f in fatores_lista]
    df["eh_critico"] = df["criticidade"] >= cfg.limiar_padrao()

    df = df.drop(columns=["_autuacao", "_movim", "_conclusao"])
    return df


def upsert_processos(conn, df: pd.DataFrame, extracao_id: int, agora_iso: str) -> int:
    """Grava estado atual. O dono (unidade) da primeira aparição é preservado."""
    from db import SCHEMA  # noqa: F401  (garante schema criado)

    colunas = [
        "numero", "unidade", "tipo_processo", "assunto", "especificacao", "situacao",
        "prioridade", "marcadores", "prioridade_nivel", "controle_prazo",
        "prazo_vencimento", "dias_atraso", "para_devolver", "sem_atribuicao",
        "data_autuacao", "data_conclusao",
        "ultima_movimentacao", "unidade_atual", "responsavel", "idas_vindas",
        "criticidade", "criticidade_fatores", "link_sei", "atualizado_em", "extracao_id",
        "eixo",
    ]
    linhas = []
    for _, r in df.iterrows():
        marc = r.get("marcadores_norm", r.get("marcadores", []))
        if isinstance(marc, list):
            marc_json = json.dumps(marc, ensure_ascii=False)
        else:
            marc_json = str(marc) if marc else "[]"
        data_aut = r.get("data_autuacao")
        data_conc = r.get("data_conclusao")
        movim = r.get("ultima_movimentacao")
        atraso = r.get("dias_atraso")
        linhas.append((
            r["numero"],
            r["unidade"],
            r.get("tipo_processo"),
            r.get("assunto"),
            r.get("especificacao"),
            r.get("situacao"),
            int(r.get("prioridade") or 0),
            marc_json,
            r.get("prioridade_nivel"),
            r.get("controle_prazo"),
            r.get("prazo_vencimento"),
            int(atraso) if atraso is not None and not pd.isna(atraso) else None,
            r.get("para_devolver"),
            int(r.get("sem_atribuicao") or 0),
            data_aut.isoformat() if isinstance(data_aut, date) else (data_aut or None),
            data_conc.isoformat() if isinstance(data_conc, date) else (data_conc or None),
            movim.isoformat() if isinstance(movim, date) else (movim or None),
            r.get("unidade_atual"),
            r.get("responsavel"),
            int(r.get("idas_vindas") or 0),
            int(r.get("criticidade") or 0),
            r.get("criticidade_fatores") or "{}",
            r.get("link_sei"),
            agora_iso,
            extracao_id,
            r.get("eixo"),
        ))

    sql = f"""
    INSERT INTO processos ({', '.join(colunas)})
    VALUES ({', '.join('?' for _ in colunas)})
    ON CONFLICT(numero, unidade) DO UPDATE SET
        tipo_processo       = excluded.tipo_processo,
        assunto             = excluded.assunto,
        especificacao       = excluded.especificacao,
        situacao            = excluded.situacao,
        prioridade          = excluded.prioridade,
        marcadores          = excluded.marcadores,
        prioridade_nivel    = excluded.prioridade_nivel,
        controle_prazo      = excluded.controle_prazo,
        prazo_vencimento    = excluded.prazo_vencimento,
        dias_atraso         = excluded.dias_atraso,
        para_devolver       = excluded.para_devolver,
        sem_atribuicao      = excluded.sem_atribuicao,
        data_autuacao       = COALESCE(excluded.data_autuacao, processos.data_autuacao),
        data_conclusao      = excluded.data_conclusao,
        ultima_movimentacao = excluded.ultima_movimentacao,
        unidade_atual       = excluded.unidade_atual,
        responsavel         = excluded.responsavel,
        idas_vindas         = excluded.idas_vindas,
        criticidade         = excluded.criticidade,
        criticidade_fatores = excluded.criticidade_fatores,
        link_sei            = COALESCE(excluded.link_sei, processos.link_sei),
        atualizado_em       = excluded.atualizado_em,
        extracao_id         = excluded.extracao_id,
        eixo                = COALESCE(excluded.eixo, processos.eixo)
    """
    conn.executemany(sql, linhas)
    conn.commit()
    return len(linhas)
