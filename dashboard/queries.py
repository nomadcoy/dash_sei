from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from cfg import unidades

from db import conectar

TTL = 300


def _df(sql: str, params: tuple = ()) -> pd.DataFrame:
    from db import conectar

    conn = conectar()
    try:
        return pd.read_sql_query(sql, conn, params=params)
    finally:
        conn.close()


@st.cache_data(ttl=TTL, show_spinner=False)
def extracao_atual() -> dict | None:
    df = _df(
        """SELECT (SELECT count(*) FROM processos) AS total_processos,
                  (SELECT MAX(ts_fim) FROM extracoes) AS ts_fim,
                  (SELECT MAX(ts_inicio) FROM extracoes) AS ts_inicio"""
    )
    if df.empty or df.iloc[0]["total_processos"] is None:
        return None
    r = dict(df.iloc[0])
    if r.get("total_processos") == 0:
        return None
    r["fonte"] = "sei"
    ts = r.get("ts_fim") or r.get("ts_inicio")
    try:
        momento = datetime.fromisoformat(ts)
        if momento.tzinfo:
            idade_min = (datetime.now(momento.tzinfo) - momento).total_seconds() / 60
        else:
            idade_min = (datetime.now() - momento).total_seconds() / 60
    except Exception:
        idade_min = None
    r["idade_min"] = idade_min
    r["ts_local"] = _local(ts)
    return r


def extracao_em_andamento() -> bool:
    """True se uma extração está de fato rodando: há registro `em_andamento` no
    banco E o lock em disco aponta para um processo vivo.

    Uma extração órfã (processo morto, registro travado) não bloqueia o botão —
    o lock morto é ignorado.
    """
    from pathlib import Path

    _RAIZ = Path(__file__).resolve().parent.parent

    conn = conectar()
    try:
        row = conn.execute(
            "SELECT id FROM extracoes WHERE status = 'em_andamento' ORDER BY id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return False

    lock = _RAIZ / "data" / "extraindo.pid"
    try:
        pid = int(lock.read_text().strip())
    except Exception:
        return False
    try:
        import os
        os.kill(pid, 0)
        return True
    except Exception:
        return False


@st.cache_data(ttl=TTL, show_spinner=False)
def extracoes_recentes(n: int = 10) -> pd.DataFrame:
    return _df("SELECT * FROM extracoes ORDER BY id DESC LIMIT ?", (n,))


def _local(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        d = datetime.fromisoformat(ts)
        return d.astimezone().strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ts


@st.cache_data(ttl=TTL, show_spinner=False)
def processos_df() -> pd.DataFrame:
    df = _df(
        """SELECT numero, unidade, tipo_processo, assunto, especificacao, situacao,
                  prioridade, marcadores, data_autuacao, data_conclusao,
                  ultima_movimentacao, unidade_atual, responsavel, idas_vindas,
                  sem_atribuicao, criticidade, criticidade_fatores, link_sei,
                  dias_atraso, prazo_vencimento, para_devolver, atualizado_em,
                  eixo
           FROM processos"""
    )
    if df.empty:
        return df
    df["marcadores"] = df["marcadores"].map(
        lambda s: json.loads(s) if isinstance(s, str) and s.startswith("[") else []
    )
    df["sem_atribuicao"] = pd.to_numeric(df["sem_atribuicao"], errors="coerce").fillna(0).astype(int)
    for c in ("data_autuacao", "data_conclusao", "ultima_movimentacao"):
        df[c] = pd.to_datetime(df[c], errors="coerce")
    df["em_aberto"] = df["situacao"].fillna("").str.contains("andamento", case=False)
    df["criticidade"] = pd.to_numeric(df["criticidade"], errors="coerce").fillna(0).astype(int)
    return df


@st.cache_data(ttl=TTL, show_spinner=False)
def painel_por_unidade() -> pd.DataFrame:
    """Cartões e tabelas do Painel de Controle (última extração de cada unidade)."""
    df = _df(
        """SELECT p.* FROM painel_unidades p
           JOIN (SELECT unidade, MAX(extracao_id) AS mid
                 FROM painel_unidades GROUP BY unidade) m
             ON p.unidade = m.unidade AND p.extracao_id = m.mid
           ORDER BY p.unidade"""
    )
    return df


CARTES_PAINEL = [
    ("total", "Total"),
    ("recebidos", "Recebidos"),
    ("gerados", "Gerados"),
    ("nao_visualizados", "Não visualizados"),
    ("sem_acompanhamento", "Sem acompanhamento"),
    ("alterados", "Alterados"),
    ("prioritarios", "Prioritários"),
]


def _painel_int(n) -> int:
    try:
        return int(float(n))
    except (TypeError, ValueError):
        return 0


def painel_kpis(painel: pd.DataFrame) -> dict[str, int]:
    """Soma dos cartões do painel do SEI em toda a superintendência."""
    tot: dict[str, int] = {}
    for chave, _ in CARTES_PAINEL:
        tot[chave] = _painel_int(painel[chave].sum())
    tot["atrasados"] = sum(painel_atrasos(painel).values())
    return tot


def painel_atrasos(painel: pd.DataFrame) -> dict[str, int]:
    """Atrasos/devoluções por unidade, vindos dos Controles de Prazos e Retornos."""
    out: dict[str, int] = {}
    for u in painel["unidade"]:
        n = 0
        for sec in ("prazos", "retornos"):
            for ln in painel_secao(painel, u, sec):
                t = str(ln.get("tipo", "")).lower()
                if "atras" in t or "devolt" in t:
                    n += _painel_int(ln.get("processos"))
        out[u] = n
    return out


def painel_agregado(painel: pd.DataFrame, secao: str) -> pd.DataFrame:
    """Soma uma seção do painel (prazos/retornos/blocos) sobre todas as unidades."""
    chave_num = "blocos" if secao == "blocos" else "processos"
    agg: dict[str, int] = {}
    for u in painel["unidade"]:
        for ln in painel_secao(painel, u, secao):
            tipo = str(ln.get("tipo", "")).strip() or "—"
            agg[tipo] = agg.get(tipo, 0) + _painel_int(ln.get(chave_num))
    seq = pd.DataFrame([{"tipo": k, "processos": v} for k, v in agg.items()])
    if seq.empty:
        return seq
    return seq.sort_values("processos", ascending=False)


def tipos_por_unidade(df: pd.DataFrame, sigla: str, n: int = 15) -> pd.DataFrame:
    sub = df[df["unidade"] == sigla]
    return (
        sub["tipo_processo"].value_counts().head(n)
        .rename_axis("tipo").reset_index(name="processos")
    )


_PADRAO_DEMANDA_EXTERNA = re.compile(
    r"ALMG|Deputad|Vereador|C[âa]mara|Minist[eé]rio P[úu]blico|MPMG|\bMP\b|"
    r"Tribunal de Contas|Prefeitura|Governador|Ouvidoria[dds]?|Procuradoria|DER\b|"
    r"SEINFRA\b",
    re.IGNORECASE,
)


def processos_demandas_externas(df: pd.DataFrame, sigla: str) -> pd.DataFrame:
    """Marca processos cuja especificação/marcador indica demanda de órgão externo."""
    sub = df[df["unidade"] == sigla].copy()
    if sub.empty:
        return sub
    marc = sub["marcadores"].map(lambda m: " ".join(m) if m else "")
    esp = sub["especificacao"].fillna("").astype(str)
    sub["demanda_externa"] = marc.str.contains("DEMANDA", case=False, na=False) | esp.str.contains(
        _PADRAO_DEMANDA_EXTERNA, na=False
    )
    return sub


def criticidade_fatores_unidade(df: pd.DataFrame, sigla: str) -> pd.DataFrame:
    sub = df[df["unidade"] == sigla]
    totais: dict[str, int] = {}
    for s in sub["criticidade_fatores"]:
        try:
            fatores = json.loads(s) if isinstance(s, str) else (s or {})
        except json.JSONDecodeError:
            fatores = {}
        for k, v in (fatores or {}).items():
            totais[k] = totais.get(k, 0) + int(v)
    rotulos = {
        "prioridade": "Prioridade SEI",
        "marcador_critico": "Marcador crítico",
        "sem_andamento": "Sem andamento (parado)",
        "idade": "Idade elevada (tipo)",
        "reprocessamento": "Idas e vindas entre unidades",
        "atraso_prazo": "Prazo vencido (SEI)",
    }
    return pd.DataFrame(
        [
            {"fator": rotulos.get(k, k), "pontos": v}
            for k, v in sorted(totais.items(), key=lambda kv: -kv[1])
        ]
    )


def evolucao_estoque() -> pd.DataFrame:
    """Estoque total por unidade em cada extração de painel (evolução real)."""
    df = _df(
        "SELECT extracao_id, unidade, total, ts FROM painel_unidades WHERE total IS NOT NULL"
    )
    if df.empty:
        return pd.DataFrame(columns=["ts", "unidade", "total"])
    dt = pd.to_datetime(df["ts"], errors="coerce")
    df["ts_txt"] = dt.dt.strftime("%d/%m %H:%M")
    df["total"] = pd.to_numeric(df["total"], errors="coerce").astype("Int64")
    out = (
        df.groupby(["ts_txt", "unidade"], as_index=False)["total"].max()
        .dropna(subset=["total"])
    )
    return out.sort_values(["ts_txt", "unidade"])


def comparativo_diretorias(
    painel: pd.DataFrame, df: pd.DataFrame, limiar: int
) -> pd.DataFrame:
    """Cartões reais do painel + vistos do controle, em uma tabela por diretoria."""
    atras = painel_atrasos(painel)
    linhas = []
    for u in [x["sigla"] for x in unidades()]:
        r = painel[painel["unidade"] == u]
        if r.empty:
            continue
        r = r.iloc[0]
        sub = df[df["unidade"] == u]
        criticos = sub[sub["em_aberto"] & (sub["criticidade"] >= limiar)]
        linhas.append({
            "unidade": u,
            "Total": _painel_int(r.get("total")),
            "Recebidos": _painel_int(r.get("recebidos")),
            "Gerados": _painel_int(r.get("gerados")),
            "Não visualizados": _painel_int(r.get("nao_visualizados")),
            "Sem acompanhamento": _painel_int(r.get("sem_acompanhamento")),
            "Alterados": _painel_int(r.get("alterados")),
            "Prioritários": _painel_int(r.get("prioritarios")),
            "Atrasos de prazo": atras.get(u, 0),
            "Sem responsável": int(sub["sem_atribuicao"].sum()),
            "Críticos": int(len(criticos)),
            "Controle (base)": int(len(sub)),
        })
    return pd.DataFrame(linhas)


def painel_secao(df: pd.DataFrame, sigla: str, secao: str) -> list[dict]:
    """Decodifica a seção JSON de uma unidade (prazos, retornos, blocos, ...)."""
    linha = df[df["unidade"] == sigla]
    if linha.empty:
        return []
    try:
        return json.loads(linha.iloc[0][f"{secao}_json"] or "[]")
    except (KeyError, json.JSONDecodeError):
        return []


def em_aberto_hoje(df: pd.DataFrame) -> pd.Series:
    return df[df["em_aberto"]].groupby("unidade").size()


def serie_mensal(df: pd.DataFrame, meses: int = 12) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["mes", "aberturas", "conclusoes"])
    fim = pd.Period(date.today(), freq="M")
    inicio = fim - (meses - 1)
    ab = (
        df.dropna(subset=["data_autuacao"])
        .groupby(df["data_autuacao"].dt.to_period("M"))
        .size()
    )
    con = (
        df.dropna(subset=["data_conclusao"])
        .groupby(df["data_conclusao"].dt.to_period("M"))
        .size()
    )
    idx = pd.period_range(inicio, fim, freq="M")
    out = pd.DataFrame({"mes": idx})
    out["aberturas"] = out["mes"].map(ab).fillna(0).astype(int)
    out["conclusoes"] = out["mes"].map(con).fillna(0).astype(int)
    out["mes_txt"] = out["mes"].dt.strftime("%m/%Y")
    return out


def serie_em_aberto(df: pd.DataFrame, dias: int = 90) -> pd.DataFrame:
    """Estoque diário = cum(autuações) - cum(conclusões) sobre toda a história.

    Sem data de autuação (controle do SEI), assume estoque constante no nível
    atual a partir da primeira extração registrada.
    """
    if df.empty:
        return pd.DataFrame(columns=["dia", "unidade", "em_aberto"])
    hoje = date.today()

    if df["data_autuacao"].notna().any():
        inicio = min(
            df["data_autuacao"].min(),
            df["data_conclusao"].dropna().min() if df["data_conclusao"].notna().any() else df["data_autuacao"].min(),
        ).date()
        datas = [(inicio + timedelta(days=i)).isoformat() for i in range((hoje - inicio).days + 1)]
        dias_dt = pd.to_datetime(datas)

        def acumulado(serie: pd.Series) -> pd.Series:
            cont = serie.dropna().dt.strftime("%Y-%m-%d").value_counts()
            return cont.reindex(datas, fill_value=0).cumsum()

        frames = []
        for u in sorted(df["unidade"].dropna().unique()):
            sub = df[df["unidade"] == u]
            estoque = (acumulado(sub["data_autuacao"]) - acumulado(sub["data_conclusao"])).clip(lower=0)
            frames.append(
                pd.DataFrame({"dia": dias_dt, "unidade": u, "em_aberto": estoque.values})[-(dias + 1):]
            )
        return pd.concat(frames, ignore_index=True)

    # sem data de autuação: nível atual constante desde a primeira extração
    try:
        ref = pd.to_datetime(df["atualizado_em"]).min()
        inicio = ref.date() if not pd.isna(ref) else hoje
    except Exception:
        inicio = hoje
    if inicio > hoje:
        inicio = hoje
    datas = [(inicio + timedelta(days=i)).isoformat() for i in range((hoje - inicio).days + 1)]
    dias_dt = pd.to_datetime(datas)
    frames = []
    for u in sorted(df["unidade"].dropna().unique()):
        estoque = int(df[(df["unidade"] == u) & df["em_aberto"]].shape[0])
        frames.append(
            pd.DataFrame({"dia": dias_dt, "unidade": u, "em_aberto": estoque})[-(dias + 1):]
        )
    return pd.concat(frames, ignore_index=True)


def kpis_janela(df: pd.DataFrame, inicio: date, fim: date) -> dict:
    ts_ini = pd.Timestamp(inicio)
    fim_ex = pd.Timestamp(fim) + pd.Timedelta(days=1)

    aut = df[df["data_autuacao"].notna()]
    janela = aut[(aut["data_autuacao"] >= ts_ini) & (aut["data_autuacao"] < fim_ex)]

    conc = df[
        df["data_conclusao"].notna()
        & (df["data_conclusao"] >= ts_ini)
        & (df["data_conclusao"] < fim_ex)
    ]
    dur = (conc["data_conclusao"] - conc["data_autuacao"]).dt.days
    return {
        "aberturas": int(len(janela)),
        "concluidos": int(len(conc)),
        "tempo_medio": float(dur.mean()) if len(dur) else None,
    }


def resumo_unidades(df: pd.DataFrame, dias: int = 30) -> pd.DataFrame:
    hoje = date.today()
    inicio = hoje - timedelta(days=dias)
    linhas = []
    siglas = [u["sigla"] for u in unidades()]
    for u in siglas:
        sub = df[df["unidade"] == u]
        abertos = sub[sub["em_aberto"]]
        ts_ini = pd.Timestamp(inicio)
        conc = sub[
            sub["data_conclusao"].notna() & (sub["data_conclusao"] >= ts_ini)
        ]
        idades = abertos["data_autuacao"].dropna()
        idade_media = float(
            ((pd.Timestamp(date.today()) - idades).dt.days).mean()
        ) if len(idades) else 0.0
        linhas.append({
            "unidade": u,
            "em_aberto": int(len(abertos)),
            "concluidos_30d": int(len(conc)),
            "criticos": int((abertos["criticidade"] >= 50).sum()),
            "idade_media": idade_media,
        })
    return pd.DataFrame(linhas)


def criticos_df(
    df: pd.DataFrame,
    limiar: int,
    siglas: list[str] | None = None,
    tipo: str | None = None,
    somente_abertos: bool = True,
) -> pd.DataFrame:
    out = df[df["criticidade"] >= limiar].copy()
    if somente_abertos:
        out = out[out["em_aberto"]]
    if siglas:
        out = out[out["unidade"].isin(siglas)]
    if tipo:
        out = out[out["tipo_processo"] == tipo]
    return out.sort_values("criticidade", ascending=False)


def processos_sem_atribuicao(
    df: pd.DataFrame,
    sigla: str | None = None,
) -> pd.DataFrame:
    out = df[df["sem_atribuicao"] == 1].copy()
    if sigla:
        out = out[out["unidade"] == sigla]
    return out.sort_values(["unidade", "numero"])


def top_marcadores(df: pd.DataFrame, sigla: str, n: int = 12) -> pd.DataFrame:
    sub = df[df["unidade"] == sigla]
    cont: dict[str, int] = {}
    for lista in sub["marcadores"]:
        for m in lista:
            if m:
                cont[m] = cont.get(m, 0) + 1
    tot = pd.DataFrame([{"marcador": k, "processos": v} for k, v in cont.items()])
    if tot.empty:
        return tot
    return tot.sort_values("processos", ascending=False).head(n)


def pontos_por_fator(df: pd.DataFrame) -> pd.DataFrame:
    totais: dict[str, int] = {}
    for s in df["criticidade_fatores"]:
        try:
            fatores = json.loads(s) if isinstance(s, str) else (s or {})
        except json.JSONDecodeError:
            fatores = {}
        for k, v in (fatores or {}).items():
            totais[k] = totais.get(k, 0) + int(v)
    rotulos = {
        "prioridade": "Prioridade SEI",
        "marcador_critico": "Marcador crítico",
        "sem_andamento": "Sem andamento (parado)",
        "idade": "Idade elevada (tipo)",
        "reprocessamento": "Idas e vindas entre unidades",
        "atraso_prazo": "Prazo vencido (SEI)",
    }
    return pd.DataFrame(
        [
            {"fator": rotulos.get(k, k), "pontos": v}
            for k, v in sorted(totais.items(), key=lambda kv: -kv[1])
        ]
    )


@st.cache_data(ttl=TTL, show_spinner=False)
def estatisticas_df() -> pd.DataFrame:
    """Tabelas de Estatística da Unidade (SEI) — última extração de cada unidade."""
    return _df(
        """SELECT e.* FROM estatisticas e
           JOIN (SELECT unidade, MAX(extracao_id) AS mid
                 FROM estatisticas GROUP BY unidade) m
             ON e.unidade = m.unidade AND e.extracao_id = m.mid
           ORDER BY e.unidade, e.periodo_de, e.tabela, e.tipo, e.mes"""
    )
