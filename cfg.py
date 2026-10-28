from __future__ import annotations

import functools
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent
CONFIG_DIR = RAIZ / "config"

load_dotenv(RAIZ / ".env")


def _carregar(nome: str) -> dict:
    with open(CONFIG_DIR / nome, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


@functools.lru_cache(maxsize=None)
def arquivo_unidades() -> dict:
    return _carregar("unidades.yaml")


@functools.lru_cache(maxsize=None)
def unidades() -> list[dict]:
    return arquivo_unidades()["unidades"]


@functools.lru_cache(maxsize=None)
def unidades_siglas() -> list[str]:
    return [u["sigla"] for u in unidades()]


@functools.lru_cache(maxsize=None)
def criterios() -> dict:
    return _carregar("criterios.yaml")


@functools.lru_cache(maxsize=None)
def prazos() -> dict:
    return _carregar("prazos.yaml")


@functools.lru_cache(maxsize=None)
def stim_map() -> dict:
    return _carregar("stim_map.yaml")


def cor_unidade(sigla: str) -> str:
    for u in unidades():
        if u["sigla"] == sigla:
            return u["cor"]
    return "#64748B"


def nome_unidade(sigla: str) -> str:
    for u in unidades():
        if u["sigla"] == sigla:
            return u["nome"]
    return sigla


def descricao_unidade(sigla: str) -> str:
    for u in unidades():
        if u["sigla"] == sigla:
            return (u.get("descricao") or "").strip()
    return ""


def limiar_padrao() -> int:
    return int(criterios().get("limiar_padrao", 50))


def dias_limite_sem_andamento(tipo_processo: str) -> int:
    p = prazos()
    por_tipo = p.get("por_tipo") or {}
    if tipo_processo in por_tipo:
        return int(por_tipo[tipo_processo])
    return int(p.get("padrao_dias_sem_andamento", 21))


def dash_credenciais() -> tuple[str, str]:
    return (
        os.getenv("DASH_USUARIO", "").strip(),
        os.getenv("DASH_SENHA", "").strip(),
    )
