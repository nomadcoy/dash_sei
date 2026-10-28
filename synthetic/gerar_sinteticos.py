"""Gera base sintética realista para desenvolver o dash sem depender do SEI.

Uso:  python synthetic/gerar_sinteticos.py [--sim]
"""
from __future__ import annotations

import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

import pandas as pd

import cfg
import db
import etl

rng = random.Random(42)

QTD_POR_UNIDADE = {"DGTI": 850, "DGTM": 750, "DRTC": 650, "STIM": 350}

TIPOS = {
    "DGTI": [
        "Autorização de Linha Intermunicipal",
        "Renovação de Concessão Intermunicipal",
        "Revisão Tarifária - Intermunicipal",
        "Modificação de Frota ou Itinerário",
        "Desativação de Linha Intermunicipal",
    ],
    "DGTM": [
        "Autorização de Linha Metropolitana",
        "Renovação de Concessão Metropolitana",
        "Reajuste Tarifário Metropolitano",
        "Modificação de Frota ou Itinerário",
        "Linha de Característica Especial",
    ],
    "DRTC": [
        "Fiscalização - Infração de Concessão",
        "Recurso de Autuação",
        "Apuração de Irregularidade",
        "Auditoria de Concessão",
        "Aplicação de Sanção Administrativa",
    ],
    "STIM": [
        "Convênio ou Consórcio Intermunicipal",
        "Manifestação/Parecer de Superintendência",
        "Parecer Técnico de Linha",
        "Protocolo de Intenção - Consórcio",
        "Acordo de Integração Tarifária",
    ],
}

OPERADORAS = [
    "Viação Minas Gerais S.A.", "Auto Viação 1001", "Transvale Transportes",
    "Viação Ímpar", "Expresso Metropolitano", "Consórcio Transminas",
    "Transportes Pássaro Rosa", "Viação Real da Mantiqueira", "Empresa Cambará",
]
MUNICIPIOS = [
    "Belo Horizonte", "Contagem", "Betim", "Nova Lima", "Ribeirão das Neves",
    "Sabará", "Uberlândia", "Juiz de Fora", "Montes Claros", "Sete Lagoas",
    "Divinópolis", "Ipatinga", "Ubá", "Teófilo Otoni", "Poços de Caldas",
    "Pouso Alegre", "Varginha", "Barbacena", "Itabira", "Passos",
]
RODOVIAS = ["BR-040", "BR-262", "BR-381", "MG-010", "MG-424", "MG-439", "MG-290", "MG-111"]
LINHAS = [f"Linha {rng.randint(100, 999)}" for _ in range(200)]

MARCADORES_NORMAIS = [
    "AGUARDA PARECER", "FISCALIZAÇÃO", "RECURSO", "MUNICÍPIO",
    "CONCESSÃO", "AUDITORIA", "TARIFA",
]
MARCADORES_CRITICOS = ["URGENTE", "VENCENDO PRAZO", "PRAZO VENCIDO", "CRÍTICO"]

OPERACOES = [
    "prorrogação de prazo", "análise de documentação", "vistoria de frota",
    "conferência de balanço", "manifestação do município", "cálculo de índice",
    "notificação ao operador", "reunião técnica", "parecer jurídico",
]

RESPONSaveis = ["a.silva", "c.souza", "m.oliveira", "r.costa", "p.santos", "j.ferreira"]


def numero_sei() -> str:
    return f"{rng.randint(1, 99):02d}.{rng.randint(1, 9)}.{rng.randint(1, 999_999_999):09d}-{rng.randint(0, 9)}"


def assunto_de(tipo: str) -> str:
    op = rng.choice(OPERADORAS)
    mun = rng.choice(MUNICIPIOS)
    lin = rng.choice(LINHAS)
    if "Intermunicipal" in tipo:
        mun2 = rng.choice([m for m in MUNICIPIOS if m != mun])
        return f"{tipo} — {lin} ({mun}/{mun2}) — {op}"
    if "Metropolitano" in tipo or "metropolitana" in tipo.lower():
        return f"{tipo} — {lin} (Região Metropolitana) — {op}"
    if "Infração" in tipo or "Autuação" in tipo or "Sanção" in tipo or "Auditoria" in tipo or "Irregularidade" in tipo:
        return f"{tipo} — {op} — {rng.choice(RODOVIAS)}"
    if "Convênio" in tipo or "Consórcio" in tipo or "Intenção" in tipo:
        n = rng.randint(2, 5)
        return f"{tipo} — {n} municípios ({mun} e outros)"
    if "Tarif" in tipo:
        return f"{tipo} — {op} — vigência {date.today().year}"
    if "Parecer" in tipo or "Manifestação" in tipo or "Acordo" in tipo:
        return f"{tipo} — {lin} — {mun}"
    return f"{tipo} — {op} — {lin}"


def especificacao_de(tipo: str) -> str:
    return (
        f"Requerimento de {rng.choice(OPERACOES)} relativo a {tipo.lower()}, "
        f"protocolado por {rng.choice(OPERADORAS)} envolvendo {rng.choice(MUNICIPIOS)} "
        f"na {rng.choice(RODOVIAS)}."
    )


def gerar_processos(hoje: date) -> list[dict]:
    linhas: list[dict] = []
    usados: set[str] = set()

    for unidade, qtd in QTD_POR_UNIDADE.items():
        for _ in range(qtd):
            numero = numero_sei()
            while numero in usados:
                numero = numero_sei()
            usados.add(numero)

            tipo = rng.choice(TIPOS[unidade])
            dias_atras = int(rng.triangular(0, 365, 75))
            autuacao = hoje - timedelta(days=dias_atras)

            p_concluido = 0.75 if dias_atras > 200 else 0.5 if dias_atras > 90 else 0.22
            situacao = "Concluído" if rng.random() < p_concluido else "Em Andamento"
            data_conclusao: date | None = None
            if situacao == "Concluído":
                dur = rng.randint(3, min(75, max(8, dias_atras)))
                conc = autuacao + timedelta(days=dur)
                if conc > hoje:
                    situacao, conc = "Em Andamento", None
                data_conclusao = conc

            if situacao == "Em Andamento":
                if rng.random() < 0.14:
                    parado = rng.randint(28, 95)
                else:
                    parado = min(rng.integers(0, 40) if hasattr(rng, "integers") else rng.randint(0, 40), dias_atras)
                    parado = min(int(abs(rng.gauss(10, 9))), dias_atras)
                ultima = max(autuacao, hoje - timedelta(days=parado))
                unidade_atual = unidade if rng.random() < 0.9 else rng.choice(
                    [u for u in QTD_POR_UNIDADE if u != unidade]
                )
                responsavel = rng.choice(RESPONSaveis) if rng.random() < 0.55 else None
            else:
                ultima = data_conclusao
                unidade_atual = unidade
                responsavel = None

            marcadores: list[str] = []
            if rng.random() < 0.10:
                marcadores.append(rng.choice(MARCADORES_CRITICOS))
            if rng.random() < 0.35:
                marcadores.append(rng.choice(MARCADORES_NORMAIS))
                if rng.random() < 0.30:
                    extra = rng.choice(MARCADORES_NORMAIS)
                    if extra not in marcadores:
                        marcadores.append(extra)

            idas_vindas = rng.choices([0, 1, 2, 3, 4], weights=[52, 25, 13, 6, 4])[0]

            linhas.append({
                "numero": numero,
                "unidade": unidade,
                "tipo_processo": tipo,
                "assunto": assunto_de(tipo),
                "especificacao": especificacao_de(tipo),
                "situacao": situacao,
                "prioridade": 1 if rng.random() < 0.08 else 0,
                "marcadores": marcadores,
                "data_autuacao": autuacao.isoformat(),
                "data_conclusao": data_conclusao.isoformat() if data_conclusao else None,
                "ultima_movimentacao": ultima.isoformat() if ultima else None,
                "unidade_atual": unidade_atual,
                "responsavel": responsavel,
                "idas_vindas": idas_vindas,
                "link_sei": None,
            })
    return linhas


def gerar_historico(df: pd.DataFrame, hoje: date, dias: int = 60) -> list[tuple]:
    registros: list[tuple] = []
    for n in range(dias, -1, -1):
        dia = hoje - timedelta(days=n)
        ts = f"{dia.isoformat()}T18:00:00+00:00"
        for _, r in df.iterrows():
            aut = pd.to_datetime(r["data_autuacao"]).date()
            if aut > dia:
                continue
            conc_val = r["data_conclusao"]
            conc = None if pd.isna(conc_val) else pd.to_datetime(conc_val).date()
            situ = "Concluído" if (conc and conc <= dia) else "Em Andamento"
            mov = r["ultima_movimentacao"]
            if not pd.isna(mov):
                mov_d = pd.to_datetime(mov).date()
                if mov_d > dia:
                    mov = dia.isoformat()
            registros.append((
                r["numero"], r["unidade"], r["unidade_atual"], situ, mov, ts,
            ))
    return registros


def main() -> None:
    if "--sim" not in sys.argv:
        conn_probe = db.conectar()
        ult = conn_probe.execute(
            "SELECT fonte FROM extracoes WHERE status='sucesso' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        conn_probe.close()
        if ult and ult["fonte"] == "sei":
            print("ABORTADO: há extração real (fonte=sei) no banco.")
            print("Se quiser sobrescrever com dados sintéticos, rode com --sim")
            sys.exit(1)

    conn = db.conectar()
    conn.execute("DELETE FROM historico_processos")
    conn.execute("DELETE FROM processos")
    conn.execute("DELETE FROM extracoes")
    conn.commit()

    hoje = date.today()
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    extracao_id = db.nova_extracao(conn, "sintetico", agora)

    linhas = gerar_processos(hoje)
    df = pd.DataFrame(linhas)
    df = etl.calcular_criticidades(df, hoje=hoje)

    total = etl.upsert_processos(conn, df, extracao_id, agora)

    hist = gerar_historico(df, hoje)
    conn.executemany(
        """INSERT OR REPLACE INTO historico_processos
           (extracao_id, numero, unidade, unidade_atual, situacao, ultima_movimentacao, ts)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [(extracao_id, *r) for r in hist],
    )
    conn.commit()

    db.finalizar_extracao(conn, extracao_id, "sucesso", "base sintética", total)
    criticos = int((df["criticidade"] >= cfg.limiar_padrao()).sum())
    print(f"OK: {total} processos sintéticos | {len(hist)} snapshots de histórico | {criticos} críticos")
    conn.close()


if __name__ == "__main__":
    main()
