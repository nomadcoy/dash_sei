from __future__ import annotations

import pandas as pd

SNAP_ABERTOS = "processos_abertos"
SNAP_FECHADOS = "processos_fechados"
SNAP_TRAMITACAO = "processos_tramitacao"
TEMPOS = "tempos_medios"

LIMITE_SUSPEITO = 300.0


def _ano(df: pd.DataFrame) -> pd.Series:
    """Ano a partir de periodo_de ('dd/mm/aaaa')."""
    return df["periodo_de"].astype(str).str[-4:]


def anos_disponiveis(df: pd.DataFrame) -> list[str]:
    a = _ano(df)
    return sorted(x for x in a.unique().tolist() if x.isdigit())


def _filtro(
    df: pd.DataFrame,
    tabela: str,
    unidades: list[str] | None = None,
    anos: list[str] | None = None,
) -> pd.DataFrame:
    m = df["tabela"].eq(tabela)
    if unidades:
        m &= df["unidade"].isin(unidades)
    if anos:
        m &= _ano(df).isin(anos)
    return df[m]


def balanco_unidades(
    df: pd.DataFrame, unidades: list[str], anos: list[str] | None = None
) -> pd.DataFrame:
    """Abertos / Em tramitação / Fechados por diretoria, no período escolhido."""
    linhas = []
    for u in unidades:
        ab = float(_filtro(df, SNAP_ABERTOS, [u], anos)["valor"].sum())
        tr = float(_filtro(df, SNAP_TRAMITACAO, [u], anos)["valor"].sum())
        fe = float(_filtro(df, SNAP_FECHADOS, [u], anos)["valor"].sum())
        denom = fe + ab
        linhas.append({
            "unidade": u,
            "Abertos": int(ab),
            "Em tramitação": int(tr),
            "Fechados": int(fe),
            "Taxa de conclusão (%)": round(fe / denom * 100, 1) if denom else 0.0,
        })
    return pd.DataFrame(linhas)


def snapshot_por_tipo(
    df: pd.DataFrame, tabela: str, unidade: str, anos: list[str] | None = None
) -> pd.DataFrame:
    sub = _filtro(df, tabela, [unidade], anos)
    if sub.empty:
        return pd.DataFrame(columns=["tipo", "total"])
    return (
        sub.groupby("tipo", as_index=False)["valor"].sum()
        .rename(columns={"valor": "total"})
        .sort_values("total", ascending=False)
    )


def tempos_medios_tipos(
    df: pd.DataFrame,
    unidade: str,
    anos: list[str] | None = None,
    incluir_suspeitos: bool = False,
) -> pd.DataFrame:
    """Tempo médio de tramitação por tipo (dias), informado pelo SEI."""
    sub = _filtro(df, TEMPOS, [unidade], anos).copy()
    if sub.empty:
        return pd.DataFrame(columns=["tipo", "dias"])
    if not incluir_suspeitos:
        sub = sub[sub["valor"] < LIMITE_SUSPEITO]
    return (
        sub.groupby("tipo", as_index=False)["valor"].mean()
        .rename(columns={"valor": "dias"})
        .sort_values("dias", ascending=False)
    )


def tempos_medios_resumo(
    df: pd.DataFrame, unidades: list[str], anos: list[str] | None = None
) -> pd.DataFrame:
    linhas = []
    for u in unidades:
        sub = _filtro(df, TEMPOS, [u], anos)
        sub = sub[sub["valor"] < LIMITE_SUSPEITO]
        if sub.empty:
            linhas.append({"unidade": u, "tipos": 0, "mediana_dias": None, "media_dias": None})
            continue
        linhas.append({
            "unidade": u,
            "tipos": int(sub["tipo"].nunique()),
            "mediana_dias": round(float(sub["valor"].median()), 1),
            "media_dias": round(float(sub["valor"].mean()), 1),
        })
    return pd.DataFrame(linhas)


def suspeitos(df: pd.DataFrame, unidade: str, anos: list[str] | None = None) -> int:
    sub = _filtro(df, TEMPOS, [unidade], anos)
    return int((sub["valor"] >= LIMITE_SUSPEITO).sum())
