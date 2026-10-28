from __future__ import annotations

import re

import pandas as pd

_RX_MES = r"^\d{4}-\d{2}$"

DOC = "documentos_gerados"
PRC = "processos_gerados"
EXT = "documentos_externos"

AUTOMATICOS = {"RECIBO ELETRÔNICO DE PROTOCOLO", "CERTIDÃO DE INTIMAÇÃO CUMPRIDA"}


def meses_disponiveis(df: pd.DataFrame) -> list[str]:
    """Meses 'YYYY-MM' presentes nas tabelas mensais do período, ordenados."""
    mes = df["mes"].dropna()
    mes = mes[mes.astype(str).str.match(_RX_MES, na=False)]
    return sorted(mes.astype(str).unique().tolist())


def rotulo_mes(mes: str) -> str:
    """'2024-01' → 'jan/2024'."""
    MESES = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]
    ano, mm = mes.split("-")
    return f"{MESES[int(mm) - 1]}/{ano}"


def linhas_mensais(
    df: pd.DataFrame,
    tabela: str,
    de: str,
    ate: str,
    unidades: list[str] | None = None,
    excluir: set[str] | None = None,
) -> pd.DataFrame:
    """Linhas mensais (mês real) de uma tabela dentro do intervalo [de, ate]."""
    mask = df["tabela"].eq(tabela) & df["mes"].astype(str).str.match(_RX_MES, na=False)
    if unidades:
        mask &= df["unidade"].isin(unidades)
    sub = df[mask]
    sub = sub[(sub["mes"] >= de) & (sub["mes"] <= ate)]
    if excluir:
        sub = sub[~sub["tipo"].astype(str).str.upper().isin(excluir)]
    return sub


def serie_mensal(
    df: pd.DataFrame,
    tabela: str,
    de: str,
    ate: str,
    unidades: list[str] | None = None,
    excluir: set[str] | None = None,
) -> pd.DataFrame:
    """Série (mês, unidade) → soma, para o intervalo e as unidades escolhidas."""
    sub = linhas_mensais(df, tabela, de, ate, unidades, excluir)
    if sub.empty:
        return pd.DataFrame(columns=["mes", "unidade", "quantidade"])
    return (
        sub.groupby(["mes", "unidade"], as_index=False)["valor"].sum()
        .rename(columns={"valor": "quantidade"})
    )


def totais_por_tipo(
    df: pd.DataFrame,
    tabela: str,
    de: str,
    ate: str,
    unidades: list[str] | None = None,
    excluir: set[str] | None = None,
) -> pd.DataFrame:
    """Soma por tipo a partir das linhas mensais do intervalo."""
    sub = linhas_mensais(df, tabela, de, ate, unidades)
    if sub.empty:
        return pd.DataFrame(columns=["tipo", "total"])
    if excluir:
        sub = sub[~sub["tipo"].astype(str).str.upper().isin(excluir)]
    out = (
        sub.groupby("tipo", as_index=False)["valor"].sum()
        .rename(columns={"valor": "total"})
        .sort_values("total", ascending=False)
    )
    return out[out["total"] > 0]


def total_periodo(
    df: pd.DataFrame,
    tabela: str,
    de: str,
    ate: str,
    unidades: list[str] | None = None,
    excluir: set[str] | None = None,
) -> float:
    t = totais_por_tipo(df, tabela, de, ate, unidades, excluir)
    return float(t["total"].sum()) if not t.empty else 0.0


def excluidos_automaticos(
    df: pd.DataFrame,
    de: str,
    ate: str,
    unidades: list[str] | None = None,
) -> float:
    """Soma dos tipos automáticos (que sairemos da contagem) no intervalo."""
    tot = total_periodo(df, DOC, de, ate, unidades, excluir=None)
    com = total_periodo(df, DOC, de, ate, unidades, excluir=AUTOMATICOS)
    return max(0.0, tot - com)


def comparativo_unidades(
    df: pd.DataFrame,
    de: str,
    ate: str,
    unidades: list[str],
    excluir: set[str] | None = None,
) -> pd.DataFrame:
    linhas = []
    for u in unidades:
        d = totais_por_tipo(df, DOC, de, ate, [u], excluir)
        p = totais_por_tipo(df, PRC, de, ate, [u], excluir=None)
        e = totais_por_tipo(df, EXT, de, ate, [u], excluir=None)
        linhas.append({
            "Unidade": u,
            "Documentos gerados": int(d["total"].sum()) if not d.empty else 0,
            "Processos gerados": int(p["total"].sum()) if not p.empty else 0,
            "Documentos externos": int(e["total"].sum()) if not e.empty else 0,
            "Tipos de doc.": int((d["total"] > 0).sum()),
        })
    return pd.DataFrame(linhas)


# ---------------------------------------------------------------------------
# Agrupamento dos tipos de documento em categorias (classificação sobre os
# tipos que o próprio SEI informa — não é estimativa, é agrupamento).
# ---------------------------------------------------------------------------
CATEGORIAS_DOC = [
    ("Protocolo automático (SEI)", r"RECIBO ELETR|CERTID[ÃA]O DE INTIMA[ÇC][ÃA]O CUMPRIDA"),
    ("Recursos humanos", r"^RH |TELETRABALHO|F[ÉE]RIAS|FREQU[ÊE]NCIA|ABONO|AFASTAMENTO|SERVI[ÇC]O REMOTO"),
    ("Comunicações oficiais", r"^OF[ÍI]CIO|E-?MAIL|MEMORANDO|^AVISO|COMUNICA[ÇC][ÃA]O|CIRCULAR|TELEGRAMA|CARTA"),
    ("Notas e relatórios técnicos", r"NOTA T[ÉE]CNICA|NOTA EXPLICATIVA|NOTA DE DILIG|RELAT[ÓO]RIO|INFORMA[ÇC][ÃA]O|PARECER|AN[ÁA]LISE|^NOTA$|ESTUDO|LAUDO"),
    ("Despachos e decisões", r"DESPACHO|^DECIS[ÃA]O|AUTORIZA[ÇC][ÃA]O|^ATO$|RESOLU[ÇC][ÃA]O|REGULAMENTO|ERRATA|HOMOLOGA|NOTIFICA|ORDEM DE SERVI"),
    ("Termos, contratos e editais", r"TERMO|MINUTA|CONTRATO|EDITAL|ADENDO|APOSTIL|ANU[ÊE]NCIA|ADITIVO|CONV[ÊE]NIO|^ATA"),
    ("Certidões e registros", r"CERTID[ÃA]O|CERTIFICADO|CHECK ?LIST|HIST[ÓO]RICO|INTIMA[ÇC][ÃA]O|DECLARA[ÇC][ÃA]O|ATESTADO|QUITA"),
    ("Requerimentos e formulários", r"REQUERIMENTO|FORMUL[ÁA]RIO|PETI[ÇC][ÃA]O|SOLICITA"),
]


def categoria_documento(tipo: str) -> str:
    t = str(tipo).upper()
    for nome, pad in CATEGORIAS_DOC:
        if re.search(pad, t):
            return nome
    return "Outros documentos"


def por_categoria(
    df: pd.DataFrame,
    de: str,
    ate: str,
    unidades: list[str] | None = None,
    excluir: set[str] | None = None,
) -> pd.DataFrame:
    sub = linhas_mensais(df, DOC, de, ate, unidades, excluir)
    if sub.empty:
        return pd.DataFrame(columns=["categoria", "total"])
    sub = sub.copy()
    sub["categoria"] = sub["tipo"].map(categoria_documento)
    return (
        sub.groupby("categoria", as_index=False)["valor"].sum()
        .rename(columns={"valor": "total"})
        .sort_values("total", ascending=False)
    )


def por_categoria_unidade(
    df: pd.DataFrame,
    de: str,
    ate: str,
    unidades: list[str],
    excluir: set[str] | None = None,
) -> pd.DataFrame:
    sub = linhas_mensais(df, DOC, de, ate, unidades, excluir)
    if sub.empty:
        return pd.DataFrame(columns=["unidade", "categoria", "total"])
    sub = sub.copy()
    sub["categoria"] = sub["tipo"].map(categoria_documento)
    return (
        sub.groupby(["unidade", "categoria"], as_index=False)["valor"].sum()
        .rename(columns={"valor": "total"})
    )