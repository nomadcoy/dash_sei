from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from cfg import unidades


def injetar_css() -> None:
    st.markdown(
        f"""
        <style>
        :root {{
            --gv-primary: #1D4E89;
            --gv-primary-dark: #143a66;
            --gv-ink: #0f172a;
            --gv-muted: #475569;
            --gv-line: #e5eaf1;
        }}
        html, body, [class*="css"], .stApp, header {{
            font-family: 'Segoe UI', system-ui, -apple-system, 'Helvetica Neue', Arial, sans-serif;
        }}
        .stApp {{
            background: linear-gradient(180deg, #f4f7fb 0%, #e9eff6 100%);
        }}
        .stApp::before {{
            content: "";
            position: fixed; top: 0; left: 0; right: 0; height: 4px;
            background: linear-gradient(90deg, #1D4E89 0%, #2b6cb0 50%, #1D4E89 100%);
            z-index: 1000000;
        }}
        [data-testid="stHeader"] {{ background: rgba(0,0,0,0); }}
        [data-testid="stAppDeployButton"], [data-testid="stMainMenu"] {{ display: none !important; }}
        [data-testid="stSidebarCollapsedControl"] {{ display: block !important; visibility: visible !important; }}
        h1, h2, h3, h4 {{ color: var(--gv-ink) !important; font-weight: 700 !important; letter-spacing: -0.01em; }}
        h2, h3 {{ border-left: 4px solid var(--gv-primary); padding-left: 12px; }}
        [data-testid="stCaptionContainer"], .stCaption, small {{ color: var(--gv-muted) !important; }}

        [data-testid="stSidebar"] {{
            background: #f8fafc; border-right: 1px solid var(--gv-line);
        }}
        [data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {{
            border-left: none; padding-left: 0; color: var(--gv-primary) !important;
        }}
        [data-testid="stSidebarNav"] a {{ border-radius: 10px; }}
        [data-testid="stSidebarNav"] a[aria-current="page"] {{
            background: #e8f0fa; color: var(--gv-primary) !important; font-weight: 700;
        }}

        [data-testid="stMetric"] {{
            background: #ffffff; border: 1px solid var(--gv-line);
            border-left: 4px solid var(--gv-primary);
            border-radius: 12px; padding: 14px 16px;
            box-shadow: 0 1px 3px rgba(16,24,40,.05);
        }}
        [data-testid="stMetricLabel"] {{
            color: #334155; font-weight: 600; text-transform: uppercase;
            font-size: .76rem; letter-spacing: .06em;
        }}
        [data-testid="stMetricValue"] {{ color: var(--gv-ink); font-weight: 800; font-size: 1.7rem; }}

        [class*="st-key-vgcard"] button {{
            width: 100%; min-height: 96px; background: #ffffff;
            border: 1px solid var(--gv-line); border-left: 4px solid var(--gv-primary);
            border-radius: 12px; padding: 12px 16px; box-shadow: 0 1px 3px rgba(16,24,40,.05);
            white-space: normal; line-height: 1.3;
        }}
        [class*="st-key-vgcard"] button:hover {{
            border-color: var(--gv-primary); background: #f7fafd;
        }}
        [class*="st-key-vgcard"] button p {{
            text-align: left; font-size: .8rem; font-weight: 600; color: #334155;
            text-transform: uppercase; letter-spacing: .04em; margin: 0;
        }}
        [class*="st-key-vgcard"] button strong {{
            display: block; margin-top: 4px; font-size: 1.6rem; font-weight: 800;
            color: var(--gv-ink); letter-spacing: -.02em;
        }}
        [class*="st-key-vgcard"] button[kind="primary"] {{
            border-color: var(--gv-primary); box-shadow: 0 0 0 2px rgba(29,78,137,.28);
        }}

        [data-testid="stPlotlyChart"], [data-testid="stDataFrame"] {{
            background: #ffffff; border: 1px solid var(--gv-line); border-radius: 12px;
            padding: 8px; box-shadow: 0 1px 3px rgba(16,24,40,.05);
        }}
        div[data-testid="stExpander"] {{
            background: #ffffff; border: 1px solid var(--gv-line); border-radius: 12px;
        }}

        .unit-chips {{ display:flex; gap:8px; flex-wrap:wrap; margin: 4px 0 12px; }}
        .chip {{ display:inline-flex; align-items:center; gap:6px; background:#fff;
                 border:1px solid var(--gv-line); border-radius:999px; padding:4px 12px;
                 font-size:.8rem; font-weight:600; color:#334155; }}
        .chip .dot {{ width:9px; height:9px; border-radius:50%; background:var(--c); }}

        .descricao-box {{
            background:#ffffff; border-left:4px solid var(--gv-primary); border-radius:12px;
            padding:14px 18px; color:#334155; line-height:1.55; font-size:.95rem;
            box-shadow: 0 1px 3px rgba(16,24,40,.05); margin-bottom: 12px;
        }}
        .etapa {{
            background:#f8fafc; border:1px solid #e2e8f0; border-radius:10px;
            padding:8px 12px; margin:6px 0; font-size:.9rem;
        }}
        footer {{ visibility: hidden; }}

        .gov-header {{
            display:flex; align-items:center; justify-content:space-between; gap:18px;
            background: linear-gradient(180deg,#ffffff 0%, #f7fafd 100%);
            border: 1px solid var(--gv-line); border-top: 4px solid var(--gv-primary);
            border-radius: 14px; padding: 16px 24px; margin-bottom: 18px; flex-wrap:wrap;
            box-shadow: 0 2px 8px rgba(16,24,40,.06);
        }}
        .gov-logos {{ display:flex; align-items:center; gap:14px; }}
        .gov-logo {{ height:46px; width:auto; object-fit:contain; }}
        .gov-titulos {{ flex:1; min-width:280px; text-align:center; }}
        .gov-org {{ font-size:.72rem; font-weight:700; letter-spacing:.14em;
                     color:var(--gv-primary); text-transform:uppercase; }}
        .gov-titulo {{ font-size:1.32rem; font-weight:800; color:var(--gv-ink);
                       letter-spacing:-0.02em; margin:3px 0; }}
        .gov-sub {{ font-size:.8rem; color:var(--gv-muted); }}
        @media (max-width: 760px) {{
            .gov-header {{ flex-direction:column; text-align:center; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def chips_unidades() -> None:
    cores = {u["sigla"]: u["cor"] for u in unidades()}
    chips = "".join(
        f'<span class="chip" style="--c:{cor}"><span class="dot"></span>{sigla}</span>'
        for sigla, cor in cores.items()
    )
    st.markdown(
        f'<div class="unit-chips">{chips}</div>',
        unsafe_allow_html=True,
    )


def descricao_box(texto: str, cor: str = "#1D4E89") -> None:
    st.markdown(
        f'<div class="descricao-box" style="border-left-color:{cor}">{texto}</div>',
        unsafe_allow_html=True,
    )


def cabecalho_institucional() -> None:
    _assets = Path(__file__).resolve().parent / "assets"

    def _img(nome: str, alt: str) -> str:
        caminho = _assets / nome
        if not caminho.exists():
            return ""
        mime = "image/png" if caminho.suffix.lower() == ".png" else "image/jpeg"
        b64 = base64.b64encode(caminho.read_bytes()).decode("ascii")
        return f'<img class="gov-logo" src="data:{mime};base64,{b64}" alt="{alt}">'

    logos_esq = _img("logo_estado.png", "Estado de Minas Gerais") + _img(
        "logo_seinfra.jpg", "SEINFRA"
    )
    logos_dir = _img("logo_sei.png", "SEI-MG")
    st.markdown(
        '<div class="gov-header">'
        f'<div class="gov-logos">{logos_esq}</div>'
        '<div class="gov-titulos">'
        '<div class="gov-org">Secretaria de Estado de Infraestrutura, Mobilidade e Parcerias - SEINFRA</div>'
        '<div class="gov-titulo">Painel de Controle de Processos - Gestão à Vista</div>'
        '<div class="gov-sub">Controle de processos SEI das unidades STIM · DGTI · DGTM · DRTC</div>'
        '</div>'
        f'<div class="gov-logos">{logos_dir}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
