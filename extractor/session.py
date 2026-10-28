from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))
load_dotenv(RAIZ / ".env")

log = logging.getLogger("extractor")

URL_LOGIN = os.getenv(
    "SEI_URL_LOGIN",
    "https://www.sei.mg.gov.br/sip/login.php?sigla_orgao_sistema=GOVMG&sigla_sistema=SEI&infra_url=L3NlaS8=",
)
LOGIN = os.getenv("SEI_LOGIN", "")
SENHA = os.getenv("SEI_SENHA", "")
HEADLESS = os.getenv("SEI_HEADLESS", "true").lower() in ("1", "true", "yes")
ORGAO_LABEL = os.getenv("SEI_ORGAO", "SEINFRA")

SESSAO_DIR = RAIZ / "data" / "sessao"
SESSAO_ARQ = SESSAO_DIR / "estado.json"
DEBUG_DIR = RAIZ / "data" / "debug"

from cfg import arquivo_unidades  # noqa: E402

BASE = arquivo_unidades().get("base_url", "https://www.sei.mg.gov.br")


class LoginFalhou(Exception):
    pass


class SessaoSei:
    """Navegador Playwright com sessão persistida (cookies) no data/sessao."""

    def __init__(self) -> None:
        self._pw = None
        self.browser = None
        self.context = None
        self.page = None
        self.orgao_efetivo = ORGAO_LABEL

    async def iniciar(self) -> None:
        from playwright.async_api import async_playwright

        self._pw = await async_playwright().start()
        opts = {}
        if SESSAO_ARQ.exists():
            opts["storage_state"] = str(SESSAO_ARQ)
        self.browser = await self._pw.chromium.launch(headless=HEADLESS)
        self.context = await self.browser.new_context(**opts)
        self.page = await self.context.new_page()
        log.info("navegador iniciado (headless=%s)", HEADLESS)

    async def fechar(self) -> None:
        try:
            if self.browser:
                await self.browser.close()
        finally:
            if self._pw:
                await self._pw.stop()

    async def _tem_tela_login(self) -> bool:
        return (await self.page.locator("#pwdSenha").count()) > 0

    async def garantir_login(self) -> bool:
        """Loga (se preciso) e salva a sessão. Retorna True se já estava logado."""
        await self.page.goto(URL_LOGIN, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_timeout(1500)

        if not await self._tem_tela_login():
            log.info("sessão de cookies ainda válida")
            return True

        for orgao in (ORGAO_LABEL, "GOVMG"):
            try:
                if await self._logar_orgao(orgao):
                    self.orgao_efetivo = orgao
                    return False
            except LoginFalhou:
                log.warning("falha de login no órgão %s, tentando próximo", orgao)
        raise LoginFalhou("login recusado nos órgãos configurados")

    async def _logar_orgao(self, orgao: str) -> bool:
        await self.page.goto(URL_LOGIN, wait_until="domcontentloaded", timeout=60000)
        await self.page.wait_for_timeout(1000)
        if not await self._tem_tela_login():
            return True

        segredo = "*" * 6
        await self.page.locator("#txtUsuario").fill(LOGIN)
        await self.page.locator("#pwdSenha").fill(SENHA)

        sel = self.page.locator("#selOrgao")
        try:
            await sel.select_option(label=orgao)
        except Exception:
            raise LoginFalhou(f"órgão '{orgao}' não listado")

        await self.page.locator("#sbmAcessar").click()
        await self.page.wait_for_load_state("domcontentloaded")
        await self.page.wait_for_timeout(2500)

        # 2FA pode surgir nessa versão — detecta e falha com orientação
        if await self._tem_2fa():
            raise LoginFalhou(
                "login exige autenticação em 2 fatores — rode uma vez com SEI_HEADLESS=false"
            )

        if await self._tem_tela_login():
            html = await self.page.content()
            d = DEBUG_DIR
            d.mkdir(parents=True, exist_ok=True)
            (d / "login_falha.html").write_text(html, encoding="utf-8", errors="replace")
            log.error("erro de autenticação (dump: data/debug/login_falha.html)")
            raise LoginFalhou("usuário/senha recusados")

        SESSAO_DIR.mkdir(parents=True, exist_ok=True)
        await self.context.storage_state(path=str(SESSAO_ARQ))
        log.info("login ok no órgão %s (login usado: %s)", orgao, segredo)
        return True

    async def _tem_2fa(self) -> bool:
        texto = await self.page.inner_text("body")
        return any(
            k in texto
            for k in (
                "Autenticação em 2 fatores",
                "autenticação em 2 fatores",
                "Código de verificação",
                "QR Code",
                "token",
            )
        )

    async def dump(self, arquivo: str) -> None:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        html = await self.page.content()
        (DEBUG_DIR / arquivo).write_text(html, encoding="utf-8", errors="replace")
        try:
            await self.page.screenshot(path=str(DEBUG_DIR / (arquivo + ".png")), full_page=True)
        except Exception:
            pass


def rodar(coro) -> None:
    asyncio.run(coro)