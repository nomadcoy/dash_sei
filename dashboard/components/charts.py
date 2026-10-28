from __future__ import annotations



import pandas as pd

import plotly.express as px

import plotly.graph_objects as go



from cfg import cor_unidade, unidades



CORES_UNIDADE = {u["sigla"]: u["cor"] for u in unidades()}

AZUL, VERDE, LARANJA, ROXO, VERMELHO = "#1D4E89", "#2E7D32", "#B45309", "#6A1B9A", "#DC2626"

CINZA = "#94A3B8"



_LAYOUT = dict(

    margin=dict(l=20, r=20, t=44, b=20),

    paper_bgcolor="rgba(0,0,0,0)",

    plot_bgcolor="rgba(0,0,0,0)",

    font=dict(family="Inter, Segoe UI, sans-serif", size=14, color="#1E293B"),

    legend=dict(orientation="h", y=1.14, font=dict(family="Inter, Segoe UI, sans-serif", color="#1E293B", size=13)),

    height=360,

    xaxis=dict(

        gridcolor="#E2E8F0",

        zerolinecolor="#CBD5E1",

        tickfont=dict(family="Inter, Segoe UI, sans-serif", color="#475569", size=12),

        title_font=dict(family="Inter, Segoe UI, sans-serif", color="#1E293B", size=13),

    ),

    yaxis=dict(

        gridcolor="#E2E8F0",

        zerolinecolor="#CBD5E1",

        tickfont=dict(family="Inter, Segoe UI, sans-serif", color="#475569", size=12),

        title_font=dict(family="Inter, Segoe UI, sans-serif", color="#1E293B", size=13),

    ),

)





def _fin(fig: go.Figure, height: int | None = None) -> go.Figure:

    layout = dict(_LAYOUT)

    if height is not None:

        layout["height"] = height

    fig.update_layout(**layout)

    return fig





def fig_serie_mensal(mensal: pd.DataFrame) -> go.Figure:

    df = mensal.melt(id_vars=["mes_txt"], value_vars=["aberturas", "conclusoes"],

                     var_name="tipo", value_name="quantidade")

    df["tipo"] = df["tipo"].map({"aberturas": "Aberturas", "conclusoes": "Conclusões"})

    fig = px.bar(

        df, x="mes_txt", y="quantidade", color="tipo", barmode="group",

        color_discrete_map={"Aberturas": AZUL, "Conclusões": VERDE},

        labels={"mes_txt": "", "quantidade": "", "tipo": ""},

    )

    return _fin(fig.update_traces(hovertemplate="%{x}: %{y}"))





def fig_em_aberto(serie: pd.DataFrame) -> go.Figure:

    fig = px.line(

        serie, x="dia", y="em_aberto", color="unidade",

        color_discrete_map=CORES_UNIDADE,

        labels={"dia": "", "em_aberto": "Processos em aberto", "unidade": ""},

        markers=False,

    )

    fig.update_traces(line=dict(width=2.5))

    return _fin(fig)





def fig_donut(valores: pd.Series, cores: list[str] | None = None, rotulos=None) -> go.Figure:

    fig = go.Figure(go.Pie(

        labels=rotulos if rotulos is not None else valores.index,

        values=valores.values,

        hole=0.55,

        marker=dict(colors=cores),

        textinfo="label+percent",

        hovertemplate="%{label}: %{value} (%{percent})<extra></extra>",

    ))

    return _fin(fig)





def fig_top_tipos(df: pd.DataFrame, n: int = 10) -> go.Figure:

    cont = (

        df.groupby(["tipo_processo", "unidade"]).size().reset_index(name="qtd")

        .sort_values("qtd", ascending=True).tail(n)

    )

    fig = px.bar(

        cont, x="qtd", y="tipo_processo", color="unidade",

        color_discrete_map=CORES_UNIDADE, orientation="h",

        labels={"qtd": "", "tipo_processo": "", "unidade": ""},

    )

    return _fin(fig, height=max(340, 26 * len(cont) + 80))





def fig_top_assuntos(df: pd.DataFrame, n: int = 10) -> go.Figure:

    cont = (

        df.groupby("assunto").size().reset_index(name="qtd")

        .sort_values("qtd", ascending=True).tail(n)

    )

    cont["rotulo"] = cont["assunto"].str.slice(0, 70)

    fig = px.bar(

        cont, x="qtd", y="rotulo", orientation="h",

        color_discrete_sequence=[AZUL],

        labels={"qtd": "", "rotulo": ""},

    )

    return _fin(fig, height=max(340, 26 * len(cont) + 80))





def fig_idade_hist(df: pd.DataFrame) -> go.Figure:

    abertos = df[df["em_aberto"]].copy()

    abertos["idade_dias"] = (pd.Timestamp.now().normalize() - abertos["data_autuacao"]).dt.days

    fig = px.histogram(

        abertos, x="idade_dias", nbins=30,

        color_discrete_sequence=[AZUL],

        labels={"idade_dias": "Idade do processo (dias)", "count": ""},

    )

    return _fin(fig)





def fig_sankey(df: pd.DataFrame) -> go.Figure:

    abertos = df[df["em_aberto"]].copy()

    cont = (

        abertos.groupby(["unidade", "unidade_atual"]).size().reset_index(name="qtd")

        .sort_values("qtd", ascending=False)

    )

    if cont.empty:

        return _fin(go.Figure())

    nos = sorted(set(cont["unidade"]) | set(cont["unidade_atual"]))

    idx = {n: i for i, n in enumerate(nos)}

    cores_no = []

    for n in nos:

        c = cor_unidade(n)

        cores_no.append(c if c != "#64748B" else CINZA)

    fig = go.Figure(go.Sankey(

        node=dict(

            label=[f" {n} " for n in nos],

            color=[cores_no[i] for i in range(len(nos))],

            pad=18, thickness=16,

        ),

        link=dict(

            source=[idx[s] for s in cont["unidade"]],

            target=[idx[t] for t in cont["unidade_atual"]],

            value=cont["qtd"],

            color=[

                f"rgba{tuple(int(cor_unidade(s)[i:i+2], 16) for i in (1, 3, 5)) + (0.35,)}"

                for s in cont["unidade"]

            ],

        ),

    ))

    return _fin(fig, height=380)





def fig_tempo_medio(df: pd.DataFrame, n: int = 12) -> go.Figure:

    conc = df[df["data_conclusao"].notna()].copy()

    conc["dias"] = (conc["data_conclusao"] - conc["data_autuacao"]).dt.days

    cont = (

        conc.groupby("tipo_processo")["dias"].mean().reset_index(name="dias")

        .sort_values("dias", ascending=True).tail(n)

    )

    fig = px.bar(

        cont, x="dias", y="tipo_processo", orientation="h",

        color_discrete_sequence=[VERDE],

        labels={"dias": "dias (média)", "tipo_processo": ""},

    )

    return _fin(fig, height=max(340, 26 * len(cont) + 80))





def fig_idade_aberto_por_tipo(df: pd.DataFrame, n: int = 12) -> go.Figure:

    ab = df[df["em_aberto"]].copy()

    ab["idade_dias"] = (pd.Timestamp.now().normalize() - ab["data_autuacao"]).dt.days

    cont = (

        ab.groupby("tipo_processo")["idade_dias"].mean().reset_index(name="dias")

        .sort_values("dias", ascending=True).tail(n)

    )

    fig = px.bar(

        cont, x="dias", y="tipo_processo", orientation="h",

        color_discrete_sequence=[LARANJA],

        labels={"dias": "dias (média em aberto)", "tipo_processo": ""},

    )

    return _fin(fig, height=max(340, 26 * len(cont) + 80))





def fig_barras_unidades(resumo: pd.DataFrame) -> go.Figure:

    df = resumo.melt(

        id_vars="unidade", value_vars=["em_aberto", "concluidos_30d", "criticos"],

        var_name="metrica", value_name="valor",

    )

    df["metrica"] = df["metrica"].map({

        "em_aberto": "Em aberto",

        "concluidos_30d": "Concluídos (30d)",

        "criticos": "Crï¿½ticos",

    })

    fig = px.bar(

        df, x="unidade", y="valor", color="metrica", barmode="group",

        color_discrete_map={"Em aberto": AZUL, "Concluídos (30d)": VERDE, "Crï¿½ticos": LARANJA},

        labels={"unidade": "", "valor": "", "metrica": ""},

        category_orders={"unidade": [u["sigla"] for u in unidades()]},

    )

    return _fin(fig)





def fig_barras_painel(

    comp: pd.DataFrame, unids: list[dict], colunas: list[str] | None = None

) -> go.Figure:

    cols = colunas or ["Total", "Sem acompanhamento"]

    df = comp.reset_index().melt(

        id_vars="unidade", value_vars=cols, var_name="metrica", value_name="valor"

    )

    cores = {"Total": AZUL, "Sem acompanhamento": LARANJA, "Prioritários": VERMELHO}

    fig = px.bar(

        df, x="unidade", y="valor", color="metrica", barmode="group",

        color_discrete_map=cores,

        labels={"unidade": "", "valor": "", "metrica": ""},

        category_orders={"unidade": [u["sigla"] for u in unids]},

    )

    return _fin(fig)





def fig_top_marcadores(marc: pd.DataFrame, n: int = 12) -> go.Figure:

    fig = px.bar(

        marc.iloc[::-1].head(n), x="processos", y="marcador", orientation="h",

        color_discrete_sequence=[LARANJA],

        labels={"processos": "processos", "marcador": ""},

    )

    return _fin(fig)





def fig_hbar(

    df_rot: pd.DataFrame,

    y: str = "rotulo",

    x: str = "n",

    cor: str = LARANJA,

    rotulo_x: str = "processos",

    height: int | None = None,

) -> go.Figure:

    fig = px.bar(

        df_rot, x=x, y=y, orientation="h",

        color_discrete_sequence=[cor],

        labels={x: rotulo_x, y: ""},

    )

    return _fin(fig, height=height)





def fig_linha_estoque(evol: pd.DataFrame, unids: list[dict]) -> go.Figure:

    cores = {u["sigla"]: u["cor"] for u in unids}

    fig = px.line(

        evol, x="ts_txt", y="total", color="unidade",

        markers=True,

        color_discrete_map=cores,

        category_orders={"unidade": [u["sigla"] for u in unids]},

        labels={"ts_txt": "extração", "total": "processos", "unidade": ""},

    )

    return _fin(fig)





def fig_pontos_fator(df: pd.DataFrame) -> go.Figure:

    fig = px.bar(

        df, x="pontos", y="fator", orientation="h",

        color_discrete_sequence=[ROXO],

        labels={"pontos": "pontos de criticidade", "fator": ""},

    )

    return _fin(fig, height=max(300, 30 * len(df) + 60))





def fig_serie_producao(base: pd.DataFrame) -> go.Figure:

    """Barras agrupadas por mï¿½s: documentos gerados, processos gerados e externos."""

    df = base.melt(

        id_vars=["mes_txt"],

        value_vars=["documentos", "processos", "externos"],

        var_name="metrica", value_name="quantidade",

    )

    df["metrica"] = df["metrica"].map({

        "documentos": "Documentos gerados",

        "processos": "Processos gerados",

        "externos": "Documentos externos",

    })

    fig = px.bar(

        df, x="mes_txt", y="quantidade", color="metrica", barmode="group",

        color_discrete_map={

            "Documentos gerados": AZUL,

            "Processos gerados": VERDE,

            "Documentos externos": LARANJA,

        },

        labels={"mes_txt": "", "quantidade": "", "metrica": ""},

    )

    return _fin(fig.update_traces(hovertemplate="%{x}: %{y}"))





def fig_serie_producao_unidades(du: pd.DataFrame) -> go.Figure:

    """Linhas por unidade: sï¿½rie mensal de documentos gerados."""

    fig = px.line(

        du, x="mes_txt", y="quantidade", color="unidade", markers=True,

        color_discrete_map=CORES_UNIDADE,

        category_orders={"unidade": [u["sigla"] for u in unidades()]},

        labels={"mes_txt": "", "quantidade": "documentos", "unidade": ""},

    )

    fig.update_traces(line=dict(width=2.5))

    return _fin(fig)





def fig_linha_total(base: pd.DataFrame) -> go.Figure:

    """Linha + ï¿½rea: total mensal de documentos gerados (mes_txt, quantidade)."""

    fig = px.line(

        base, x="mes_txt", y="quantidade",

        color_discrete_sequence=[AZUL],

        labels={"mes_txt": "", "quantidade": "documentos"},

    )

    fig.update_traces(

        mode="lines+markers",

        line=dict(width=3),

        marker=dict(size=7),

        fill="tozeroy",

        fillcolor="rgba(29,78,137,.10)",

        hovertemplate="%{x}: %{y:,.0f}<extra></extra>",

    )

    fig.update_layout(showlegend=False)

    return _fin(fig)





def fig_barras_balanco(df: pd.DataFrame, unids: list[dict]) -> go.Figure:

    df2 = df.melt(
        id_vars="unidade",
        value_vars=["Abertos", "Em tramitação", "Fechados"],
        var_name="metrica", value_name="valor",
    )

    cores = {"Abertos": LARANJA, "Em tramitação": AZUL, "Fechados": VERDE}

    fig = px.bar(
        df2, x="unidade", y="valor", color="metrica", barmode="group",
        color_discrete_map=cores,
        labels={"unidade": "", "valor": "", "metrica": ""},
        category_orders={"unidade": [u["sigla"] for u in unids]},
    )

    return _fin(fig)





def fig_barras_categorias(df: pd.DataFrame, unids: list[dict]) -> go.Figure:

    fig = px.bar(
        df, x="categoria", y="total", color="unidade", barmode="group",
        color_discrete_map=CORES_UNIDADE,
        category_orders={"unidade": [u["sigla"] for u in unids]},
        labels={"categoria": "", "total": "documentos", "unidade": ""},
    )

    fig.update_layout(xaxis_tickangle=-20)

    return _fin(fig, height=420)

