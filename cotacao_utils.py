import pandas as pd

from utils import corrigir_classe, normalizar_lista_precos


ORDEM_CLASSES_COTACAO = {
    "Hortaliças": 1,
    "Frutas": 2,
    "Especiarias": 3,
    "Cereais": 4,
    "SEM CLASSE": 99
}


def ordenar_produtos_para_cotacao(produtos):
    df = produtos.copy()

    if df.empty:
        return df

    df["classe"] = df["classe"].apply(corrigir_classe)
    df["ordem_classe"] = df["classe"].map(ORDEM_CLASSES_COTACAO).fillna(99)
    df = df.sort_values(["ordem_classe", "nome"])
    df = df.drop(columns=["ordem_classe"])

    return df


def preparar_ultimas_cotacoes(df_cotacoes):
    if df_cotacoes.empty or "data" not in df_cotacoes.columns:
        return pd.DataFrame()

    df = df_cotacoes.copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"])

    if df.empty:
        return pd.DataFrame()

    df["produto"] = df["produto"].astype(str).str.strip().str.upper()
    df = df.sort_values("data", ascending=False)
    df = df.drop_duplicates(subset="produto", keep="first")

    return df


def obter_sugestoes_cotacao(ultima_cotacao):
    sugestoes = normalizar_lista_precos(
        ultima_cotacao.get("precos_digitados", [])
    )

    if sugestoes:
        return sugestoes

    try:
        preco_min_antigo = float(ultima_cotacao["preco_min"])
        preco_max_antigo = float(ultima_cotacao["preco_max"])
    except Exception:
        return []

    sugestoes = []

    if preco_min_antigo > 0:
        sugestoes.append(preco_min_antigo)

    if preco_max_antigo > 0 and preco_max_antigo != preco_min_antigo:
        sugestoes.append(preco_max_antigo)

    return sugestoes


def calcular_precos_validos(precos, sugestoes):
    precos_validos = []

    for indice, preco in enumerate(precos):
        texto = str(preco).replace(",", ".").strip()

        if texto != "":
            try:
                valor = float(texto)

                if valor > 0:
                    precos_validos.append(valor)
            except Exception:
                pass

        elif indice < len(sugestoes) and sugestoes[indice]:
            try:
                valor = float(sugestoes[indice])

                if valor > 0:
                    precos_validos.append(valor)
            except Exception:
                pass

    return precos_validos


def normalizar_kg(kg, padrao=1):
    try:
        kg_numero = float(kg)
    except Exception:
        return padrao

    if kg_numero <= 0:
        return padrao

    return kg_numero


def calcular_resumo_precos(precos_validos, kg):
    if precos_validos:
        preco_min = min(precos_validos)
        preco_max = max(precos_validos)
        preco_medio = sum(precos_validos) / len(precos_validos)
    else:
        preco_min = 0
        preco_max = 0
        preco_medio = 0

    kg_base = normalizar_kg(kg, padrao=0)
    valor_kg = (preco_medio / kg_base) if kg_base > 0 else 0

    return preco_min, preco_max, preco_medio, valor_kg


def calcular_variacao_percentual(valor_atual, valor_anterior):
    try:
        valor_anterior = float(valor_anterior)
        valor_atual = float(valor_atual)
    except Exception:
        return 0

    if valor_anterior <= 0:
        return 0

    return ((valor_atual - valor_anterior) / valor_anterior) * 100


def montar_registro_cotacao(
    data_str,
    produto,
    classe,
    unidade,
    kg,
    lista_precos,
    normalizar_kg_salvo=False
):
    preco_min, preco_max, preco_medio, valor_kg = calcular_resumo_precos(
        lista_precos,
        kg
    )

    kg_base = normalizar_kg(kg)
    kg_salvo = int(round(kg_base)) if normalizar_kg_salvo else kg

    return {
        "data": data_str,
        "classe": corrigir_classe(classe),
        "produto": str(produto).strip().upper(),
        "unidade": unidade,
        "kg": kg_salvo,
        "preco_min": preco_min,
        "preco_max": preco_max,
        "preco_medio": preco_medio,
        "valor_kg": valor_kg,
        "precos_digitados": lista_precos
    }


def montar_registros_cotacoes(cotacoes, data_str):
    registros = []

    for cotacao in cotacoes:
        produto, classe, unidade, kg, _, _, lista_precos = cotacao

        registros.append(
            montar_registro_cotacao(
                data_str=data_str,
                produto=produto,
                classe=classe,
                unidade=unidade,
                kg=kg,
                lista_precos=lista_precos
            )
        )

    return registros
