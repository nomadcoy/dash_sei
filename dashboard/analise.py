from __future__ import annotations

"""Motor de análise do painel — gera leitura e narrativa em PT-BR a partirdos dados reais extraídos do SEI.

Princípio de honestidade: nenhuma métrica aqui é inventada. Tudo o que esta
camada produz deriva exclusivamente das colunas que a extração realmente
captura; onde falta dado (histórico de tramitação, datas de ciclo de vida),
a função diz explicitamente que não é computável — em vez de preencher.

Não usa API externa nem modelo: é pandas puro sobre o SQLite local.
"""

import json
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

_FUSO = ZoneInfo("America/Sao_Paulo")


def _fmt(n: float | int) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def _pct(parte: float, todo: float) -> str:
    if not todo:
        return "0%"
    return f"{round(parte / todo * 100)}%"


def _hoje() -> datetime:
    return datetime.now(_FUSO)


# --------------------------------------------------------------------------
# Envelhecimento por data de autuação (quando o SEI entrega a data)
# --------------------------------------------------------------------------
def idade_dias_serie(serie: pd.Series) -> pd.Series:
    """Idade em dias a partir de uma série de datas."""
    d = pd.to_datetime(serie, errors="coerce")
    hoje = _hoje().replace(tzinfo=None)
    return (hoje - d).dt.days


def faixas_idade(idade_dias: pd.Series) -> pd.Series:
    """Agrupa idades (dias) em faixas de leitura: ≤7, ≤30, ≤90, ≤180, 180+."""
    return pd.cut(
        idade_dias,
        bins=[-1, 7, 30, 90, 180, float("inf")],
        labels=["≤ 7d", "8–30d", "31–90d", "91–180d", "180d+"],
    )


def envelhecimento_unidade(df: pd.DataFrame, sigla: str) -> pd.DataFrame:
    """Distribuição de idade (pela data de autuação) dos processos da unidade.

    Honesto: marca explicitamente quantos não têm data de autuação no SEI —
    sobre esses não sabemos a idade.
    """
    sub = df[df["unidade"] == sigla].copy()
    if sub.empty:
        return pd.DataFrame(columns=["faixa", "processos", "sem_data"])
    sub["_idade"] = idade_dias_serie(sub.get("data_autuacao"))
    com = sub[sub["_idade"].notna()]
    tot = pd.DataFrame(
        com["_idade"].groupby(faixas_idade(com["_idade"]), observed=False)
        .size().rename_axis("faixa").reset_index(name="processos")
    )
    tot["sem_data"] = 0
    sem_tot = int(sub["_idade"].isna().sum())
    if not tot.empty:
        tot.loc[tot.index[0], "sem_data"] = sem_tot
    elif sem_tot:
        tot = pd.DataFrame({"faixa": ["sem_data"], "processos": [0], "sem_data": [sem_tot]})
    return tot


# --------------------------------------------------------------------------
# Parados / sem movimentação (a partir da última movimentação que capturamos)
# --------------------------------------------------------------------------
def dias_parados_unidade(df: pd.DataFrame, sigla: str) -> pd.DataFrame:
    """Processos da unidade com N+ dias sem movimentação registrada.

    Fonte: 'ultima_movimentacao' — quando existe. Onde não existe, a linha
    entra como 'sem data' (não sabemos quando parou).
    """
    sub = df[df["unidade"] == sigla].copy()
    if sub.empty:
        return pd.DataFrame(columns=["faixa", "processos", "sem_data"])
    mov = pd.to_datetime(sub.get("ultima_movimentacao"), errors="coerce")
    hoje = _hoje().replace(tzinfo=None)
    dias = (hoje - mov).dt.days
    corte = pd.cut(
        dias,
        bins=[-1, 1, 7, 30, 90, float("inf")],
        labels=["≤ 1d", "2–7d", "8–30d", "31–90d", "90d+"],
    )
    out = pd.DataFrame(
        dias.groupby(corte, observed=False).size().rename_axis("faixa")
        .reset_index(name="processos")
    )
    out["sem_data"] = 0
    sem_tot = int(dias.isna().sum())
    if not out.empty:
        out.loc[out.index[0], "sem_data"] = sem_tot
    elif sem_tot:
        out = pd.DataFrame({"faixa": ["sem_data"], "processos": [0], "sem_data": [sem_tot]})
    return out


def parados_ha_unidade(df: pd.DataFrame, sigla: str, n_dias: int = 7) -> int:
    sub = df[df["unidade"] == sigla]
    if sub.empty:
        return 0
    mov = pd.to_datetime(sub.get("ultima_movimentacao"), errors="coerce")
    hoje = _hoje().replace(tzinfo=None)
    dias = (hoje - mov).dt.days
    return int((dias >= n_dias).sum())


# --------------------------------------------------------------------------
# Fluxo entre unidades — a partir do que o SEI realmente diz
# --------------------------------------------------------------------------
_PADRAO_ORIGEM = re.compile(
    r"^\s*(\S.*?)\s+\d{2}/\d{2}/\d{4}", re.IGNORECASE
)


def _origem_de_texto(texto: str | None) -> str | None:
    """Extrai a unidade/origem do texto 'Para Devolver' (ex.: 'SEINFRA/SUBMOB 08/08/2026...')."""
    if not texto:
        return None
    m = _PADRAO_ORIGEM.match(texto)
    if not m:
        return None
    orig = m.group(1).strip()
    if not orig or orig.upper() in ("SEI", "SEI-MG", "PROCESSO"):
        return None
    return orig


def fluxo_unidades(df: pd.DataFrame) -> pd.DataFrame:
    """Processos marcados como 'Para Devolver' com unidade de destino explícita no SEI.

    O texto do controle captura o formato 'UNIDADE_ORIGEM DD/MM/YYYY ...'. Quando a
    origem é legível, registramos o par (unidade atual → destino). Isso é o mais
    próximo de 'fluxo entre unidades' que os dados permitem hoje — não é o histórico
    completo A→B→C, que não capturamos.
    """
    linhas: list[dict] = []
    for _, r in df.iterrows():
        dev = r.get("para_devolver")
        if not dev:
            continue
        dest = _origem_de_texto(str(dev))
        if not dest:
            continue
        linhas.append({"unidade": r.get("unidade"), "destino": dest})
    if not linhas:
        return pd.DataFrame(columns=["unidade", "destino", "processos"])
    out = (
        pd.DataFrame(linhas)
        .value_counts(["unidade", "destino"])
        .rename("processos").reset_index()
    )
    return out.sort_values("processos", ascending=False)


def fluxo_resumo(df: pd.DataFrame, sigla: str) -> pd.DataFrame:
    flx = fluxo_unidades(df)
    if flx.empty:
        return flx
    return flx[flx["unidade"] == sigla]


# --------------------------------------------------------------------------
# Eixos de trabalho — partem do texto real do SEI, sem IA externa
# --------------------------------------------------------------------------
def eixo_do_processo(
    tipo_processo: object, especificacao: object, assunto: object
) -> str:
    """Atribui um eixo temático ao processo (regras declarativas em eixos.py)."""
    import eixos

    return eixos.classificar(tipo_processo, especificacao, assunto)


def eixos_conjunto(df: pd.DataFrame, unidades_meta: list[str]) -> pd.DataFrame:
    """Distribuição dos eixos no conjunto: processos, críticos e sem responsável.

    Usa a coluna 'eixo' quando o ETL registrou; se algum processo ficar sem,
    classifica na hora a partir do texto (fallback idêntico ao do ETL).
    """
    d = df.copy()
    if "eixo" not in d.columns:
        d["eixo"] = None
    falha = d["eixo"].isna() | (d["eixo"].astype(str).str.strip() == "")
    if falha.any():
        d.loc[falha, "eixo"] = [
            eixo_do_processo(t, e, a)
            for t, e, a in zip(
                d.loc[falha, "tipo_processo"],
                d.loc[falha, "especificacao"],
                d.loc[falha, "assunto"],
            )
        ]
    d["eixo"] = d["eixo"].fillna("Outros e temas diversos")

    crit = d["criticidade"] >= 50 if "criticidade" in d else pd.Series(False, index=d.index)
    semr = d["sem_atribuicao"].fillna(0) if "sem_atribuicao" in d else pd.Series(0, index=d.index)

    return (
        d.groupby("eixo")
        .agg(
            processos=("numero", "size"),
            criticos=("numero", lambda s: int(crit[s.index].sum())),
            sem_responsavel=("numero", lambda s: int(semr[s.index].sum())),
        )
        .reset_index()
        .sort_values("processos", ascending=False)
    )


def eixos_unidade(df: pd.DataFrame, sigla: str) -> pd.DataFrame:
    """Eixos da unidade — análogo a eixos_conjunto, filtrado pela diretoria."""
    return eixos_conjunto(df[df["unidade"] == sigla], [])


def narrativa_eixos(df: pd.DataFrame, unidades_meta: list[str]) -> list[dict]:
    """Leitura dos eixos dominantes — o 'no que as diretorias trabalham hoje'."""
    ex = eixos_conjunto(df, unidades_meta)
    if ex.empty:
        return [{"tipo": "info", "texto": "Sem processos classificáveis."}]

    total = int(ex["processos"].sum())
    saida: list[dict] = []
    topo = ex.head(5)
    partes = " · ".join(
        f"**{r['eixo']}** ({_fmt(int(r['processos']))})" for _, r in topo.iterrows()
    )
    saida.append({
        "tipo": "info",
        "texto": (
            f"Distribuição dos **{_fmt(total)}** processos por eixo; os cinco "
            f"maiores concentram o trabalho: {partes}."
        ),
    })

    semr = int(ex["sem_responsavel"].sum())
    if semr:
        saida.append({
            "tipo": "atencao" if semr / max(total, 1) >= 0.3 else "info",
            "texto": (
                f"**{_fmt(semr)}** processos sem responsável registrado "
                f"({_pct(semr, total)}) — onde o dono não está no SEI, o eixo "
                "conta o volume, não a condução."
            ),
        })

    criticos = int(ex["criticos"].sum())
    if criticos:
        mais = ex.sort_values("criticos", ascending=False).iloc[0]
        saida.append({
            "tipo": "alerta" if criticos / max(total, 1) >= 0.1 else "info",
            "texto": (
                f"**{_fmt(criticos)}** processos críticos (criticidade ≥ 50); "
                f"**{mais['eixo']}** concentra **{_fmt(int(mais['criticos']))}**."
            ),
        })
    return saida


# --------------------------------------------------------------------------
# Estágios do fluxo — as etapas onde o processo está (marcadores do SEI)
# --------------------------------------------------------------------------
_ESTAGIOS = [
    (("CONCLUÍDO", "CONCLUIDO", "MONITORAMENTO"), "Concluído / monitoramento"),
    (("JUDICIAL", "DEMANDA"), "Demanda judicial"),
    (("IMPUGNAÇÃO", "IMPUGNACAO", "EDITAL", "LICITAÇÃO", "LICITACAO", "CONSÓRCIO", "CONSORCIO"),
     "Licitação / contrato"),
    (("ASSINATURA", "DELIBERAÇÃO", "DELIBERACAO", "DESPACHO", "EXPEDIR", "DECISÃO", "DECISAO"),
     "Assinatura / deliberação"),
    (("RELATÓRIO", "RELATORIO", "CHECK-LIST", "AVALIAR", "TÉCNICO", "TECNICO", "ANÁLISE", "ANALISE"),
     "Análise técnica"),
    (("INTIMAÇÃO", "INTIMACAO", "CUMPRIMENTO"), "Cumprimento de intimação"),
    (("DELEGATÁRIA", "DELEGATARIA", "PERMISSIONÁRIO", "PERMISSIONARIO"), "Aguardando delegatária/permissionária"),
    (("RETORNO", "AGUARDAR", "AGUARDA", "AGUARDAMOS"), "Aguardando retorno externo"),
    (("RESPOSTA", "RESPONDER", "MANIFESTAÇÃO", "MANIFESTACAO"), "Resposta / manifestação"),
    (("AVISO", "ORIENTAÇÃO", "ORIENTACAO", "CIÊNCIA", "CIENCIA", "VISTA"), "Orientação / ciência"),
    (("PROVIDÊNCIA", "PROVIDENCIA"), "Providências a tomar"),
    (("VEÍCULO", "FROTA", "PEDÁGIO", "PEDAGIO"), "Veículos / frota / pedágio"),
]


def estagio_do_processo(marcadores: object) -> str:
    """Etapa do fluxo em que o processo está, derivada dos marcadores do SEI.

    Os marcadores do Controle de Processos são, na prática, a etapa em que a
    equipe deixou o processo ('AGUARDAR RETORNO', 'RESPONDER',
    'ASSINATURA DA SUPERINTENDENTE', ...). Esta função reduz a lista bruta a
    um estágio legível; onde nenhum marcador casa, diz claramente que a etapa
    não está registrada.
    """
    if isinstance(marcadores, str):
        import json as _json

        texto = marcadores.strip()
        try:
            lista = [str(v).upper() for v in _json.loads(texto)] if texto.startswith("[") else [texto]
        except _json.JSONDecodeError:
            lista = [texto]
    else:
        lista = [str(m).upper() for m in (marcadores or [])]

    for chaves, tag in _ESTAGIOS:
        if any(k in m for m in lista for k in chaves):
            return tag
    return "Outros / sem etapa registrada"


def estagios_unidade(df: pd.DataFrame, sigla: str) -> pd.DataFrame:
    return estagios_conjunto(df[df["unidade"] == sigla])


def estagios_conjunto(df: pd.DataFrame) -> pd.DataFrame:
    """Distribuição dos processos por estágio do fluxo.

    Mostra em que etapa o lote está parado — o retrato do 'onde emperra'.
    Cruzamos com: críticos, sem responsável, prazo vencido e parados 7+ dias.
    """
    d = df.copy()
    d["estagio"] = d["marcadores"].map(estagio_do_processo)
    criticos = d["criticidade"] >= 50 if "criticidade" in d else pd.Series(False, index=d.index)
    semr = d["sem_atribuicao"].fillna(0) if "sem_atribuicao" in d else pd.Series(0, index=d.index)
    atr = d["dias_atraso"].fillna(0) > 0 if "dias_atraso" in d else pd.Series(False, index=d.index)
    mov = pd.to_datetime(d.get("ultima_movimentacao"), errors="coerce")
    hoje = _hoje().replace(tzinfo=None)
    parado = (hoje - mov).dt.days >= 7 if "ultima_movimentacao" in d else pd.Series(False, index=d.index)

    out = (
        d.groupby("estagio")
        .agg(
            processos=("numero", "size"),
            criticos=("numero", lambda s: int(criticos[s.index].sum())),
            sem_responsavel=("numero", lambda s: int(semr[s.index].sum())),
            prazo_vencido=("numero", lambda s: int(atr[s.index].sum())),
            parados_7mais=("numero", lambda s: int(parado[s.index].sum())),
        )
        .reset_index()
        .sort_values("processos", ascending=False)
    )
    return out


def narrativa_gargalos(df: pd.DataFrame) -> list[dict]:
    """Leitura dos estágios dominantes — onde o trabalho está empacado hoje."""
    es = estagios_conjunto(df)
    if es.empty:
        return [{"tipo": "info", "texto": "Sem processos com estágio identificável."}]
    total = int(es["processos"].sum())
    saida: list[dict] = []
    topo = es.head(5)
    partes = " · ".join(
        f"**{r['estagio']}** ({_fmt(int(r['processos']))})" for _, r in topo.iterrows()
    )
    saida.append({
        "tipo": "info",
        "texto": (
            f"Distribuição dos **{_fmt(total)}** processos por estágio do fluxo "
            f"(marcadores do SEI). Onde o trabalho concentra hoje: {partes}."
        ),
    })
    parado = int(es["parados_7mais"].sum())
    if parado:
        top_parado = es.sort_values("parados_7mais", ascending=False).iloc[0]
        saida.append({
            "tipo": "alerta" if parado / max(total, 1) >= 0.4 else "info",
            "texto": (
                f"**{_fmt(parado)}** processos parados há 7+ dias; o estágio "
                f"**{top_parado['estagio']}** concentra **{_fmt(int(top_parado['parados_7mais']))}**."
            ),
        })
    venc = int(es["prazo_vencido"].sum())
    if venc:
        saida.append({
            "tipo": "atencao",
            "texto": f"**{_fmt(venc)}** processos ({_pct(venc, total)}) com prazo já vencido.",
        })
    semd = int(es["sem_responsavel"].sum())
    if semd:
        saida.append({
            "tipo": "atencao" if semd / max(total, 1) >= 0.3 else "info",
            "texto": (
                f"**{_fmt(semd)}** nesses estágios sem responsável registrado no SEI."
            ),
        })
    return saida


# --------------------------------------------------------------------------
# Narrativa automática — frases geradas dos números (sem IA externa)
# --------------------------------------------------------------------------
def narrativa_unidade(df: pd.DataFrame, sigla: str) -> list[dict]:
    """Gera frases analíticas para a unidade, cada uma com sua evidência."""
    sub = df[df["unidade"] == sigla]
    if sub.empty:
        return [{"tipo": "info", "texto": "Sem dados para esta unidade."}]

    total = int(len(sub))
    saida: list[dict] = []

    sem_resp = int(sub["sem_atribuicao"].fillna(0).sum()) if "sem_atribuicao" in sub else 0
    parados = parados_ha_unidade(df, sigla, 7)
    env = envelhecimento_unidade(df, sigla)
    idosos = int(env.loc[env["faixa"] == "90d+", "processos"].sum()) if not env.empty else 0

    if parados:
        saida.append(
            {
                "tipo": "alerta" if parados / max(total, 1) >= 0.5 else "info",
                "texto": (
                    f"**{_fmt(total)}** processos · **{_fmt(parados)}** parados há 7+ "
                    f"dias ({_pct(parados, total)})."
                ),
            }
        )
    else:
        saida.append({"tipo": "info", "texto": f"**{_fmt(total)}** processos em carteira."})

    if sem_resp:
        saida.append(
            {
                "tipo": "atencao" if sem_resp / max(total, 1) >= 0.3 else "info",
                "texto": (
                    f"**{_fmt(sem_resp)}** sem responsável registrado "
                    f"({_pct(sem_resp, total)}) — o dono não está explicitado no SEI."
                ),
            }
        )

    if idosos:
        saida.append(
            {
                "tipo": "alerta",
                "texto": (
                    f"**{_fmt(idosos)}** processos com 90+ dias de idade pela data de "
                    f"autuação — são o núcleo do estoque de longo prazo."
                ),
            }
        )

    sem_data_idade = int(env["sem_data"].sum()) if not env.empty else 0
    if sem_data_idade:
        saida.append(
            {
                "tipo": "info",
                "texto": (
                    f"**{_fmt(sem_data_idade)}** processos sem data de autuação no SEI — "
                    "idade desses não é computável com os dados atuais."
                ),
            }
        )

    flx = fluxo_resumo(df, sigla)
    if not flx.empty:
        topo = flx.head(3)
        partes = " · ".join(
            f"**{r['destino']}** ({_fmt(r['processos'])})" for _, r in topo.iterrows()
        )
        saida.append({"tipo": "fluxo", "texto": f"Fluxo de devolução para: {partes}."})

    return saida


def narrativa_conjunto(df: pd.DataFrame, unidades_meta: list[str]) -> list[dict]:
    """Narrativa de conjunto (todas as diretorias) — leitura do 'todo'."""
    saida: list[dict] = []
    if df.empty:
        return [{"tipo": "info", "texto": "Sem dados na base."}]

    total = int(len(df))
    sem_resp = int(df["sem_atribuicao"].fillna(0).sum()) if "sem_atribuicao" in df else 0
    atrasados = int(df["dias_atraso"].fillna(0).gt(0).sum()) if "dias_atraso" in df else 0
    idosos = 0
    for u in unidades_meta:
        env = envelhecimento_unidade(df, u)
        if not env.empty:
            idosos += int(env.loc[env["faixa"] == "90d+", "processos"].sum())
    parados_geral = sum(parados_ha_unidade(df, u, 7) for u in unidades_meta)

    saida.append(
        {
            "tipo": "info",
            "texto": (
                f"**{_fmt(total)}** processos no conjunto · **{_fmt(atrasados)}** com "
                f"prazo vencido ({_pct(atrasados, total)})."
            ),
        }
    )
    if sem_resp:
        saida.append(
            {
                "tipo": "atencao",
                "texto": (
                    f"**{_fmt(sem_resp)}** processos ({_pct(sem_resp, total)}) seguem "
                    "sem responsável — a atribuição não está registrada no SEI."
                ),
            }
        )
    if parados_geral:
        maior = max(
            ((u, parados_ha_unidade(df, u, 7)) for u in unidades_meta),
            key=lambda kv: kv[1],
        )
        saida.append(
            {
                "tipo": "info",
                "texto": (
                    f"**{_fmt(parados_geral)}** processos parados há 7+ dias; "
                    f"**{maior[0]}** responde por **{_fmt(maior[1])}**."
                ),
            }
        )
    if idosos:
        saida.append(
            {
                "tipo": "alerta",
                "texto": (
                    f"**{_fmt(idosos)}** processos com 90+ dias pela data de autuação — "
                    "indicam envelhecimento do estoque no conjunto."
                ),
            }
        )

    flags_estaticos = [
        ("sem_atribuicao", "atribuição"),
        ("criticidade", "criticidade"),
        ("dias_atraso", "prazo"),
        ("ultima_movimentacao", "última movimentação"),
    ]
    campos_ausentes = [n for c, n in flags_estaticos if c not in df.columns]
    if campos_ausentes:
        saida.append(
            {
                "tipo": "info",
                "texto": (
                    "Não registramos: " + ", ".join(campos_ausentes) + ". "
                    "Onde o dado não entra, não afirmamos."
                ),
            }
        )
    return saida
