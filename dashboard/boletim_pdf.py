from __future__ import annotations

import base64
import io
from datetime import date
from pathlib import Path

import pandas as pd

_RAIZ = Path(__file__).resolve().parent.parent


def _logo_stim() -> str:
    """Logo da STIM embutido em base64 (data URI). Fallback: vetor vazio."""
    caminho = _RAIZ / "dashboard" / "assets" / "logo_stim.png"
    if not caminho.exists():
        return ""
    b64 = base64.b64encode(caminho.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def _cor(sigla: str) -> str:
    C = {
        "DGTI": "#1D4E89",
        "DGTM": "#2E7D32",
        "DRTC": "#C62828",
        "STIM": "#6A1B9A",
    }
    return C.get(sigla, "#334155")


def _img_serie(serie: pd.DataFrame, unidades: list[str], altura: float = 3.4) -> str:
    """Gera PNG (base64) com a série mensal por unidade. Vazio = sem gráfico."""
    piv = serie.pivot(index="mes", columns="unidade", values="quantidade").fillna(0)
    piv.index = [f"{m[5:7]}/{m[2:4]}" for m in piv.index]
    import matplotlib  # noqa: PLC0415
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    cor = [_cor(u) for u in unidades if u in piv.columns]
    fig, ax = plt.subplots(figsize=(9.5, altura), dpi=110)
    piv[list(unidades)].plot.bar(ax=ax, color=cor, width=0.82)
    ax.set_ylim(bottom=0)
    ax.legend(ncol=len(unidades), frameon=False, fontsize=8, loc="upper left")
    ax.tick_params(labelsize=7)
    ax.grid(axis="y", ls=":", alpha=0.4)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"


def _img_serie_linha(serie: pd.DataFrame, unidades: list[str]) -> str:
    """PNG (base64): total mensal em linha + linhas por unidade. Vazio = sem gráfico."""
    piv = serie.pivot(index="mes", columns="unidade", values="quantidade").fillna(0)
    piv.index = [f"{m[5:7]}/{m[2:4]}" for m in piv.index]
    import matplotlib  # noqa: PLC0415
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    cols = [u for u in unidades if u in piv.columns]
    fig, ax = plt.subplots(figsize=(9.5, 3.4), dpi=110)
    piv.sum(axis=1).plot(ax=ax, color="#0f172a", lw=2.6, marker="o", ms=4, label="Total")
    if cols:
        piv[cols].plot(ax=ax, color=[_cor(u) for u in cols], lw=1.5, marker="o", ms=3, alpha=.85)
    ax.set_ylim(bottom=0)
    ax.legend(ncol=len(cols) + 1, frameon=False, fontsize=8, loc="upper left")
    ax.tick_params(labelsize=7)
    ax.grid(axis="y", ls=":", alpha=0.4)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.tight_layout()
    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return f"data:image/png;base64,{base64.b64encode(buf.getvalue()).decode('ascii')}"


def _analise_html(analise: list[dict] | None) -> str:
    """Blocos da leitura analítica (texto com **negrito** → <b>)."""
    if not analise:
        return ""
    import re  # noqa: PLC0415

    cores = {
        "info": "#1D4E89",
        "positivo": "#2E7D32",
        "atencao": "#B45309",
        "alerta": "#DC2626",
    }
    itens = []
    for item in analise:
        texto = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", str(item.get("texto", "")))
        cor = cores.get(item.get("tipo", "info"), "#1D4E89")
        itens.append(f"<div class='analise' style='border-left-color:{cor}'>{texto}</div>")
    return "".join(itens)


def _tabela_html(df: pd.DataFrame, fonte: str) -> str:
    if df is None or df.empty:
        return "<p class='vazio'>Sem dados para exibir.</p>"
    cols = list(df.columns)
    th = "".join(f"<th>{c}</th>" for c in cols)
    linhas = []
    for _, r in df.iterrows():
        tds = "".join(f"<td>{r[c]}</td>" for c in cols)
        linhas.append(f"<tr>{tds}</tr>")
    return (
        f"<table><thead><tr>{th}</tr></thead><tbody>{''.join(linhas)}</tbody></table>"
        + (f"<p class='fonte'>Fonte: {fonte}</p>" if fonte else "")
    )


def html_boletim(
    *,
    de: str,
    ate: str,
    unidades: list[str],
    excluir_auto: bool,
    kpis: dict,
    comparativo: pd.DataFrame,
    serie: pd.DataFrame,
    por_tipo: dict[str, pd.DataFrame],
    excluidos: float,
    analise: list[dict] | None = None,
    categorias: pd.DataFrame | None = None,
    top_documentos: pd.DataFrame | None = None,
    externos: pd.DataFrame | None = None,
    processos: pd.DataFrame | None = None,
    eficiencia: pd.DataFrame | None = None,
    sintese: list[dict] | None = None,
) -> str:
    """Monta o HTML do boletim (mesma lógica da tela) para conversão em PDF."""
    rot_de = f"{de[5:7]}/{de[2:4]}" if len(de) == 7 else de
    rot_ate = f"{ate[5:7]}/{ate[2:4]}" if len(ate) == 7 else ate
    un_txt = ", ".join(unidades)
    auto_txt = (
        "Documentos automáticos do SEI excluídos (Recibo Eletrônico de Protocolo e "
        f"Certidão de Intimação Cumprida): {int(excluidos):,}".replace(",", ".")
        if excluir_auto
        else "Documentos automáticos do SEI incluídos na contagem."
    )

    logo = _logo_stim()
    logo_html = f'<img src="{logo}" class="logo">' if logo else "<div class='logo-fake'></div>"

    cabecalho = f"""
    <div class="cabecalho">
      {logo_html}
      <div class="cabecalho-titulos">
        <div class="cabecalho-org">Secretaria de Estado de Infraestrutura, Mobilidade e Parcerias</div>
        <div class="cabecalho-titulo">Boletim de Produtividade — SEINFRA / STIM</div>
        <div class="cabecalho-sub">Documentos e processos gerados por unidade, mês a mês · Estatísticas da Unidade (SEI-MG)</div>
      </div>
      <div class="cabecalho-gerado">Gerado automaticamente<br>pelo Painel de Controle de Processos</div>
    </div>
    """

    cards = ""
    for rotulo, valor in kpis.items():
        cards += f"<div class='card'><div class='card-r'>{rotulo}</div><div class='card-v'>{valor}</div></div>"

    img = _img_serie(serie, unidades) if not serie.empty else ""
    img_html = f"<img src='{img}' class='grafico'>" if img else ""
    img_linha = _img_serie_linha(serie, unidades) if not serie.empty else ""
    img_linha_html = f"<img src='{img_linha}' class='grafico'>" if img_linha else ""
    analise_html = _analise_html(analise)

    blocos_tipos = ""
    for u in unidades:
        t = por_tipo.get(u)
        if t is None or t.empty:
            continue
        blocos_tipos += (
            f"<h3>{u} — documentos gerados por tipo</h3>"
            + _tabela_html(t.rename(columns={"tipo": "Tipo de documento", "total": "Quantidade"}), fonte="Estatísticas da Unidade do SEI")
        )

    bloco_categorias = ""
    if categorias is not None and not categorias.empty:
        bloco_categorias = (
            "<h2>O que as diretorias produzem — por categoria de documento</h2>"
            + _tabela_html(
                categorias.rename(columns={"categoria": "Categoria", "total": "Documentos"}),
                fonte="Agrupamento dos tipos de documento informados pelo SEI",
            )
        )

    bloco_top = ""
    if top_documentos is not None and not top_documentos.empty:
        bloco_top = (
            "<h2>Documentos mais produzidos (por tipo)</h2>"
            + _tabela_html(
                top_documentos.rename(columns={"tipo": "Tipo de documento", "total": "Quantidade"}),
                fonte="Estatísticas da Unidade do SEI",
            )
        )

    bloco_ext = ""
    if externos is not None and not externos.empty:
        bloco_ext = (
            "<h2>Documentos externos (origem externa)</h2>"
            + _tabela_html(
                externos.rename(columns={"tipo": "Tipo", "total": "Quantidade"}),
                fonte="Tabela 'Documentos externos' do SEI",
            )
        )

    bloco_prc = ""
    if processos is not None and not processos.empty:
        bloco_prc = (
            "<h2>Tipos de processo gerados</h2>"
            + _tabela_html(
                processos.rename(columns={"tipo": "Tipo de processo", "total": "Quantidade"}),
                fonte="Tabela 'Processos gerados' do SEI",
            )
        )

    bloco_sintese = ""
    if sintese:
        bloco_sintese = (
            "<h2>Síntese do período — leitura do conjunto</h2>"
            + _analise_html(sintese)
        )

    bloco_efi = ""
    if eficiencia is not None and not eficiencia.empty:
        bloco_efi = (
            "<h2>Eficiência — tempo médio de tramitação</h2>"
            + _tabela_html(
                eficiencia.rename(columns={
                    "unidade": "Diretoria", "tipos": "Tipos com tempo",
                    "mediana_dias": "Mediana (dias)", "media_dias": "Média (dias)",
                }),
                fonte="Tabela 'Tempos médios' do SEI (valores ≥300 dias fora da mediana)",
            )
        )

    return f"""<!DOCTYPE html>
<html lang="pt-BR"><head><meta charset="utf-8">
<style>
  @page {{ size: A4; margin: 16mm 14mm; }}
  * {{ box-sizing: border-box; }}
  body {{ font-family: Arial, Helvetica, sans-serif; color: #0f172a; font-size: 12px; line-height: 1.45; }}
  h1 {{ color: #1D4E89; font-size: 20px; margin: 0 0 2px; }}
  h2 {{ color: #1D4E89; font-size: 15px; border-bottom: 2px solid #1D4E89; padding-bottom: 3px; margin: 18px 0 8px; }}
  h3 {{ font-size: 13px; margin: 14px 0 6px; color: #334155; }}
  .sub {{ color: #475569; font-size: 11px; margin: 0 0 10px; }}
  .cabecalho {{ display: flex; align-items: center; gap: 16px; background: #1D4E89;
                color: #fff; border-radius: 10px; padding: 14px 18px; margin-bottom: 14px; }}
  .logo {{ height: 54px; width: auto; border-radius: 8px; background: #fff; padding: 4px; }}
  .logo-fake {{ width: 54px; height: 54px; border-radius: 8px; background: rgba(255,255,255,.2); }}
  .cabecalho-titulos {{ flex: 1; }}
  .cabecalho-org {{ font-size: 10px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; opacity: .85; }}
  .cabecalho-titulo {{ font-size: 18px; font-weight: 800; letter-spacing: -.01em; margin: 3px 0; }}
  .cabecalho-sub {{ font-size: 10.5px; opacity: .9; }}
  .cabecalho-gerado {{ text-align: right; font-size: 9px; line-height: 1.5; opacity: .95;
                      border-left: 1px solid rgba(255,255,255,.35); padding-left: 14px; }}
  .periodo {{ background: #eef2f7; border: 1px solid #d6dee8; border-radius: 6px; padding: 6px 10px; font-size: 11px; margin-bottom: 12px; }}
  .cards {{ display: flex; gap: 8px; flex-wrap: wrap; margin: 8px 0 12px; }}
  .card {{ flex: 1 1 140px; border: 1px solid #e5eaf1; border-radius: 10px; padding: 10px 12px; }}
  .card-r {{ font-size: 10px; color: #334155; text-transform: uppercase; letter-spacing: .04em; font-weight: 700; }}
  .card-v {{ font-size: 20px; font-weight: 800; color: #0f172a; margin-top: 4px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 6px 0 4px; }}
  th, td {{ border: 1px solid #e2e8f0; padding: 4px 8px; text-align: left; font-size: 11px; }}
  th {{ background: #1D4E89; color: #fff; font-weight: 700; }}
  tr:nth-child(even) td {{ background: #f8fafc; }}
  img.grafico {{ width: 100%; border: 1px solid #e5eaf1; border-radius: 8px; margin: 6px 0; }}
  .fonte {{ font-size: 9px; color: #64748b; margin: 2px 0 8px; }}
  .vazio {{ color: #64748b; font-style: italic; }}
  .analise {{ background: #f8fafc; border-left: 4px solid #1D4E89; border-radius: 0 8px 8px 0;
              padding: 7px 12px; margin: 5px 0; font-size: 11.5px; line-height: 1.5; }}
  .rodape {{ margin-top: 18px; font-size: 9px; color: #64748b; border-top: 1px solid #e5eaf1; padding-top: 6px; }}
</style></head><body>
  {cabecalho}
  <div class="periodo">Período: <b>{rot_de} a {rot_ate}</b> · Unidades: <b>{un_txt}</b> · {auto_txt}</div>
  <div class="cards">{cards}</div>
  <h2>Leitura analítica do período</h2>
  {analise_html or "<p class='vazio'>Sem leitura para o período selecionado.</p>"}
  {bloco_categorias}
  {bloco_top}
  {bloco_ext}
  {bloco_prc}
  {bloco_efi}
  <h2>Série histórica (linha)</h2>
  {img_linha_html}
  <h2>Produção por unidade, mês a mês</h2>
  {img_html}
  <h2>Comparativo por diretoria</h2>
  {_tabela_html(comparativo, fonte="Tabelas 'Documentos gerados / Processos gerados / Documentos externos' do SEI")}
  <h2>Documentos gerados por tipo</h2>
  {blocos_tipos}
  {bloco_sintese}
  <p class="rodape">Documento gerado automaticamente em {date.today().strftime('%d/%m/%Y')}. Fonte dos dados: Estatísticas da Unidade do SEI-MG (extração automática); os valores são informados pelo próprio SEI, e o painel apenas os organiza e compara. O SEI limita a consulta a 1 ano por vez; o recorte usa as coletas mensais. {auto_txt}</p>
</body></html>"""


def gerar_pdf(html: str) -> bytes:
    """Renderiza o HTML em PDF A4 via Chromium (Playwright)."""
    from playwright.sync_api import sync_playwright  # noqa: PLC0415

    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        pg = b.new_page()
        pg.set_content(html, wait_until="networkidle")
        data = pg.pdf(
            format="A4",
            print_background=True,
            margin={"top": "14mm", "bottom": "14mm", "left": "12mm", "right": "12mm"},
        )
        b.close()
    return data