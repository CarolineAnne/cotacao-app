"""
Script legado da versão SQLite local.

O app atual usa Supabase em `db.py`. Este arquivo fica isolado em `legacy/`
apenas para consulta histórica ou recuperação manual de dados antigos.
"""

import sqlite3
from pathlib import Path


DB_LOCAL = Path(__file__).with_name("database.db")


def conectar():
    return sqlite3.connect(DB_LOCAL)


def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        usuario TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        nivel TEXT NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        classe TEXT NOT NULL,
        unidade TEXT NOT NULL,
        kg REAL NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cotacoes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        data TEXT NOT NULL,
        classe TEXT NOT NULL,
        produto TEXT NOT NULL,
        unidade TEXT NOT NULL,
        kg REAL NOT NULL,
        preco_min REAL NOT NULL,
        preco_max REAL NOT NULL,
        preco_medio REAL NOT NULL,
        valor_kg REAL NOT NULL
    )
    """)

    conn.commit()
    conn.close()


if __name__ == "__main__":
    print(
        "Este script e legado e nao e usado pelo app atual. "
        "Use apenas para consulta ou recuperacao manual de dados antigos."
    )
