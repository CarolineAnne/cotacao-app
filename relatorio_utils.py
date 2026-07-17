from xml.sax.saxutils import escape


ORDEM_CLASSES_RELATORIO = {
    "Hortaliças": 1,
    "Frutas": 2,
    "Especiarias": 3,
    "Cereais": 4,
    "SEM CLASSE": 99
}


def formatar_moeda(valor):
    try:
        return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "R$ 0,00"


def formatar_numero(valor, casas=0):
    try:
        return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0"


def formatar_percentual(valor):
    try:
        return f"{float(valor):.2f}%".replace(".", ",")
    except Exception:
        return "0,00%"


def texto_seguro(valor):
    if valor is None:
        return ""
    return escape(str(valor))


def classificar_alerta(valor):
    try:
        valor = float(valor)
    except Exception:
        return "Variação normal"

    if valor >= 60:
        return "Alta crítica"
    if valor >= 30:
        return "Alta acentuada"
    if valor >= 10:
        return "Alta moderada"
    if valor <= -30:
        return "Queda acentuada"
    if valor <= -10:
        return "Queda relevante"
    return "Variação normal"


def ordenar_classes(df, coluna_classe="classe", coluna_produto="produto"):
    df = df.copy()

    if coluna_classe in df.columns:
        df["_ordem_classe"] = df[coluna_classe].map(ORDEM_CLASSES_RELATORIO).fillna(99)
    else:
        df["_ordem_classe"] = 99

    colunas_ordem = ["_ordem_classe"]

    if coluna_produto in df.columns:
        colunas_ordem.append(coluna_produto)

    df = df.sort_values(colunas_ordem)
    df = df.drop(columns=["_ordem_classe"], errors="ignore")

    return df
