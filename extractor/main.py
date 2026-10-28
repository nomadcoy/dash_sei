from __future__ import annotations

import argparse
import logging
import os
import random
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from cfg import unidades  # noqa: E402

_log = logging.getLogger("extractor.main")


def configurar_log() -> None:
    log_dir = RAIZ / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s", "%d/%m/%Y %H:%M:%S")
    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    fh = logging.FileHandler(log_dir / "extracao.log", encoding="utf-8")
    fh.setFormatter(formatter)
    handlers.append(fh)
    for h in handlers:
        h.setFormatter(formatter)
        logging.getLogger().addHandler(h)
    logging.getLogger().setLevel(logging.INFO)


async def principal(args: argparse.Namespace) -> int:
    import db

    # Lock de concorrência: impede duas extrações simultâneas (causa de falhas
    # na troca de unidade). Se já existe lock com PID vivo, aborta imediatamente.
    lock = RAIZ / "data" / "extraindo.pid"
    lock.parent.mkdir(parents=True, exist_ok=True)
    try:
        pid_ativo = int(lock.read_text().strip())
        if _pid_vivo(pid_ativo):
            _log.error(
                "extração já em andamento (PID %s em data/extraindo.pid) — abortando",
                pid_ativo,
            )
            return 2
    except (ValueError, FileNotFoundError):
        pass
    lock.write_text(str(os.getpid()), encoding="utf-8")
    try:
        return await _executar(args)
    finally:
        try:
            lock.unlink(missing_ok=True)
        except Exception:
            pass


def _pid_vivo(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _periodos_anuais(de: str, ate: str) -> list[tuple[str, str]]:
    """Fatia um intervalo em períodos anuais (o SEI aceita no máximo 1 ano)."""
    d = datetime.strptime(de, "%d/%m/%Y")
    a = datetime.strptime(ate, "%d/%m/%Y")
    periodos: list[tuple[str, str]] = []
    atual = d
    while atual <= a:
        fim_ano = datetime(atual.year, 12, 31)
        if fim_ano <= a:
            periodos.append((atual.strftime("%d/%m/%Y"), fim_ano.strftime("%d/%m/%Y")))
        else:
            periodos.append((atual.strftime("%d/%m/%Y"), a.strftime("%d/%m/%Y")))
            break
        atual = datetime(atual.year + 1, 1, 1)
    return periodos


async def _executar(args: argparse.Namespace) -> int:
    import db

    from extractor import scraping, session

    conn = db.conectar()
    ts_ini = datetime.now(timezone.utc).isoformat(timespec="seconds")
    ext_id = db.nova_extracao(conn, "sei", ts_ini)
    total_coletado = 0

    try:
        sess = session.SessaoSei()
        await sess.iniciar()
        await sess.garantir_login()

        await sess.dump("apos_login.html")

        for u in unidades():
            sigla = u["sigla"]
            if args.unidades and sigla not in args.unidades:
                continue
            try:
                await scraping.trocar_unidade(sess.page, sigla)
            except Exception as exc:
                _log.error("unidade %s: falha ao trocar unidade — %s", sigla, exc)
                continue
            if not args.somente_painel:
                coletadas = await scraping.coletar_controle(
                    sess.page, sigla, max_paginas=args.max_paginas
                )
                total_coletado += len(coletadas)

                from extractor import etl_sei

                df = etl_sei.processar(coletadas, sigla)
                conn.execute("DELETE FROM processos WHERE unidade = ?", (sigla,))
                if not df.empty:
                    df["unidade_atual"] = df["unidade_atual"].fillna(sigla)
                    df["unidade"] = sigla
                    n = etl_sei.gravar(conn, df, ext_id, sigla)
                    db.gravar_historico(conn, ext_id, ts_ini, df.to_dict("records"))
                    _log.info("unidade %s: %d registros gravados", sigla, n)
            try:
                painel = await scraping.coletar_painel(sess.page, sigla)
                db.gravar_painel(
                    conn, ext_id, sigla,
                    painel.get("cartoes", {}),
                    painel.get("tabelas", {}),
                    ts_ini,
                )
                _log.info(
                    "unidade %s: painel ok (total=%s sem_acomp=%s prioritarios=%s)",
                    sigla,
                    painel.get("cartoes", {}).get("total"),
                    painel.get("cartoes", {}).get("sem_acompanhamento"),
                    painel.get("cartoes", {}).get("prioritarios"),
                )
            except Exception as exc:
                _log.warning("unidade %s: falha ao ler painel — %s", sigla, exc)

            if args.estatisticas:
                try:
                    for de, ate in _periodos_anuais(*args.estatisticas_periodo):
                        est = await scraping.coletar_estatisticas(
                            sess.page, sigla, de=de, ate=ate
                        )
                        db.gravar_estatisticas(
                            conn, ext_id, sigla, de, ate,
                            est.get("registros", []), ts_ini,
                        )
                        _log.info(
                            "unidade %s: estatísticas ok (%s registros, %s a %s)",
                            sigla, len(est.get("registros", [])), de, ate,
                        )
                except Exception as exc:
                    _log.warning("unidade %s: falha ao ler estatísticas — %s", sigla, exc)

        await sess.fechar()
        if args.estatisticas:
            rem = db.limpar_estatisticas_antigas(conn)
            if rem:
                _log.info("estatísticas antigas removidas: %d linhas", rem)
        db.finalizar_extracao(
            conn, ext_id, "sucesso",
            detalhe=f"{total_coletado} processos coletados (paginado)",
            total=total_coletado,
        )
        _log.info("extração concluída: %d processos", total_coletado)
        return 0
    except Exception as exc:
        _log.error("extração falhou: %s", exc)
        _log.error(traceback.format_exc())
        db.finalizar_extracao(conn, ext_id, "erro", detalhe=str(exc)[:500])
        return 1


def main() -> None:
    configurar_log()
    parser = argparse.ArgumentParser(description="Extrai dados do SEI-MG para o dashboard")
    parser.add_argument("--unidades", nargs="*", help="filtra por siglas (DGTI DGTM DRTC STIM)")
    parser.add_argument("--max-paginas", type=int, default=80, help="limite de páginas por unidade")
    parser.add_argument(
        "--somente-painel", action="store_true",
        help="não recolhe o controle de processos; apenas atualiza o Painel de Controle",
    )
    parser.add_argument(
        "--estatisticas", action="store_true",
        help="coleta as tabelas de Estatísticas da Unidade (documentos gerados, tempos médios etc.)",
    )
    parser.add_argument(
        "--estatisticas-periodo", nargs=2,
        default=["01/01/2024", datetime.now().strftime("%d/%m/%Y")],
        metavar=("DE", "ATE"), help="período DD/MM/AAAA DD/MM/AAAA das estatísticas",
    )
    args = parser.parse_args()

    from extractor.session import rodar

    sys.exit(rodar(principal(args)))


if __name__ == "__main__":
    main()