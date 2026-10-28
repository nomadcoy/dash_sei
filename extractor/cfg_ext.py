from __future__ import annotations

# Helpers de configuração usados pelo extrator (importados também de cfg quando aplicável)
import asyncio
import functools
import os
import random


@functools.lru_cache(maxsize=1)
def pausa_min() -> float:
    return float(os.getenv("EXTRAC_PAUSA_MIN", "0.9"))


@functools.lru_cache(maxsize=1)
def pausa_max() -> float:
    return float(os.getenv("EXTRAC_PAUSA_MAX", "1.6"))


@functools.lru_cache(maxsize=1)
def sei_base() -> str:
    from cfg import arquivo_unidades

    return arquivo_unidades().get("base_url", "https://www.sei.mg.gov.br")