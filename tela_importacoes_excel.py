import re
import unicodedata
import streamlit as st
import pandas as pd

from utils import corrigir_classe

from dados_utils import carregar_produtos


TABELA_COTACOES = "cotacoes"
TABELA_VOLUMES = "volumes_ano_anterior"


def limpar_nome_coluna(nome):
    nome = str(nome).strip().lower()
    nome = unicodedata.normalize("NFKD", nome)
    nome = nome.encode("ascii", "ignore").decode("utf-8")
    nome = re.sub(r"[^a-z0-9]+", "_", nome)
    nome = nome.strip("_")
    return nome

def normalizar_nome_produto(valor):
    texto = str(valor).strip().upper()
    texto = texto.replace("_", " ")
    texto = texto.replace("-", " ")

    texto = unicodedata.normalize("NFKD", texto)
    texto = texto.encode("ascii", "ignore").decode("utf-8")

    texto = re.sub(r"\s+", " ", texto)
    texto = texto.strip()

    return texto

def padronizar_colunas(df):
    df = df.copy()

    mapa = {}

    for col in df.columns:
        c = limpar_nome_coluna(col)

        aliases = {
            "data": "data",
            "classe": "classe",
            "produto": "produto",
            "unidade": "unidade",
            "kg": "kg",
            "preco_min": "preco_min",
            "preco_minimo": "preco_min",
            "preco_mín": "preco_min",
            "preco_max": "preco_max",
            "preco_maximo": "preco_max",
            "preco_medio": "preco_medio",
            "preco_medio_r": "preco_medio",
            "valor_kg": "valor_kg",
            "valor_por_kg": "valor_kg",
            "mes_ano": "mes_ano",
            "mes": "mes",
            "ano": "ano",
            "quantidade": "quantidade_kg",
            "quantidade_kg": "quantidade_kg",
            "volume": "quantidade_kg",
            "volume_kg": "quantidade_kg",
        }

        mapa[col] = aliases.get(c, c)

    df = df.rename(columns=mapa)

    return df


def converter_numero(valor):
    if pd.isna(valor):
        return 0

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = str(valor).strip()
    texto = texto.replace("R$", "").replace(" ", "")

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return 0


def salvar_em_lotes(supabase, tabela, registros, tamanho_lote=500, upsert=False, on_conflict=None):
    total = 0

    for i in range(0, len(registros), tamanho_lote):
        lote = registros[i:i + tamanho_lote]

        if upsert:
            supabase.table(tabela).upsert(
                lote,
                on_conflict=on_conflict
            ).execute()
        else:
            supabase.table(tabela).insert(lote).execute()

        total += len(lote)

    return total


def preparar_cotacoes_antigas(df, df_produtos):
    df = padronizar_colunas(df)

    colunas_obrigatorias = [
        "data",
        "produto",
        "preco_min",
        "preco_max"
    ]

    faltando = [c for c in colunas_obrigatorias if c not in df.columns]

    if faltando:
        raise ValueError(
            "A planilha de cotações antigas está sem estas colunas: "
            + ", ".join(faltando)
        )

    df = df[colunas_obrigatorias].copy()

    # ================= TRATAR DATA E PRODUTO =================
    df["data"] = pd.to_datetime(df["data"], errors="coerce", dayfirst=True)
    df = df.dropna(subset=["data"])

    df["produto"] = df["produto"].apply(normalizar_nome_produto)

    # ================= TRATAR PREÇOS =================
    df["preco_min"] = df["preco_min"].apply(converter_numero)
    df["preco_max"] = df["preco_max"].apply(converter_numero)

    df = df[
        (df["preco_min"] > 0) &
        (df["preco_max"] > 0)
    ].copy()

    # ================= CALCULAR PREÇO MÉDIO =================
    df["preco_medio"] = (
        df["preco_min"] + df["preco_max"]
    ) / 2

    # ================= BUSCAR DADOS DO PRODUTO NO BANCO =================
    df_produtos = df_produtos.copy()

    df_produtos["nome"] = df_produtos["nome"].apply(normalizar_nome_produto)
    df_produtos["classe"] = df_produtos["classe"].astype(str).str.strip().apply(corrigir_classe)
    df_produtos["unidade"] = df_produtos["unidade"].astype(str).str.strip().str.upper()

    if "kg" not in df_produtos.columns:
        df_produtos["kg"] = 1

    df_produtos["kg"] = df_produtos["kg"].apply(converter_numero)
    df_produtos["kg"] = df_produtos["kg"].fillna(1)
    df_produtos["kg"] = df_produtos["kg"].apply(lambda x: int(round(float(x))) if float(x) > 0 else 1)

    df_base_produtos = df_produtos[
        ["nome", "classe", "unidade", "kg"]
    ].copy()

    df = df.merge(
        df_base_produtos,
        left_on="produto",
        right_on="nome",
        how="left"
    )

    df["kg"] = df["kg"].fillna(1)
    df["kg"] = df["kg"].apply(lambda x: int(round(float(x))) if float(x) > 0 else 1)

    produtos_nao_encontrados = df[df["classe"].isna()]["produto"].unique().tolist()

    if produtos_nao_encontrados:
        raise ValueError(
            "Estes produtos não foram encontrados no cadastro de produtos: "
            + ", ".join(produtos_nao_encontrados)
        )

    df = df.drop(columns=["nome"])

    # ================= CALCULAR VALOR POR KG =================
    df["valor_kg"] = df.apply(
        lambda row: row["preco_medio"] / row["kg"]
        if row["kg"] and row["kg"] > 0
        else row["preco_medio"],
        axis=1
    )

    # ================= FORMATAR DATA PARA O BANCO =================
    df["data"] = df["data"].dt.strftime("%Y-%m-%d")

    df = df[
        [
            "data",
            "classe",
            "produto",
            "unidade",
            "kg",
            "preco_min",
            "preco_max",
            "preco_medio",
            "valor_kg"
        ]
    ]

    return df


def preparar_volumes_ano_anterior(df, df_produtos):
    df = padronizar_colunas(df)

    colunas_obrigatorias = [
        "mes_ano",
        "produto",
        "quantidade_kg"
    ]

    faltando = [c for c in colunas_obrigatorias if c not in df.columns]

    if faltando:
        raise ValueError(
            "A planilha de volumes está sem estas colunas: "
            + ", ".join(faltando)
            + ". Use apenas: mes_ano, produto e quantidade_kg."
        )

    df = df[colunas_obrigatorias].copy()

    df["produto"] = df["produto"].apply(normalizar_nome_produto)
    df["quantidade_kg"] = df["quantidade_kg"].apply(converter_numero)

    def converter_mes_ano(valor):
        if pd.isna(valor):
            return None

        if isinstance(valor, pd.Timestamp):
            data = valor
        else:
            texto = str(valor).strip()

            if re.match(r"^\d{1,2}/\d{4}$", texto):
                texto = "01/" + texto

            data = pd.to_datetime(texto, errors="coerce", dayfirst=True)

        if pd.isna(data):
            return None

        return {
            "mes_ano": data.strftime("%m/%Y"),
            "ano": int(data.year),
            "mes": int(data.month)
        }

    dados_datas = df["mes_ano"].apply(converter_mes_ano)

    df["mes_ano"] = dados_datas.apply(lambda x: x["mes_ano"] if x else None)
    df["ano"] = dados_datas.apply(lambda x: x["ano"] if x else None)
    df["mes"] = dados_datas.apply(lambda x: x["mes"] if x else None)

    df = df.dropna(subset=["mes_ano", "ano", "mes"])
    df = df[df["quantidade_kg"] > 0].copy()

    df["ano"] = df["ano"].astype(int)
    df["mes"] = df["mes"].astype(int)

    # ================= BUSCAR CLASSE NO CADASTRO DE PRODUTOS =================
    df_produtos = df_produtos.copy()
    df_produtos.columns = [limpar_nome_coluna(c) for c in df_produtos.columns]

    # O cadastro pode vir com a coluna "nome" ou "produto".
    # Internamente, vamos usar sempre "nome".
    if "nome" not in df_produtos.columns and "produto" in df_produtos.columns:
        df_produtos = df_produtos.rename(columns={"produto": "nome"})

    if "nome" not in df_produtos.columns:
        raise ValueError("A tabela de produtos precisa ter a coluna 'nome' ou 'produto'.")

    if "classe" not in df_produtos.columns:
        raise ValueError("A tabela de produtos precisa ter a coluna 'classe'.")

    df_produtos["nome"] = df_produtos["nome"].apply(normalizar_nome_produto)
    df_produtos["classe"] = df_produtos["classe"].astype(str).str.strip().apply(corrigir_classe)

    df_base_produtos = (
        df_produtos[["nome", "classe"]]
        .drop_duplicates(subset=["nome"])
        .copy()
    )

    df = df.merge(
        df_base_produtos,
        left_on="produto",
        right_on="nome",
        how="left"
    )

    produtos_nao_encontrados = df[df["classe"].isna()]["produto"].unique().tolist()

    if produtos_nao_encontrados:
        raise ValueError(
            "Estes produtos não foram encontrados no cadastro de produtos: "
            + ", ".join(produtos_nao_encontrados)
        )

    df = df.drop(columns=["nome"])

    df = df[
        [
            "mes_ano",
            "ano",
            "mes",
            "classe",
            "produto",
            "quantidade_kg"
        ]
    ]

    df = (
        df
        .groupby(["mes_ano", "ano", "mes", "classe", "produto"], as_index=False)
        .agg({"quantidade_kg": "sum"})
    )

    return df


def remover_cotacoes_duplicadas(supabase, df_importacao):
    try:
        resp = (
            supabase
            .table(TABELA_COTACOES)
            .select("data, produto")
            .execute()
        )

        existentes = set()

        for item in resp.data:
            data = str(item.get("data", ""))[:10]
            produto = str(item.get("produto", "")).strip().upper()
            existentes.add((data, produto))

        df = df_importacao.copy()

        df["_chave"] = list(zip(
            df["data"].astype(str),
            df["produto"].astype(str).str.strip().str.upper()
        ))

        df = df[~df["_chave"].isin(existentes)].copy()
        df = df.drop(columns=["_chave"])

        return df

    except Exception:
        return df_importacao


def tela_importacoes_excel(supabase):
    st.title("📥 Importações por Excel")

    st.info(
        "Nesta tela você poderá importar cotações antigas e volumes do ano anterior "
        "por planilhas Excel."
    )

    aba1, aba2 = st.tabs([
        "📊 Importar cotações antigas",
        "📦 Importar volumes do ano anterior"
    ])

    with aba1:
        st.subheader("📊 Importar cotações antigas")

        st.markdown(
            """
            A planilha deve ter estas colunas:

            `data`, `produto`, `preco_min`, `preco_max`

            O sistema buscará automaticamente `classe`, `unidade` e `kg` no cadastro de produtos.

            O `preco_medio` será calculado por:

            `(preco_min + preco_max) / 2`

            O `valor_kg` será calculado por:

            `preco_medio / kg`
            """
        )

        arquivo_cotacoes = st.file_uploader(
            "Selecione o Excel das cotações antigas",
            type=["xlsx"],
            key="upload_cotacoes_antigas"
        )

        ignorar_duplicadas = st.checkbox(
            "Ignorar cotações duplicadas por data e produto",
            value=True,
            key="ignorar_duplicadas_cotacoes"
        )

        if arquivo_cotacoes is not None:
            try:
                df_excel = pd.read_excel(arquivo_cotacoes)

                df_produtos = carregar_produtos(supabase)

                df_preparado = preparar_cotacoes_antigas(
                    df_excel,
                    df_produtos
                )

                if ignorar_duplicadas:
                    df_preparado = remover_cotacoes_duplicadas(
                        supabase,
                        df_preparado
                    )

                st.success(f"{len(df_preparado)} cotação(ões) pronta(s) para importar.")

                st.dataframe(
                    df_preparado.head(50),
                    use_container_width=True
                )

                if st.button("💾 Salvar cotações antigas no banco", type="primary"):
                    registros = df_preparado.to_dict(orient="records")

                    if not registros:
                        st.warning("Não há registros novos para salvar.")
                    else:
                        total = salvar_em_lotes(
                            supabase,
                            TABELA_COTACOES,
                            registros,
                            upsert=False
                        )

                        st.success(f"{total} cotação(ões) importada(s) com sucesso.")

            except Exception as e:
                st.error(f"Erro ao importar cotações antigas: {e}")

    with aba2:
        st.subheader("📦 Importar volumes do ano anterior")

        st.markdown(
            """
            A planilha deve ter estas colunas:

            `mes_ano`, `produto`, `quantidade_kg`

            Exemplo: `05/2025`, `ABACATE`, `12000`

            A `classe` será puxada automaticamente do cadastro de produtos.
            """
        )

        arquivo_volumes = st.file_uploader(
            "Selecione o Excel dos volumes do ano anterior",
            type=["xlsx"],
            key="upload_volumes_ano_anterior"
        )

        if arquivo_volumes is not None:
            try:
                df_excel = pd.read_excel(arquivo_volumes)
                df_produtos = carregar_produtos(supabase)

                if df_produtos.empty:
                    st.error("A tabela de produtos está vazia. Cadastre os produtos antes de importar os volumes.")
                    return

                df_preparado = preparar_volumes_ano_anterior(
                    df_excel,
                    df_produtos
                )

                st.success(f"{len(df_preparado)} volume(s) pronto(s) para importar.")

                st.dataframe(
                    df_preparado.head(50),
                    use_container_width=True
                )

                if st.button("💾 Salvar volumes no banco", type="primary"):
                    registros = df_preparado.to_dict(orient="records")

                    if not registros:
                        st.warning("Não há registros para salvar.")
                    else:
                        total = salvar_em_lotes(
                            supabase,
                            TABELA_VOLUMES,
                            registros,
                            upsert=True,
                            on_conflict="ano,mes,classe,produto"
                        )

                        st.success(f"{total} volume(s) importado(s) com sucesso.")

            except Exception as e:
                st.error(f"Erro ao importar volumes: {e}")