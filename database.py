import sqlite3

import psycopg2

# ------------------ CONEXÃO ------------------ #
def conectar():
    return psycopg2.connect(
        host="db.yovuvhuubopujagvukki.supabase.co",
        database="postgres",
        user="postgres",
        password="AnneCarol91",
        port="5432"
    )

# ------------------ CRIAR TABELAS ------------------ #
def criar_tabelas():
    conn = conectar()
    cursor = conn.cursor()

    # -------- USUÁRIOS -------- #
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT NOT NULL,
        usuario TEXT UNIQUE NOT NULL,
        senha TEXT NOT NULL,
        nivel TEXT NOT NULL
    )
    """)

    # -------- PRODUTOS -------- #
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS produtos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nome TEXT UNIQUE NOT NULL,
        classe TEXT NOT NULL,
        unidade TEXT NOT NULL,
        kg REAL NOT NULL
    )
    """)

    # -------- COTAÇÕES -------- #
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

# ------------------ CRIAR ADMIN PADRÃO ------------------ #
def criar_admin():
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
    INSERT OR IGNORE INTO usuarios (id, nome, usuario, senha, nivel)
    VALUES (1, 'Administrador', 'admin', '123', 'admin')
    """)

    conn.commit()
    conn.close()

# ------------------ EXECUÇÃO ------------------ #
if __name__ == "__main__":
    criar_tabelas()
    criar_admin()
    print("Banco criado/atualizado com sucesso!")
