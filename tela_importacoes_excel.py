import re
import unicodedata
from datetime import datetime

import streamlit as st
import pandas as pd

from utils import corrigir_classe

from dados_utils import carregar_produtos


TABELA_COTACOES = "cotacoes"
TABELA_VOLUMES = "volumes_ano_anterior"


# =========================================================
# FUNÇÕES GERAIS
# =========================================================
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


def limpar_texto_busca(valor):
    texto = str(valor or "").strip().upper()

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
            "produtos": "produto",
            "unidade": "unidade",
            "unid": "unidade",
            "kg": "kg",
            "preco_min": "preco_min",
            "preco_minimo": "preco_min",
            "minimo": "preco_min",
            "preco_max": "preco_max",
            "preco_maximo": "preco_max",
            "maximo": "preco_max",
            "preco_medio": "preco_medio",
            "preco_medio_r": "preco_medio",
            "comum": "preco_medio",
            "valor_kg": "valor_kg",
            "valor_por_kg": "valor_kg",
            "valor_kg_r": "valor_kg",
            "valor_por_kg_r": "valor_kg",
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
    texto = texto.replace("\xa0", "")

    if texto in ["", "-", "--", "#REF!", "#DIV/0!", "#N/A", "NAN", "nan"]:
        return 0

    if "," in texto and "." in texto:
        texto = texto.replace(".", "").replace(",", ".")
    elif "," in texto:
        texto = texto.replace(",", ".")

    try:
        return float(texto)
    except Exception:
        return 0


def salvar_em_lotes(
    supabase,
    tabela,
    registros,
    tamanho_lote=500,
    upsert=False,
    on_conflict=None
):
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


# =========================================================
# COTAÇÕES ANTIGAS EM PLANILHA SIMPLES
# =========================================================
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
    df_produtos = preparar_base_produtos(df_produtos)

    df = df.merge(
        df_produtos,
        left_on="produto",
        right_on="nome",
        how="left"
    )

    df["kg"] = df["kg"].fillna(1)
    df["kg"] = df["kg"].apply(
        lambda x: int(round(float(x))) if float(x) > 0 else 1
    )

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


# =========================================================
# IMPORTAÇÃO DA PLANILHA COMPLETA DA AMA
# =========================================================
def identificar_classe_ama(valor):
    texto = limpar_texto_busca(valor)

    if texto in ["HORTALICAS", "HORTALICA", "HORTALIÇAS", "HORTALIÇA"]:
        return "Hortaliças"

    if texto in ["FRUTAS", "FRUTA"]:
        return "Frutas"

    if texto in ["ESPECIARIAS", "ESPECIARIA"]:
        return "Especiarias"

    if texto in ["CEREAIS", "CEREAL"]:
        return "Cereais"

    return None


def eh_linha_cabecalho_produtos(row):
    for idx, valor in enumerate(row):
        texto = limpar_nome_coluna(valor)

        if texto in ["produtos", "produto"]:
            return idx

    return None


def converter_data_nome_aba(nome_aba):
    texto = str(nome_aba).strip()

    if re.match(r"^\d{8}$", texto):
        try:
            return datetime.strptime(texto, "%d%m%Y")
        except Exception:
            return None

    return None


def preparar_base_produtos(df_produtos):
    if df_produtos is None or df_produtos.empty:
        return pd.DataFrame(
            columns=[
                "nome",
                "classe",
                "unidade",
                "kg"
            ]
        )

    df_produtos = df_produtos.copy()
    df_produtos.columns = [
        limpar_nome_coluna(c)
        for c in df_produtos.columns
    ]

    if "nome" not in df_produtos.columns and "produto" in df_produtos.columns:
        df_produtos = df_produtos.rename(columns={"produto": "nome"})

    if "nome" not in df_produtos.columns:
        df_produtos["nome"] = ""

    if "classe" not in df_produtos.columns:
        df_produtos["classe"] = "SEM CLASSE"

    if "unidade" not in df_produtos.columns:
        df_produtos["unidade"] = ""

    if "kg" not in df_produtos.columns:
        df_produtos["kg"] = 1

    df_produtos["nome"] = df_produtos["nome"].apply(normalizar_nome_produto)
    df_produtos["classe"] = (
        df_produtos["classe"]
        .astype(str)
        .str.strip()
        .apply(corrigir_classe)
    )
    df_produtos["unidade"] = (
        df_produtos["unidade"]
        .astype(str)
        .str.strip()
        .str.upper()
    )
    df_produtos["kg"] = df_produtos["kg"].apply(converter_numero)
    df_produtos["kg"] = df_produtos["kg"].apply(
        lambda x: int(round(float(x))) if float(x) > 0 else 1
    )

    df_produtos = (
        df_produtos[
            [
                "nome",
                "classe",
                "unidade",
                "kg"
            ]
        ]
        .drop_duplicates(subset=["nome"])
        .copy()
    )

    return df_produtos


def produto_deve_ser_ignorado(valor):
    texto = limpar_texto_busca(valor)

    if not texto:
        return True

    termos_ignorar = [
        "PRODUTO",
        "PRODUTOS",
        "TOTAL",
        "MEDIA",
        "MEDIO",
        "OBS",
        "OBSERVACAO",
        "DIRETOR",
        "FONE",
        "DATA"
    ]

    if texto in termos_ignorar:
        return True

    return False


def extrair_cotacoes_aba_ama(df_raw, nome_aba, df_produtos_base):
    data_aba = converter_data_nome_aba(nome_aba)

    if data_aba is None:
        return pd.DataFrame(), {
            "Aba": nome_aba,
            "Data": "",
            "Registros": 0,
            "Status": "Ignorada: nome da aba não é uma data"
        }, []

    registros = []
    avisos = []
    classe_atual = "SEM CLASSE"

    col_produto = None
    col_unidade = None
    col_kg = None
    col_min = None
    col_max = None
    col_comum = None

    mapa_produtos = {}

    if df_produtos_base is not None and not df_produtos_base.empty:
        for _, produto_db in df_produtos_base.iterrows():
            mapa_produtos[produto_db["nome"]] = {
                "classe": produto_db.get("classe", "SEM CLASSE"),
                "unidade": produto_db.get("unidade", ""),
                "kg": produto_db.get("kg", 1)
            }

    for _, row in df_raw.iterrows():
        valores_linha = row.tolist()

        # Primeiro procura uma classe em qualquer célula da linha.
        for valor in valores_linha:
            classe_identificada = identificar_classe_ama(valor)

            if classe_identificada:
                classe_atual = corrigir_classe(classe_identificada)
                break

        # Depois verifica se a linha é cabeçalho da tabela de produtos.
        indice_produtos = eh_linha_cabecalho_produtos(valores_linha)

        if indice_produtos is not None:
            col_produto = indice_produtos
            col_unidade = indice_produtos + 1
            col_kg = indice_produtos + 2
            col_min = indice_produtos + 3
            col_max = indice_produtos + 4
            col_comum = indice_produtos + 5
            continue

        if col_produto is None:
            continue

        # Garante que a linha tenha colunas suficientes.
        if len(valores_linha) <= col_max:
            continue

        produto_original = valores_linha[col_produto]

        if produto_deve_ser_ignorado(produto_original):
            continue

        classe_na_linha = identificar_classe_ama(produto_original)

        if classe_na_linha:
            classe_atual = corrigir_classe(classe_na_linha)
            continue

        produto = normalizar_nome_produto(produto_original)

        unidade_planilha = ""
        kg_planilha = 1
        preco_min = 0
        preco_max = 0
        preco_medio_planilha = 0

        if len(valores_linha) > col_unidade:
            unidade_planilha = str(valores_linha[col_unidade]).strip().upper()

        if len(valores_linha) > col_kg:
            kg_planilha = converter_numero(valores_linha[col_kg])

        if len(valores_linha) > col_min:
            preco_min = converter_numero(valores_linha[col_min])

        if len(valores_linha) > col_max:
            preco_max = converter_numero(valores_linha[col_max])

        if len(valores_linha) > col_comum:
            preco_medio_planilha = converter_numero(valores_linha[col_comum])

        if kg_planilha <= 0:
            kg_planilha = 1

        if preco_min <= 0 and preco_max <= 0 and preco_medio_planilha <= 0:
            continue

        if preco_min <= 0 and preco_medio_planilha > 0:
            preco_min = preco_medio_planilha

        if preco_max <= 0 and preco_medio_planilha > 0:
            preco_max = preco_medio_planilha

        if preco_min <= 0 or preco_max <= 0:
            continue

        if preco_medio_planilha > 0:
            preco_medio = preco_medio_planilha
        else:
            preco_medio = (
                preco_min + preco_max
            ) / 2

        dados_cadastro = mapa_produtos.get(produto)

        if dados_cadastro:
            classe = dados_cadastro.get("classe", classe_atual)
            unidade = dados_cadastro.get("unidade", unidade_planilha) or unidade_planilha
            kg = dados_cadastro.get("kg", kg_planilha) or kg_planilha
        else:
            classe = classe_atual
            unidade = unidade_planilha
            kg = kg_planilha

            if len(avisos) < 20:
                avisos.append(
                    f"Produto não encontrado no cadastro e importado com dados da planilha: {produto}"
                )

        kg = converter_numero(kg)

        if kg <= 0:
            kg = 1

        valor_kg = (
            preco_medio / kg
            if kg > 0
            else preco_medio
        )

        registros.append({
            "data": data_aba.strftime("%Y-%m-%d"),
            "classe": corrigir_classe(classe),
            "produto": produto,
            "unidade": unidade,
            "kg": int(round(float(kg))) if float(kg) > 0 else 1,
            "preco_min": float(preco_min),
            "preco_max": float(preco_max),
            "preco_medio": float(preco_medio),
            "valor_kg": float(valor_kg)
        })

    df_aba = pd.DataFrame(registros)

    resumo = {
        "Aba": nome_aba,
        "Data": data_aba.strftime("%d/%m/%Y"),
        "Registros": len(df_aba),
        "Status": "Lida" if len(df_aba) > 0 else "Sem registros válidos"
    }

    return df_aba, resumo, avisos


def preparar_cotacoes_planilha_ama(arquivo_excel, df_produtos):
    if hasattr(arquivo_excel, "seek"):
        arquivo_excel.seek(0)

    xls = pd.ExcelFile(arquivo_excel)
    df_produtos_base = preparar_base_produtos(df_produtos)

    partes = []
    resumos = []
    avisos = []

    abas_data = [
        aba for aba in xls.sheet_names
        if converter_data_nome_aba(aba) is not None
    ]

    if not abas_data:
        raise ValueError(
            "Nenhuma aba com nome de data foi encontrada. "
            "Use abas no formato 05012026, 06012026, 07012026..."
        )

    for aba in abas_data:
        try:
            df_raw = pd.read_excel(
                xls,
                sheet_name=aba,
                header=None
            )

            df_aba, resumo, avisos_aba = extrair_cotacoes_aba_ama(
                df_raw,
                aba,
                df_produtos_base
            )

            resumos.append(resumo)

            if not df_aba.empty:
                partes.append(df_aba)

            avisos.extend([
                f"{aba}: {aviso}"
                for aviso in avisos_aba
            ])

        except Exception as erro:
            resumos.append({
                "Aba": aba,
                "Data": "",
                "Registros": 0,
                "Status": f"Erro: {erro}"
            })

    if partes:
        df_final = pd.concat(
            partes,
            ignore_index=True
        )
    else:
        df_final = pd.DataFrame(
            columns=[
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
        )

    df_resumo = pd.DataFrame(resumos)

    return df_final, df_resumo, avisos


# =========================================================
# VOLUMES
# =========================================================
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
    df_produtos = preparar_base_produtos(df_produtos)

    df = df.merge(
        df_produtos[["nome", "classe"]],
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


def formatar_dataframe_importacao_cotacoes(df):
    df_exibir = df.copy()

    if "data" in df_exibir.columns:
        df_exibir["data"] = pd.to_datetime(
            df_exibir["data"],
            errors="coerce"
        ).dt.strftime("%d/%m/%Y")

    for coluna in [
        "preco_min",
        "preco_max",
        "preco_medio",
        "valor_kg"
    ]:
        if coluna in df_exibir.columns:
            df_exibir[coluna] = df_exibir[coluna].apply(
                lambda x: f"{float(x):.2f}".replace(".", ",")
            )

    return df_exibir


# =========================================================
# TELA
# =========================================================
def tela_importacoes_excel(supabase):
    st.title("📥 Importações por Excel")

    st.info(
        "Nesta tela você poderá importar cotações antigas, uma planilha completa "
        "da AMA com várias abas e volumes do ano anterior."
    )

    aba1, aba2, aba3 = st.tabs([
        "📊 Importar cotações antigas",
        "📑 Importar planilha completa da AMA",
        "📦 Importar volumes do ano anterior"
    ])

    with aba1:
        st.subheader("📊 Importar cotações antigas")

        st.markdown(
            """
            A planilha simples deve ter estas colunas:

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
                    formatar_dataframe_importacao_cotacoes(df_preparado.head(50)),
                    width="stretch"
                )

                if st.button(
                    "💾 Salvar cotações antigas no banco",
                    type="primary",
                    key="btn_salvar_cotacoes_antigas"
                ):
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
        st.subheader("📑 Importar planilha completa da AMA")

        st.markdown(
            """
            Esta opção lê a planilha no modelo da AMA, com várias abas por data.

            O sistema identifica automaticamente as abas com nome no formato:

            `05012026`, `06012026`, `07012026`...

            E ignora abas como:

            `MED MENSAL`, `VOLUME`, `AJUSTES`, `GRÁFICO`, `PlanilhaDinamica`.

            Dentro de cada aba, ele localiza a tabela com:

            `PRODUTOS`, `UNID.`, `KG`, `MÍNIMO`, `MÁXIMO`, `COMUM`, `VALOR / KG`.

            Quando a coluna `COMUM` estiver com erro ou vazia, o sistema calcula:

            `(MÍNIMO + MÁXIMO) / 2`
            """
        )

        arquivo_ama = st.file_uploader(
            "Selecione a planilha completa da AMA",
            type=["xlsx"],
            key="upload_planilha_completa_ama"
        )

        ignorar_duplicadas_ama = st.checkbox(
            "Ignorar cotações já existentes por data e produto",
            value=True,
            key="ignorar_duplicadas_planilha_ama"
        )

        if arquivo_ama is not None:
            try:
                df_produtos = carregar_produtos(supabase)

                df_preparado, resumo_abas, avisos = preparar_cotacoes_planilha_ama(
                    arquivo_ama,
                    df_produtos
                )

                total_lido = len(df_preparado)

                if ignorar_duplicadas_ama:
                    df_preparado = remover_cotacoes_duplicadas(
                        supabase,
                        df_preparado
                    )

                total_novo = len(df_preparado)

                st.success(
                    f"{total_lido} cotação(ões) lida(s) na planilha. "
                    f"{total_novo} cotação(ões) pronta(s) para importar."
                )

                st.subheader("Resumo das abas lidas")

                st.dataframe(
                    resumo_abas,
                    width="stretch",
                    hide_index=True
                )

                if avisos:
                    st.warning(
                        "Alguns produtos não foram encontrados no cadastro. "
                        "Eles foram importados usando classe, unidade e kg da própria planilha."
                    )

                    with st.expander("Ver avisos"):
                        for aviso in avisos[:80]:
                            st.write(f"- {aviso}")

                        if len(avisos) > 80:
                            st.write(
                                f"... e mais {len(avisos) - 80} aviso(s)."
                            )

                st.subheader("Prévia das cotações que serão importadas")

                st.dataframe(
                    formatar_dataframe_importacao_cotacoes(df_preparado.head(100)),
                    width="stretch"
                )

                if st.button(
                    "💾 Salvar planilha completa da AMA no banco",
                    type="primary",
                    key="btn_salvar_planilha_ama"
                ):
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

                        st.success(
                            f"{total} cotação(ões) da planilha completa importada(s) com sucesso."
                        )

            except Exception as e:
                st.error(f"Erro ao importar planilha completa da AMA: {e}")

    with aba3:
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
                    width="stretch"
                )

                if st.button(
                    "💾 Salvar volumes no banco",
                    type="primary",
                    key="btn_salvar_volumes_ano_anterior"
                ):
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
