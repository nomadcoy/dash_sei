# -*- coding: utf-8 -*-
"""Inspeção pontual: o que analise.py (motor de narrativa) realmente EXPÕE e
o que ele CHAMA de queries — para o panorama usar apenas o que existe."""
import ast
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
ARQ = RAIZ / "dashboard" / "analise.py"

src = ARQ.read_text(encoding="utf-8")
t = ast.parse(src)

print("=== defs TOLEVEL (exportadas por analise.py) ===")
for n in t.body:
    if isinstance(n, ast.FunctionDef):
        args = ", ".join(a.arg for a in n.args.args)
        print(f"  def {n.name}({args})")

print("\n=== imports TOPLEVEL de analise.py ===")
for n in t.body:
    if isinstance(n, ast.ImportFrom):
        print("  from", n.module, "import", ", ".join(a.name for a in n.names))
    elif isinstance(n, ast.Import):
        print("  import", ", ".join(a.name for a in n.names))

print("\n=== CHAMADAS por nome (Call func=Name) — deve existir em queries.py ou local ===")
chamadas = set()
for n in ast.walk(t):
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Name):
        chamadas.add(n.func.id)

defs_locais = {
    n.name for n in t.body if isinstance(n, ast.FunctionDef)
}
importados = set()
for n in t.body:
    if isinstance(n, ast.ImportFrom):
        importados |= {a.name for a in n.names}
    elif isinstance(n, ast.Import):
        importados |= {a.asname or a.name for a in n.names}
builtins = set(dir(__builtins__)) if isinstance(__builtins__, dict) else set(dir(__builtins__))

for c in sorted(chamadas):
    etiqueta = (
        "LOCAL" if c in defs_locais
        else "IMPORT" if c in importados
        else "BUILTIN" if c in builtins
        else "??? (precisa checar queries.py)"
    )
    print(f"  {c}  [{etiqueta}]")

print("\n=== queries.py: defs que existem (cruzamento) ===")
q = ast.parse((RAIZ / "dashboard" / "queries.py").read_text(encoding="utf-8"))
qdefs = {n.name: ", ".join(a.arg for a in n.args.args) for n in q.body if isinstance(n, ast.FunctionDef)}
for c in sorted(chamadas):
    if c in qdefs:
        print(f"  queries.{c}({qdefs[c]})")
    elif c not in defs_locais and c not in importados and c not in builtins:
        print(f"  XXX NAO EXISTE em queries.py: {c}")
