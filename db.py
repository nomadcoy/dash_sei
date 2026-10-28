from __future__ import annotations

import re
import sqlite3
import threading

from cfg import RAIZ

DB_PATH = RAIZ / "data" / "sei.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS extracoes (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    fonte           TEXT NOT NULL,
    ts_inicio       TEXT NOT NULL,
    ts_fim          TEXT,
    status          TEXT NOT NULL,
    detalhe         TEXT,
    total_processos INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS processos (
    numero               TEXT NOT NULL,
    unidade              TEXT NOT NULL,
    tipo_processo        TEXT,
    assunto              TEXT,
    especificacao        TEXT,
    situacao             TEXT,
    prioridade           INTEGER NOT NULL DEFAULT 0,
    marcadores           TEXT NOT NULL DEFAULT '[]',
    prioridade_nivel     TEXT,
    controle_prazo       TEXT,
    prazo_vencimento     TEXT,
    dias_atraso          INTEGER,
    para_devolver        TEXT,
    sem_atribuicao       INTEGER NOT NULL DEFAULT 0,
    data_autuacao        TEXT,
    data_conclusao       TEXT,
    ultima_movimentacao  TEXT,
    unidade_atual        TEXT,
    responsavel          TEXT,
    idas_vindas          INTEGER NOT NULL DEFAULT 0,
    criticidade          INTEGER NOT NULL DEFAULT 0,
    criticidade_fatores  TEXT NOT NULL DEFAULT '{}',
    link_sei             TEXT,
    atualizado_em        TEXT NOT NULL,
    extracao_id          INTEGER REFERENCES extracoes(id),
    eixo                 TEXT,
    PRIMARY KEY (numero, unidade)
);

CREATE TABLE IF NOT EXISTS painel_unidades (
    extracao_id         INTEGER NOT NULL REFERENCES extracoes(id),
    unidade             TEXT NOT NULL,
    total               INTEGER,
    recebidos           INTEGER,
    gerados             INTEGER,
    nao_visualizados    INTEGER,
    atribuidos_a_mim    INTEGER,
    sem_acompanhamento  INTEGER,
    alterados           INTEGER,
    prioritarios        INTEGER,
    prazos_json         TEXT DEFAULT '{}',
    retornos_json       TEXT DEFAULT '{}',
    blocos_json         TEXT DEFAULT '{}',
    grupos_json         TEXT DEFAULT '{}',
    tipos_json          TEXT DEFAULT '{}',
    ts                  TEXT NOT NULL,
    PRIMARY KEY (extracao_id, unidade)
);

CREATE TABLE IF NOT EXISTS historico_processos (
    extracao_id         INTEGER NOT NULL REFERENCES extracoes(id),
    numero              TEXT NOT NULL,
    unidade             TEXT NOT NULL,
    unidade_atual       TEXT,
    situacao            TEXT,
    ultima_movimentacao TEXT,
    ts                  TEXT NOT NULL,
    PRIMARY KEY (extracao_id, numero)
);

CREATE TABLE IF NOT EXISTS estatisticas (
    extracao_id  INTEGER NOT NULL REFERENCES extracoes(id),
    unidade      TEXT NOT NULL,
    tabela       TEXT NOT NULL,
    periodo_de   TEXT NOT NULL,
    periodo_ate  TEXT NOT NULL,
    tipo         TEXT NOT NULL,
    mes          TEXT,
    valor        REAL NOT NULL DEFAULT 0,
    detalhe      TEXT,
    ts           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_processos_unidade   ON processos(unidade);
CREATE INDEX IF NOT EXISTS idx_processos_situacao  ON processos(situacao);
CREATE INDEX IF NOT EXISTS idx_processos_critic    ON processos(criticidade DESC);
CREATE INDEX IF NOT EXISTS idx_processos_tipo      ON processos(tipo_processo);
CREATE INDEX IF NOT EXISTS idx_hist_ts             ON historico_processos(ts);
CREATE INDEX IF NOT EXISTS idx_estat_unidade       ON estatisticas(unidade);
CREATE INDEX IF NOT EXISTS idx_estat_tabela        ON estatisticas(tabela);
CREATE INDEX IF NOT EXISTS idx_estat_mes           ON estatisticas(mes);
"""


_inicializado = False
_lock_init = threading.Lock()


def conectar() -> sqlite3.Connection:
    global _inicializado
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    if not _inicializado:
        with _lock_init:
            if not _inicializado:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.executescript(SCHEMA)
                _migrar(conn)
                _inicializado = True
    return conn


_COLUNAS_NOVAS = {
    "prioridade_nivel": "TEXT",
    "controle_prazo": "TEXT",
    "prazo_vencimento": "TEXT",
    "dias_atraso": "INTEGER",
    "para_devolver": "TEXT",
    "sem_atribuicao": "INTEGER DEFAULT 0",
    "eixo": "TEXT",
}

_COLS_NOVAS_TABELA = [
    "numero", "unidade", "tipo_processo", "assunto", "especificacao", "situacao",
    "prioridade", "marcadores", "prioridade_nivel", "controle_prazo",
    "prazo_vencimento", "dias_atraso", "para_devolver", "sem_atribuicao",
    "data_autuacao", "data_conclusao", "ultima_movimentacao", "unidade_atual",
    "responsavel", "idas_vindas", "criticidade", "criticidade_fatores",
    "link_sei", "atualizado_em", "extracao_id", "eixo",
]


def _migrar(conn: sqlite3.Connection) -> None:
    """Adiciona colunas que não existiam em bancos antigos (ALTER TABLE)."""
    existentes = {r[1] for r in conn.execute("PRAGMA table_info(processos)")}
    for nome, tipo in _COLUNAS_NOVAS.items():
        if nome not in existentes:
            conn.execute(f"ALTER TABLE processos ADD COLUMN {nome} {tipo}")
    _migrar_chave_composta(conn)
    cols_estat = {r[1] for r in conn.execute("PRAGMA table_info(estatisticas)")}
    if "detalhe" not in cols_estat:
        conn.execute("ALTER TABLE estatisticas ADD COLUMN detalhe TEXT")
    conn.commit()


def _migrar_chave_composta(conn: sqlite3.Connection) -> None:
    """Recria processos com PRIMARY KEY (numero, unidade) se ainda tiver PK antiga."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='processos'"
    ).fetchone()
    if not row or "PRIMARY KEY (numero, unidade)" in (row[0] or ""):
        return
    conn.execute("ALTER TABLE processos RENAME TO processos_ant")
    conn.executescript(SCHEMA)
    cols = ", ".join(f'"{c}"' for c in _COLS_NOVAS_TABELA)
    conn.execute(f"INSERT INTO processos ({cols}) SELECT {cols} FROM processos_ant")
    conn.execute("DROP TABLE processos_ant")


def nova_extracao(conn: sqlite3.Connection, fonte: str, ts_inicio: str) -> int:
    cur = conn.execute(
        "INSERT INTO extracoes (fonte, ts_inicio, status) VALUES (?, ?, 'em_andamento')",
        (fonte, ts_inicio),
    )
    conn.commit()
    return int(cur.lastrowid)


def finalizar_extracao(
    conn: sqlite3.Connection,
    extracao_id: int,
    status: str,
    detalhe: str = "",
    total: int = 0,
) -> None:
    from datetime import datetime, timezone

    conn.execute(
        """UPDATE extracoes
           SET ts_fim = ?, status = ?, detalhe = ?, total_processos = ?
           WHERE id = ?""",
        (datetime.now(timezone.utc).isoformat(timespec="seconds"), status, detalhe, total, extracao_id),
    )
    conn.commit()


def gravar_painel(
    conn: sqlite3.Connection,
    extracao_id: int,
    unidade: str,
    cartoes: dict,
    tabelas: dict,
    ts: str,
) -> None:
    import json

    conn.execute(
        """INSERT OR REPLACE INTO painel_unidades
           (extracao_id, unidade, total, recebidos, gerados, nao_visualizados,
            atribuidos_a_mim, sem_acompanhamento, alterados, prioritarios,
            prazos_json, retornos_json, blocos_json, grupos_json, tipos_json, ts)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            extracao_id,
            unidade,
            cartoes.get("total"),
            cartoes.get("recebidos"),
            cartoes.get("gerados"),
            cartoes.get("nao_visualizados"),
            cartoes.get("atribuidos_a_mim"),
            cartoes.get("sem_acompanhamento"),
            cartoes.get("alterados"),
            cartoes.get("prioritarios"),
            json.dumps(tabelas.get("prazos", []), ensure_ascii=False),
            json.dumps(tabelas.get("retornos", []), ensure_ascii=False),
            json.dumps(tabelas.get("blocos", []), ensure_ascii=False),
            json.dumps(tabelas.get("grupos", []), ensure_ascii=False),
            json.dumps(tabelas.get("tipos", []), ensure_ascii=False),
            ts,
        ),
    )
    conn.commit()


def gravar_historico(
    conn: sqlite3.Connection,
    extracao_id: int,
    ts: str,
    registros: list[sqlite3.Row | dict],
) -> None:
    conn.executemany(
        """INSERT OR REPLACE INTO historico_processos
           (extracao_id, numero, unidade, unidade_atual, situacao, ultima_movimentacao, ts)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                extracao_id,
                r["numero"],
                r["unidade"],
                r.get("unidade_atual"),
                r.get("situacao"),
                r.get("ultima_movimentacao"),
                ts,
            )
            for r in registros
        ],
    )
    conn.commit()


def gravar_estatisticas(
    conn: sqlite3.Connection,
    extracao_id: int,
    unidade: str,
    periodo_de: str,
    periodo_ate: str,
    registros: list[dict],
    ts: str,
) -> None:
    """Persiste as tabelas de Estatísticas da Unidade (menor nível agregado já vem
    do SEI; guardamos todo registro por (unidade, tabela, tipo, mes)."""
    conn.executemany(
        """INSERT INTO estatisticas
           (extracao_id, unidade, tabela, periodo_de, periodo_ate, tipo, mes, valor, detalhe, ts)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                extracao_id,
                unidade,
                r["tabela"],
                periodo_de,
                periodo_ate,
                r["tipo"],
                r.get("mes"),
                _valor_num(r.get("valor")),
                r.get("detalhe"),
                ts,
            )
            for r in registros
        ],
    )
    conn.commit()


def limpar_estatisticas_antigas(conn: sqlite3.Connection) -> int:
    """Mantém apenas a última extração de cada unidade (o dashboard só lê a mais
    recente por unidade); retorna quantas linhas antigas removiu."""
    cur = conn.execute(
        """DELETE FROM estatisticas WHERE extracao_id NOT IN
           (SELECT MAX(extracao_id) FROM estatisticas GROUP BY unidade)"""
    )
    conn.commit()
    return cur.rowcount


def _valor_num(v) -> float:
    """Transforma valor em número: '15d 3h 52m 5s' → dias; inteiro permanece."""
    if isinstance(v, (int, float)):
        return float(v)
    if not isinstance(v, str):
        return 0.0
    m = re.match(r"(\d+)d\s+(\d+)h\s+(\d+)m\s+(\d+)s", v.strip())
    if m:
        d, h, mi, s = (int(x) for x in m.groups())
        return round(d + h / 24 + mi / 1440 + s / 86400, 3)
    return float(v.replace(",", ".")) if v.replace(",", "").replace(".", "").replace("-", "").isdigit() else 0.0
