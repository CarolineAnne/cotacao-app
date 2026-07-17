# Legado SQLite

Esta pasta guarda arquivos antigos da versão local em SQLite.

O sistema atual usa Supabase por meio de `db.py` e `st.secrets`, então estes arquivos não fazem parte do fluxo principal do app.

## Arquivos

- `database_sqlite.py`: script antigo para criar tabelas SQLite locais.
- `database.db`: banco SQLite local antigo, mantido apenas como referência local.

## Cuidados

- Não use este banco como fonte oficial de dados.
- Não publique arquivos `.db` com dados reais.
- Se precisar recuperar algum dado antigo, faça uma cópia antes de abrir ou modificar o arquivo.
