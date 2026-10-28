from __future__ import annotations

from datetime import datetime

import pandas as pd

from dashboard.boletim_dados import (
    DOC,
    EXT,
    PRC,
    por_categoria,
    rotulo_mes,
    serie_mensal,
    totais_por_tipo,
    total_periodo,
)
from dashboard.gestao_dados import balanco_unidades, tempos_medios_resumo

CORES_TIPO = {
    "info": "#1D4E89",
    "positivo": "#2E7D32",
    "atencao": "#B45309",
    "alerta": "#DC2626",
}


def _fmt(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def _pct(parte: float, todo: float) -> str:
    return f"{parte / todo * 100:.0f}%" if todo else "0%"


def texto_analitico(
    df: pd.DataFrame,
    de: str,
    ate: str,
    unidades: list[str],
    excluir: set[str] | None = None,
) -> list[dict]:
    """Frases analíticas do período, geradas só dos números (sem IA externa).

    Cada item: {"tipo": info|positivo|atencao|alerta, "texto": str com **negrito**}.
    """
    ser = serie_mensal(df, DOC, de, ate, unidades, excluir)
    if ser.empty:
        return [{
            "tipo": "info",
            "texto": f"Sem documentos registrados entre **{rotulo_mes(de)}** e "
                     f"**{rotulo_mes(ate)}** para as unidades selecionadas.",
        }]

    tot_mes = ser.groupby("mes")["quantidade"].sum().sort_index()
    n = len(tot_mes)
    total = float(tot_mes.sum())
    media = total / n

    saida: list[dict] = [{
        "tipo": "info",
        "texto": (
            f"**{_fmt(total)}** documentos gerados entre **{rotulo_mes(de)}** e "
            f"**{rotulo_mes(ate)}** — {n} {'meses' if n > 1 else 'mês'}, "
            f"média de **{_fmt(media)}** por mês."
        ),
    }]

    mes_corrente = datetime.now().strftime("%Y-%m")
    if n and tot_mes.index[-1] >= mes_corrente:
        saida.append({
            "tipo": "atencao",
            "texto": (
                f"**{rotulo_mes(tot_mes.index[-1])}** ainda está em curso - os números "
                "desse mês refletem só o que foi registrado até hoje e tendem a ficar "
                "abaixo dos meses fechados."
            ),
        })

    if n >= 6:
        ult = float(tot_mes.iloc[-3:].mean())
        ant = float(tot_mes.iloc[-6:-3].mean())
        var = (ult - ant) / ant * 100 if ant else 0.0
        saida.append({
            "tipo": "positivo" if var >= 0 else "atencao",
            "texto": (
                f"Média dos **3 últimos meses** ({_fmt(ult)}) está **{abs(var):.1f}% "
                f"{'acima' if var >= 0 else 'abaixo'}** da média dos 3 meses "
                f"anteriores ({_fmt(ant)})."
            ),
        })
    elif n >= 2:
        pri = float(tot_mes.iloc[0])
        ult = float(tot_mes.iloc[-1])
        var = (ult - pri) / pri * 100 if pri else 0.0
        saida.append({
            "tipo": "positivo" if var >= 0 else "atencao",
            "texto": (
                f"De **{rotulo_mes(tot_mes.index[0])}** ({_fmt(pri)}) para "
                f"**{rotulo_mes(tot_mes.index[-1])}** ({_fmt(ult)}): variação de "
                f"**{var:+.1f}%**."
            ),
        })

    if n >= 2 and tot_mes.idxmax() != tot_mes.idxmin():
        saida.append({
            "tipo": "info",
            "texto": (
                f"Maior produção em **{rotulo_mes(tot_mes.idxmax())}** "
                f"({_fmt(float(tot_mes.max()))}); menor em "
                f"**{rotulo_mes(tot_mes.idxmin())}** "
                f"({_fmt(float(tot_mes.min()))})."
            ),
        })

    por_u = ser.groupby("unidade")["quantidade"].sum().sort_values(ascending=False)
    if len(por_u) >= 2:
        lider, menor = por_u.index[0], por_u.index[-1]
        saida.append({
            "tipo": "info",
            "texto": (
                f"**{lider}** lidera com **{_fmt(float(por_u.iloc[0]))}** documentos "
                f"(**{_pct(float(por_u.iloc[0]), total)}** do período); menor volume: "
                f"**{menor}** (**{_pct(float(por_u.iloc[-1]), total)}**)."
            ),
        })
    else:
        saida.append({
            "tipo": "info",
            "texto": (
                f"Unidade **{por_u.index[0]}**: **{_fmt(float(por_u.iloc[0]))}** "
                f"documentos no período."
            ),
        })

    tp = totais_por_tipo(df, DOC, de, ate, unidades, excluir)
    if not tp.empty and total:
        topo = tp.iloc[0]
        saida.append({
            "tipo": "info",
            "texto": (
                f"Tipo mais frequente: **{topo['tipo']}** — "
                f"**{_fmt(float(topo['total']))}** documentos "
                f"(**{_pct(float(topo['total']), total)}** do total)."
            ),
        })

    prc = total_periodo(df, PRC, de, ate, unidades, None)
    ext = total_periodo(df, EXT, de, ate, unidades, None)
    partes = [f"**{_fmt(prc)}** processos gerados"]
    if prc:
        partes.append(f"em média **{total / prc:.1f}** documentos por processo")
    if ext:
        partes.append(f"**{_fmt(ext)}** documentos externos")
    saida.append({"tipo": "info", "texto": " · ".join(partes) + "."})

    return saida


def _junta(itens: list[str]) -> str:
    if not itens:
        return ""
    if len(itens) == 1:
        return itens[0]
    return ", ".join(itens[:-1]) + " e " + itens[-1]


def sintese_final(
    df: pd.DataFrame,
    de: str,
    ate: str,
    unidades: list[str],
    excluir: set[str] | None = None,
) -> list[dict]:
    """Síntese informativa do conjunto (STIM + diretorias), gerada só dos números.

    Serve para leitura da totalidade: volumes, mix de categorias, liderança,
    eficiência e o perfil de cada diretoria. Sem estimativas.
    """
    doc = total_periodo(df, DOC, de, ate, unidades, excluir)
    prc = total_periodo(df, PRC, de, ate, unidades, None)
    ext = total_periodo(df, EXT, de, ate, unidades, None)
    if not doc and not prc and not ext:
        return [{
            "tipo": "info",
            "texto": f"Sem produção registrada entre **{rotulo_mes(de)}** e "
                     f"**{rotulo_mes(ate)}** para as unidades selecionadas.",
        }]

    anos = [str(a) for a in range(int(de[:4]), int(ate[:4]) + 1)]
    saida: list[dict] = []

    # --- visão geral do conjunto ---
    ser = serie_mensal(df, DOC, de, ate, unidades, excluir)
    n_meses = int(ser["mes"].nunique()) if not ser.empty else 0
    media = doc / n_meses if n_meses else 0
    saida.append({"tipo": "info", "texto": (
        f"**Síntese do conjunto.** No período de **{rotulo_mes(de)}** a "
        f"**{rotulo_mes(ate)}** ({n_meses} {'meses' if n_meses != 1 else 'mês'}), as "
        f"unidades {', '.join(unidades)} geraram **{_fmt(doc)}** documentos e "
        f"**{_fmt(prc)}** processos, e trataram **{_fmt(ext)}** documentos de origem "
        f"externa — uma média de **{_fmt(media)}** documentos por mês."
    )})

    # --- mix de categorias ---
    cat = por_categoria(df, de, ate, unidades, excluir)
    if not cat.empty:
        tot_cat = float(cat["total"].sum())
        top = [f"**{r['categoria']}** ({_pct(float(r['total']), tot_cat)})"
               for _, r in cat.head(3).iterrows()]
        saida.append({"tipo": "info", "texto": (
            "A produção documental se concentra em " + _junta(top) + "."
        )})

    # --- liderança de volume ---
    vol = {u: total_periodo(df, DOC, de, ate, [u], excluir) for u in unidades}
    ordem = sorted(vol.items(), key=lambda kv: kv[1], reverse=True)
    if len(ordem) >= 2 and doc:
        lid, lv = ordem[0]
        ult, uv = ordem[-1]
        saida.append({"tipo": "info", "texto": (
            f"A **{lid}** lidera o volume documental com **{_fmt(lv)}** documentos "
            f"(**{_pct(lv, doc)}** do total); o menor volume é da **{ult}** "
            f"(**{_fmt(uv)}**)."
        )})

    # --- eficiência ---
    res = tempos_medios_resumo(df, unidades, anos)
    bal = balanco_unidades(df, unidades, anos)
    if not res.empty and res["mediana_dias"].notna().any():
        r = res.dropna(subset=["mediana_dias"])
        fast = r.loc[r["mediana_dias"].idxmin()]
        slow = r.loc[r["mediana_dias"].idxmax()]
        saida.append({"tipo": "info", "texto": (
            "No tempo de tramitação informado pelo SEI, a mediana vai de "
            f"**{fast['mediana_dias']:.0f} dias** na **{fast['unidade']}** a "
            f"**{slow['mediana_dias']:.0f} dias** na **{slow['unidade']}**."
        )})
    if not bal.empty:
        b = bal[bal["Taxa de conclusão (%)"] > 0]
        if not b.empty:
            mx = b.loc[b["Taxa de conclusão (%)"].idxmax()]
            mn = b.loc[b["Taxa de conclusão (%)"].idxmin()]
            saida.append({"tipo": "info", "texto": (
                "A taxa de conclusão (fechados ÷ fechados + abertos) varia de "
                f"**{mn['Taxa de conclusão (%)']:.0f}%** na **{mn['unidade']}** a "
                f"**{mx['Taxa de conclusão (%)']:.0f}%** na **{mx['unidade']}**."
            )})

    # --- perfil por diretoria ---
    for u in unidades:
        d = total_periodo(df, DOC, de, ate, [u], excluir)
        p = total_periodo(df, PRC, de, ate, [u], None)
        e = total_periodo(df, EXT, de, ate, [u], None)
        c = por_categoria(df, de, ate, [u], excluir)
        cat_u = c.iloc[0]["categoria"] if not c.empty else "—"
        tv = res[res["unidade"] == u]["mediana_dias"].tolist() if not res.empty else []
        t_txt = f"{tv[0]:.0f} dias" if tv and pd.notna(tv[0]) else "sem dado"
        cv = bal[bal["unidade"] == u]["Taxa de conclusão (%)"].tolist() if not bal.empty else []
        c_txt = f"{cv[0]:.0f}%" if cv and cv[0] else "—"
        saida.append({"tipo": "info", "texto": (
            f"**{u}** — **{_fmt(d)}** documentos, **{_fmt(p)}** processos e "
            f"**{_fmt(e)}** documentos externos; categoria predominante "
            f"**{cat_u}**; tempo mediano de tramitação **{t_txt}**; "
            f"conclusão **{c_txt}**."
        )})

    return saida
