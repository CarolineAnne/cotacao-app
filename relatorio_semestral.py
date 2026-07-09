import os
import tempfile
from datetime import datetime
from xml.sax.saxutils import escape

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer,
    Image as RLImage
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from dados_utils import carregar_todas_cotacoes
from utils import corrigir_classe


# =========================================================
# PADRÃO VISUAL - MESMO ESTILO DO RELATÓRIO DIÁRIO/SEMANAL
# =========================================================
FONTE_TITULO = 18
FONTE_SUBTITULO = 14
FONTE_TEXTO = 10.5
FONTE_INFO = 9
FONTE_RODAPE = 8

FONTE_TABELA_PEQUENA = 9.2
FONTE_TABELA_MEDIA = 8.2
FONTE_TABELA_GRANDE = 7.2

AZUL_CABECALHO = "#1F4E79"
AZUL_GRAFICO = "#2F6F9F"
VERMELHO_GRAFICO = "#A33D3D"
CINZA_GRADE = "#DDDDDD"

ORDEM_CLASSES = {
    "Hortaliças": 1,
    "Frutas": 2,
    "Especiarias": 3,
    "Cereais": 4,
    "SEM CLASSE": 99
}


# =========================================================
# FORMATAÇÕES
# =========================================================
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


def limitar_texto(valor, limite=34):
    texto = str(valor or "").strip()

    if len(texto) <= limite:
        return texto

    return texto[:limite - 3] + "..."


def nome_semestre(semestre):
    if semestre == "1º semestre":
        return "1º semestre"

    return "2º semestre"


def periodo_semestre(ano, semestre):
    ano = int(ano)

    if semestre == "1º semestre":
        return pd.Timestamp(ano, 1, 1), pd.Timestamp(ano, 6, 30)

    return pd.Timestamp(ano, 7, 1), pd.Timestamp(ano, 12, 31)


def nome_mes_curto(mes):
    nomes = {
        1: "Jan",
        2: "Fev",
        3: "Mar",
        4: "Abr",
        5: "Mai",
        6: "Jun",
        7: "Jul",
        8: "Ago",
        9: "Set",
        10: "Out",
        11: "Nov",
        12: "Dez"
    }

    return nomes.get(int(mes), str(mes))


def trimestre_do_semestre(mes, semestre):
    mes = int(mes)

    if semestre == "1º semestre":
        return "1º trimestre" if mes <= 3 else "2º trimestre"

    return "3º trimestre" if mes <= 9 else "4º trimestre"


def ordenar_classes(df, coluna_classe="classe", coluna_produto="produto"):
    df = df.copy()

    if coluna_classe in df.columns:
        df["_ordem_classe"] = df[coluna_classe].map(ORDEM_CLASSES).fillna(99)
    else:
        df["_ordem_classe"] = 99

    colunas_ordem = ["_ordem_classe"]

    if coluna_produto in df.columns:
        colunas_ordem.append(coluna_produto)

    df = df.sort_values(colunas_ordem)
    df = df.drop(columns=["_ordem_classe"], errors="ignore")

    return df


# =========================================================
# PREPARAÇÃO DOS DADOS
# =========================================================
def preparar_base_cotacoes(df_todas):
    df = df_todas.copy()

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"])

    df["produto"] = df["produto"].astype(str).str.strip().str.upper()
    df["classe"] = df["classe"].astype(str).str.strip().apply(corrigir_classe)

    for col in ["kg", "preco_min", "preco_max", "preco_medio", "valor_kg"]:
        if col not in df.columns:
            df[col] = 0

        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    df = df[df["valor_kg"] > 0].copy()

    df["ano"] = df["data"].dt.year
    df["mes"] = df["data"].dt.month
    df["mes_nome"] = df["mes"].apply(nome_mes_curto)
    df["mes_ano"] = df["data"].dt.to_period("M").astype(str)

    return df


def calcular_metricas_produtos(df_periodo):
    if df_periodo.empty:
        return pd.DataFrame()

    df_ord = df_periodo.sort_values(["produto", "data"]).copy()

    primeira = (
        df_ord
        .groupby(["produto", "classe"], as_index=False)
        .first()
    )

    ultima = (
        df_ord
        .groupby(["produto", "classe"], as_index=False)
        .last()
    )

    resumo = (
        df_ord
        .groupby(["produto", "classe"], as_index=False)
        .agg(
            valor_kg_medio=("valor_kg", "mean"),
            valor_kg_min=("valor_kg", "min"),
            valor_kg_max=("valor_kg", "max"),
            preco_medio_semestre=("preco_medio", "mean"),
            desvio_padrao=("valor_kg", "std"),
            dias_cotados=("data", "nunique"),
            registros=("produto", "count")
        )
    )

    comparativo = primeira[
        [
            "produto",
            "classe",
            "data",
            "valor_kg",
            "preco_medio"
        ]
    ].merge(
        ultima[
            [
                "produto",
                "classe",
                "data",
                "valor_kg",
                "preco_medio"
            ]
        ],
        on=["produto", "classe"],
        suffixes=("_inicial", "_final")
    )

    comparativo["variacao_absoluta"] = (
        comparativo["valor_kg_final"] -
        comparativo["valor_kg_inicial"]
    )

    comparativo["variacao_percentual"] = comparativo.apply(
        lambda row: (
            ((row["valor_kg_final"] - row["valor_kg_inicial"]) / row["valor_kg_inicial"]) * 100
            if row["valor_kg_inicial"] > 0
            else 0
        ),
        axis=1
    )

    metricas = resumo.merge(
        comparativo[
            [
                "produto",
                "classe",
                "data_inicial",
                "data_final",
                "valor_kg_inicial",
                "valor_kg_final",
                "preco_medio_inicial",
                "preco_medio_final",
                "variacao_absoluta",
                "variacao_percentual"
            ]
        ],
        on=["produto", "classe"],
        how="left"
    )

    metricas["amplitude"] = (
        metricas["valor_kg_max"] -
        metricas["valor_kg_min"]
    )

    metricas["amplitude_percentual"] = metricas.apply(
        lambda row: (
            (row["amplitude"] / row["valor_kg_min"]) * 100
            if row["valor_kg_min"] > 0
            else 0
        ),
        axis=1
    )

    metricas["desvio_padrao"] = metricas["desvio_padrao"].fillna(0)

    metricas = ordenar_classes(metricas)

    return metricas


def calcular_mensal(df_periodo):
    if df_periodo.empty:
        return pd.DataFrame(), pd.DataFrame()

    mensal = (
        df_periodo
        .groupby(["ano", "mes", "mes_nome"], as_index=False)
        .agg(
            produtos=("produto", "nunique"),
            registros=("produto", "count"),
            preco_medio=("preco_medio", "mean"),
            valor_kg_medio=("valor_kg", "mean")
        )
        .sort_values(["ano", "mes"])
    )

    mensal_classe = (
        df_periodo
        .groupby(["ano", "mes", "mes_nome", "classe"], as_index=False)
        .agg(
            produtos=("produto", "nunique"),
            valor_kg_medio=("valor_kg", "mean")
        )
        .sort_values(["ano", "mes", "classe"])
    )

    return mensal, mensal_classe


def calcular_resumo_classes(df_periodo):
    if df_periodo.empty:
        return pd.DataFrame()

    resumo = (
        df_periodo
        .groupby("classe", as_index=False)
        .agg(
            produtos=("produto", "nunique"),
            registros=("produto", "count"),
            dias_cotados=("data", "nunique"),
            preco_medio=("preco_medio", "mean"),
            valor_kg_medio=("valor_kg", "mean"),
            valor_kg_min=("valor_kg", "min"),
            valor_kg_max=("valor_kg", "max")
        )
    )

    resumo = ordenar_classes(
        resumo,
        coluna_classe="classe",
        coluna_produto="classe"
    )

    return resumo


def calcular_comparacao_trimestres(df_periodo, semestre):
    if df_periodo.empty:
        return pd.DataFrame()

    df = df_periodo.copy()
    df["trimestre"] = df["mes"].apply(
        lambda mes: trimestre_do_semestre(mes, semestre)
    )

    tabela = (
        df
        .groupby(["produto", "classe", "trimestre"], as_index=False)
        .agg(valor_kg_medio=("valor_kg", "mean"))
    )

    pivot = tabela.pivot_table(
        index=["produto", "classe"],
        columns="trimestre",
        values="valor_kg_medio",
        aggfunc="mean"
    ).reset_index()

    colunas_trimestre = [
        c for c in pivot.columns
        if "trimestre" in str(c)
    ]

    if len(colunas_trimestre) < 2:
        return pd.DataFrame()

    col_1 = colunas_trimestre[0]
    col_2 = colunas_trimestre[1]

    pivot["variacao_percentual"] = pivot.apply(
        lambda row: (
            ((row[col_2] - row[col_1]) / row[col_1]) * 100
            if row[col_1] > 0
            else 0
        ),
        axis=1
    )

    pivot = pivot.rename(columns={
        col_1: "media_primeira_parte",
        col_2: "media_segunda_parte"
    })

    pivot["variacao_abs"] = pivot["variacao_percentual"].abs()

    pivot = pivot.sort_values(
        "variacao_abs",
        ascending=False
    ).drop(columns=["variacao_abs"])

    return pivot


def preparar_relatorio_semestral(df_todas, ano, semestre, classe_sel="Todas"):
    df = preparar_base_cotacoes(df_todas)

    data_inicio, data_fim = periodo_semestre(ano, semestre)

    df_periodo = df[
        (df["data"] >= data_inicio) &
        (df["data"] <= data_fim)
    ].copy()

    if classe_sel != "Todas":
        df_periodo = df_periodo[df_periodo["classe"] == classe_sel].copy()

    if df_periodo.empty:
        return None

    metricas = calcular_metricas_produtos(df_periodo)
    mensal, mensal_classe = calcular_mensal(df_periodo)
    resumo_classes = calcular_resumo_classes(df_periodo)
    comparacao_trimestres = calcular_comparacao_trimestres(df_periodo, semestre)

    ranking_altas = (
        metricas[metricas["variacao_percentual"] > 0]
        .sort_values("variacao_percentual", ascending=False)
        .head(10)
        .copy()
    )

    ranking_quedas = (
        metricas[metricas["variacao_percentual"] < 0]
        .sort_values("variacao_percentual", ascending=True)
        .head(10)
        .copy()
    )

    produtos_estaveis = (
        metricas[metricas["dias_cotados"] >= 2]
        .assign(abs_variacao=lambda d: d["variacao_percentual"].abs())
        .sort_values(["abs_variacao", "amplitude_percentual"], ascending=[True, True])
        .head(10)
        .copy()
    )

    produtos_instaveis = (
        metricas[metricas["dias_cotados"] >= 2]
        .sort_values("amplitude_percentual", ascending=False)
        .head(10)
        .copy()
    )

    mais_caros = (
        metricas
        .sort_values("valor_kg_medio", ascending=False)
        .head(10)
        .copy()
    )

    mais_baratos = (
        metricas
        .sort_values("valor_kg_medio", ascending=True)
        .head(10)
        .copy()
    )

    maior_alta = ranking_altas.iloc[0] if not ranking_altas.empty else pd.Series({
        "produto": "Nenhum produto",
        "variacao_percentual": 0,
        "valor_kg_inicial": 0,
        "valor_kg_final": 0
    })

    maior_queda = ranking_quedas.iloc[0] if not ranking_quedas.empty else pd.Series({
        "produto": "Nenhum produto",
        "variacao_percentual": 0,
        "valor_kg_inicial": 0,
        "valor_kg_final": 0
    })

    maior_preco_kg = metricas.sort_values(
        "valor_kg_medio",
        ascending=False
    ).iloc[0]

    menor_preco_kg = metricas.sort_values(
        "valor_kg_medio",
        ascending=True
    ).iloc[0]

    mais_instavel = produtos_instaveis.iloc[0] if not produtos_instaveis.empty else pd.Series({
        "produto": "Nenhum produto",
        "amplitude_percentual": 0,
        "valor_kg_medio": 0
    })

    mais_estavel = produtos_estaveis.iloc[0] if not produtos_estaveis.empty else pd.Series({
        "produto": "Nenhum produto",
        "amplitude_percentual": 0,
        "valor_kg_medio": 0
    })

    indicadores = {
        "ano": int(ano),
        "semestre": nome_semestre(semestre),
        "classe": classe_sel,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "dias_cotacao": int(df_periodo["data"].nunique()),
        "produtos_cotados": int(df_periodo["produto"].nunique()),
        "registros": int(len(df_periodo)),
        "classes_analisadas": int(df_periodo["classe"].nunique()),
        "preco_medio_geral": float(df_periodo["preco_medio"].mean()),
        "valor_kg_medio": float(df_periodo["valor_kg"].mean()),
        "menor_valor_kg": float(df_periodo["valor_kg"].min()),
        "maior_valor_kg": float(df_periodo["valor_kg"].max())
    }

    return {
        "df_periodo": df_periodo,
        "metricas": metricas,
        "mensal": mensal,
        "mensal_classe": mensal_classe,
        "resumo_classes": resumo_classes,
        "comparacao_trimestres": comparacao_trimestres,
        "ranking_altas": ranking_altas,
        "ranking_quedas": ranking_quedas,
        "produtos_estaveis": produtos_estaveis,
        "produtos_instaveis": produtos_instaveis,
        "mais_caros": mais_caros,
        "mais_baratos": mais_baratos,
        "maior_alta": maior_alta,
        "maior_queda": maior_queda,
        "maior_preco_kg": maior_preco_kg,
        "menor_preco_kg": menor_preco_kg,
        "mais_instavel": mais_instavel,
        "mais_estavel": mais_estavel,
        "indicadores": indicadores
    }


# =========================================================
# PDF - ESTILOS E TABELAS
# =========================================================
def criar_estilos_pdf():
    styles = getSampleStyleSheet()

    estilo_titulo = styles["Title"].clone("titulo_relatorio_semestral")
    estilo_titulo.alignment = TA_CENTER
    estilo_titulo.fontSize = FONTE_TITULO
    estilo_titulo.leading = FONTE_TITULO + 3
    estilo_titulo.spaceAfter = 10

    estilo_subtitulo = styles["Heading2"].clone("subtitulo_relatorio_semestral")
    estilo_subtitulo.fontSize = FONTE_SUBTITULO
    estilo_subtitulo.leading = FONTE_SUBTITULO + 3
    estilo_subtitulo.spaceBefore = 10
    estilo_subtitulo.spaceAfter = 6

    estilo_normal = styles["Normal"].clone("normal_relatorio_semestral")
    estilo_normal.fontSize = FONTE_TEXTO
    estilo_normal.leading = FONTE_TEXTO + 3
    estilo_normal.alignment = TA_LEFT

    estilo_info = ParagraphStyle(
        "info_relatorio_semestral",
        parent=styles["Normal"],
        fontSize=FONTE_INFO,
        leading=FONTE_INFO + 2,
        textColor=colors.grey
    )

    estilo_observacao = ParagraphStyle(
        "observacao_relatorio_semestral",
        parent=styles["Normal"],
        fontSize=FONTE_INFO,
        leading=FONTE_INFO + 2,
        textColor=colors.HexColor("#444444"),
        backColor=colors.HexColor("#F2F6FA"),
        borderColor=colors.HexColor("#D7E2EC"),
        borderWidth=0.5,
        borderPadding=6,
        spaceBefore=4,
        spaceAfter=8
    )

    return estilo_titulo, estilo_subtitulo, estilo_normal, estilo_info, estilo_observacao


def adicionar_numero_pagina(canvas, doc):
    canvas.saveState()

    largura, altura = A4
    numero_pagina = canvas.getPageNumber()

    canvas.setFont("Helvetica", FONTE_RODAPE)
    canvas.setFillColor(colors.grey)

    canvas.drawString(
        25,
        15,
        "AMA | Sistema de Cotação"
    )

    canvas.drawRightString(
        largura - 25,
        15,
        f"Página {numero_pagina}"
    )

    canvas.restoreState()


def criar_tabela_pdf(
    dados,
    larguras=None,
    fonte=8,
    repetir_cabecalho=True,
    colunas_texto=None
):
    if colunas_texto is None:
        colunas_texto = []

    estilo_cabecalho = ParagraphStyle(
        "cabecalho_tabela",
        fontName="Helvetica-Bold",
        fontSize=fonte,
        leading=fonte + 2,
        textColor=colors.white,
        alignment=TA_CENTER
    )

    estilo_celula = ParagraphStyle(
        "celula_tabela",
        fontName="Helvetica",
        fontSize=fonte,
        leading=fonte + 2,
        textColor=colors.black,
        alignment=TA_CENTER
    )

    estilo_celula_texto = ParagraphStyle(
        "celula_tabela_texto",
        fontName="Helvetica",
        fontSize=fonte,
        leading=fonte + 2,
        textColor=colors.black,
        alignment=TA_LEFT
    )

    dados_formatados = []

    for i, linha in enumerate(dados):
        nova_linha = []

        for j, valor in enumerate(linha):
            if i == 0:
                nova_linha.append(
                    Paragraph(texto_seguro(valor), estilo_cabecalho)
                )
            else:
                if j in colunas_texto:
                    nova_linha.append(
                        Paragraph(texto_seguro(valor), estilo_celula_texto)
                    )
                else:
                    nova_linha.append(
                        Paragraph(texto_seguro(valor), estilo_celula)
                    )

        dados_formatados.append(nova_linha)

    tabela = Table(
        dados_formatados,
        colWidths=larguras,
        repeatRows=1 if repetir_cabecalho else 0
    )

    estilo = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(AZUL_CABECALHO)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), fonte),
        ("FONTSIZE", (0, 1), (-1, -1), fonte),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("ALIGN", (0, 1), (-1, -1), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
            colors.whitesmoke,
            colors.HexColor("#E8E8E8")
        ]),
        ("LEFTPADDING", (0, 0), (-1, -1), 2),
        ("RIGHTPADDING", (0, 0), (-1, -1), 2),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])

    for coluna in colunas_texto:
        estilo.add("ALIGN", (coluna, 1), (coluna, -1), "LEFT")

    tabela.setStyle(estilo)

    return tabela


# =========================================================
# TABELAS DO RELATÓRIO
# =========================================================
def tabela_resumo_executivo(dados):
    ind = dados["indicadores"]

    return [
        ["Indicador", "Resultado"],
        ["Período analisado", f"{ind['data_inicio'].strftime('%d/%m/%Y')} a {ind['data_fim'].strftime('%d/%m/%Y')}"],
        ["Classe filtrada", str(ind["classe"])],
        ["Dias com cotação", str(ind["dias_cotacao"])],
        ["Produtos cotados", str(ind["produtos_cotados"])],
        ["Registros analisados", str(ind["registros"])],
        ["Preço médio geral", formatar_moeda(ind["preco_medio_geral"])],
        ["Valor/kg médio", formatar_moeda(ind["valor_kg_medio"])]
    ]


def tabela_destaques(dados):
    maior_alta = dados["maior_alta"]
    maior_queda = dados["maior_queda"]
    maior_preco_kg = dados["maior_preco_kg"]
    menor_preco_kg = dados["menor_preco_kg"]
    mais_instavel = dados["mais_instavel"]
    mais_estavel = dados["mais_estavel"]

    return [
        ["Destaque", "Produto", "Resultado"],
        [
            "Maior alta no valor/kg",
            str(maior_alta.get("produto", "")),
            formatar_percentual(maior_alta.get("variacao_percentual", 0))
        ],
        [
            "Maior queda no valor/kg",
            str(maior_queda.get("produto", "")),
            formatar_percentual(maior_queda.get("variacao_percentual", 0))
        ],
        [
            "Maior média de valor/kg",
            str(maior_preco_kg.get("produto", "")),
            formatar_moeda(maior_preco_kg.get("valor_kg_medio", 0))
        ],
        [
            "Menor média de valor/kg",
            str(menor_preco_kg.get("produto", "")),
            formatar_moeda(menor_preco_kg.get("valor_kg_medio", 0))
        ],
        [
            "Produto mais instável",
            str(mais_instavel.get("produto", "")),
            formatar_percentual(mais_instavel.get("amplitude_percentual", 0))
        ],
        [
            "Produto mais estável",
            str(mais_estavel.get("produto", "")),
            formatar_percentual(mais_estavel.get("amplitude_percentual", 0))
        ]
    ]


def tabela_mensal(df):
    dados = [
        ["Mês", "Produtos", "Registros", "Preço médio", "Valor/kg médio"]
    ]

    if df is None or df.empty:
        return dados

    for _, row in df.iterrows():
        dados.append([
            str(row.get("mes_nome", "")),
            str(int(row.get("produtos", 0))),
            str(int(row.get("registros", 0))),
            formatar_moeda(row.get("preco_medio", 0)),
            formatar_moeda(row.get("valor_kg_medio", 0))
        ])

    return dados


def tabela_resumo_classes(df):
    dados = [
        ["Classe", "Produtos", "Registros", "Dias", "Preço médio", "Valor/kg médio"]
    ]

    if df is None or df.empty:
        return dados

    for _, row in df.iterrows():
        dados.append([
            str(row.get("classe", "")),
            str(int(row.get("produtos", 0))),
            str(int(row.get("registros", 0))),
            str(int(row.get("dias_cotados", 0))),
            formatar_moeda(row.get("preco_medio", 0)),
            formatar_moeda(row.get("valor_kg_medio", 0))
        ])

    return dados


def tabela_ranking_variacao(df):
    dados = [
        ["Produto", "Classe", "Inicial/kg", "Final/kg", "Variação", "Dias"]
    ]

    if df is None or df.empty:
        return dados

    for _, row in df.iterrows():
        dados.append([
            limitar_texto(row.get("produto", ""), 32),
            str(row.get("classe", "")),
            formatar_moeda(row.get("valor_kg_inicial", 0)),
            formatar_moeda(row.get("valor_kg_final", 0)),
            formatar_percentual(row.get("variacao_percentual", 0)),
            str(int(row.get("dias_cotados", 0)))
        ])

    return dados


def tabela_estabilidade(df):
    dados = [
        ["Produto", "Classe", "Média/kg", "Menor/kg", "Maior/kg", "Amplitude", "Dias"]
    ]

    if df is None or df.empty:
        return dados

    for _, row in df.iterrows():
        dados.append([
            limitar_texto(row.get("produto", ""), 28),
            str(row.get("classe", "")),
            formatar_moeda(row.get("valor_kg_medio", 0)),
            formatar_moeda(row.get("valor_kg_min", 0)),
            formatar_moeda(row.get("valor_kg_max", 0)),
            formatar_percentual(row.get("amplitude_percentual", 0)),
            str(int(row.get("dias_cotados", 0)))
        ])

    return dados


def tabela_preco_medio(df):
    dados = [
        ["Produto", "Classe", "Média/kg", "Menor/kg", "Maior/kg", "Dias"]
    ]

    if df is None or df.empty:
        return dados

    for _, row in df.iterrows():
        dados.append([
            limitar_texto(row.get("produto", ""), 32),
            str(row.get("classe", "")),
            formatar_moeda(row.get("valor_kg_medio", 0)),
            formatar_moeda(row.get("valor_kg_min", 0)),
            formatar_moeda(row.get("valor_kg_max", 0)),
            str(int(row.get("dias_cotados", 0)))
        ])

    return dados


def tabela_trimestres(df):
    dados = [
        ["Produto", "Classe", "Média 1ª parte", "Média 2ª parte", "Variação"]
    ]

    if df is None or df.empty:
        return dados

    for _, row in df.head(12).iterrows():
        dados.append([
            limitar_texto(row.get("produto", ""), 32),
            str(row.get("classe", "")),
            formatar_moeda(row.get("media_primeira_parte", 0)),
            formatar_moeda(row.get("media_segunda_parte", 0)),
            formatar_percentual(row.get("variacao_percentual", 0))
        ])

    return dados


def tabela_produtos_geral(df):
    dados = [
        ["Produto", "Classe", "Média/kg", "Inicial/kg", "Final/kg", "Variação", "Dias"]
    ]

    if df is None or df.empty:
        return dados

    for _, row in df.iterrows():
        dados.append([
            limitar_texto(row.get("produto", ""), 28),
            str(row.get("classe", "")),
            formatar_moeda(row.get("valor_kg_medio", 0)),
            formatar_moeda(row.get("valor_kg_inicial", 0)),
            formatar_moeda(row.get("valor_kg_final", 0)),
            formatar_percentual(row.get("variacao_percentual", 0)),
            str(int(row.get("dias_cotados", 0)))
        ])

    return dados


# =========================================================
# GRÁFICOS
# =========================================================
def criar_grafico_linha_mensal(mensal, mensal_classe):
    if mensal is None or mensal.empty:
        return None

    fig, ax = plt.subplots(figsize=(7.0, 3.35))

    meses = mensal["mes_nome"].tolist()

    ax.plot(
        meses,
        mensal["valor_kg_medio"],
        marker="o",
        linewidth=2.2,
        color=AZUL_GRAFICO,
        label="Média geral"
    )

    marcadores = ["s", "^", "D", "v", "P", "X"]
    estilos = ["--", ":", "-.", "--", ":"]

    if mensal_classe is not None and not mensal_classe.empty:
        classes = mensal_classe["classe"].dropna().unique().tolist()

        for i, classe in enumerate(classes):
            df_c = mensal_classe[mensal_classe["classe"] == classe].copy()

            ax.plot(
                df_c["mes_nome"],
                df_c["valor_kg_medio"],
                marker=marcadores[i % len(marcadores)],
                linestyle=estilos[i % len(estilos)],
                linewidth=1.7,
                label=classe
            )

    ax.set_title("Evolução mensal do valor/kg médio", fontsize=12, fontweight="bold")
    ax.set_ylabel("Valor/kg médio (R$)")
    ax.grid(True, linestyle=":", alpha=0.45)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.legend(fontsize=7, loc="best")

    caminho = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name

    fig.tight_layout()
    fig.savefig(caminho, dpi=180, bbox_inches="tight")
    plt.close(fig)

    return caminho


def criar_grafico_barras_variacao(df, titulo, tipo="alta"):
    if df is None or df.empty:
        return None

    df_plot = df.head(10).copy()

    if tipo == "queda":
        df_plot = df_plot.sort_values("variacao_percentual", ascending=True)
        cor = VERMELHO_GRAFICO
    else:
        df_plot = df_plot.sort_values("variacao_percentual", ascending=True)
        cor = AZUL_GRAFICO

    produtos = [
        limitar_texto(p, 26)
        for p in df_plot["produto"].astype(str).tolist()
    ]

    valores = pd.to_numeric(
        df_plot["variacao_percentual"],
        errors="coerce"
    ).fillna(0).tolist()

    fig, ax = plt.subplots(figsize=(7.0, 3.45))

    barras = ax.barh(
        produtos,
        valores,
        color=cor,
        height=0.58
    )

    max_abs = max([abs(v) for v in valores] + [1])

    for barra, valor in zip(barras, valores):
        largura = barra.get_width()
        y = barra.get_y() + barra.get_height() / 2

        # Percentual dentro da barra quando houver espaço.
        if abs(valor) >= max_abs * 0.12:
            x_texto = largura * 0.96
            ha = "right" if valor >= 0 else "left"
            cor_texto = "white"
        else:
            x_texto = largura + (max_abs * 0.03 if valor >= 0 else -max_abs * 0.03)
            ha = "left" if valor >= 0 else "right"
            cor_texto = "black"

        ax.text(
            x_texto,
            y,
            formatar_percentual(valor),
            ha=ha,
            va="center",
            fontsize=7.5,
            color=cor_texto,
            fontweight="bold"
        )

    ax.axvline(0, color="#555555", linewidth=0.8)
    ax.set_title(titulo, fontsize=12, fontweight="bold")
    ax.set_xlabel("Variação (%)")
    ax.grid(axis="x", linestyle=":", alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(axis="y", labelsize=7.5)
    ax.tick_params(axis="x", labelsize=8)

    caminho = tempfile.NamedTemporaryFile(delete=False, suffix=".png").name

    fig.tight_layout()
    fig.savefig(caminho, dpi=180, bbox_inches="tight")
    plt.close(fig)

    return caminho


def inserir_imagem_grafico(elementos, caminho, largura=510, altura=260):
    if caminho and os.path.exists(caminho):
        img = RLImage(caminho, width=largura, height=altura)
        elementos.append(img)
        elementos.append(Spacer(1, 8))


# =========================================================
# PDF - RELATÓRIO SEMESTRAL
# =========================================================
def gerar_pdf_relatorio_semestral(dados, nome_pdf, classe_sel):
    doc = SimpleDocTemplate(
        nome_pdf,
        pagesize=A4,
        leftMargin=22,
        rightMargin=22,
        topMargin=25,
        bottomMargin=28
    )

    elementos = []
    graficos_temp = []

    estilo_titulo, estilo_subtitulo, estilo_normal, estilo_info, estilo_observacao = criar_estilos_pdf()

    ind = dados["indicadores"]

    data_inicio_txt = ind["data_inicio"].strftime("%d/%m/%Y")
    data_fim_txt = ind["data_fim"].strftime("%d/%m/%Y")

    titulo = f"Relatório Semestral de Cotação - {ind['semestre']} de {ind['ano']}"

    elementos.append(Paragraph(titulo, estilo_titulo))
    elementos.append(Paragraph("AMA - Autarquia Municipal de Abastecimento", estilo_info))
    elementos.append(Paragraph("Mercado do Produtor de Juazeiro-BA", estilo_info))
    elementos.append(Paragraph(f"Período analisado: {data_inicio_txt} a {data_fim_txt}", estilo_info))
    elementos.append(Paragraph(f"Classe filtrada: {classe_sel}", estilo_info))
    elementos.append(Spacer(1, 10))

    # ================= 1. RESUMO EXECUTIVO =================
    elementos.append(Paragraph("1. Resumo executivo", estilo_subtitulo))

    texto_resumo = (
        f"No {ind['semestre']} de {ind['ano']}, foram analisados "
        f"{ind['produtos_cotados']} produtos, em {ind['dias_cotacao']} dias de cotação, "
        f"totalizando {formatar_numero(ind['registros'])} registros válidos. "
        f"O valor/kg médio do período foi de {formatar_moeda(ind['valor_kg_medio'])}."
    )

    elementos.append(Paragraph(texto_seguro(texto_resumo), estilo_normal))
    elementos.append(Spacer(1, 6))

    elementos.append(
        criar_tabela_pdf(
            tabela_resumo_executivo(dados),
            larguras=[190, 340],
            fonte=FONTE_TABELA_PEQUENA,
            colunas_texto=[0, 1]
        )
    )

    elementos.append(Spacer(1, 10))

    # ================= 2. DESTAQUES =================
    elementos.append(Paragraph("2. Destaques do semestre", estilo_subtitulo))

    texto_destaques = (
        "Os destaques abaixo reúnem os principais produtos observados no período, "
        "considerando alta, queda, valor/kg médio, estabilidade e instabilidade."
    )

    elementos.append(Paragraph(texto_seguro(texto_destaques), estilo_normal))
    elementos.append(Spacer(1, 6))

    elementos.append(
        criar_tabela_pdf(
            tabela_destaques(dados),
            larguras=[145, 265, 120],
            fonte=FONTE_TABELA_PEQUENA,
            colunas_texto=[0, 1]
        )
    )

    elementos.append(Spacer(1, 8))

    # ================= 3. LEITURA TÉCNICA =================
    elementos.append(Paragraph("3. Leitura técnica dos resultados", estilo_subtitulo))

    maior_alta = dados["maior_alta"]
    maior_queda = dados["maior_queda"]
    mais_instavel = dados["mais_instavel"]

    texto_tecnico = (
        f"A maior alta registrada foi observada em {maior_alta.get('produto', '')}, "
        f"com variação de {formatar_percentual(maior_alta.get('variacao_percentual', 0))}. "
        f"A maior queda foi observada em {maior_queda.get('produto', '')}, "
        f"com variação de {formatar_percentual(maior_queda.get('variacao_percentual', 0))}. "
        f"Já o produto com maior amplitude de oscilação foi {mais_instavel.get('produto', '')}, "
        f"com amplitude de {formatar_percentual(mais_instavel.get('amplitude_percentual', 0))}."
    )

    elementos.append(Paragraph(texto_seguro(texto_tecnico), estilo_normal))

    elementos.append(
        Paragraph(
            texto_seguro(
                "Observação: as variações podem ser influenciadas por sazonalidade, oferta regional, "
                "origem da mercadoria, custos logísticos, qualidade do produto, datas comemorativas e "
                "mudanças na procura."
            ),
            estilo_observacao
        )
    )

    elementos.append(Spacer(1, 12))

    # ================= 4. RESUMO MENSAL =================
    elementos.append(Paragraph("4. Resumo mensal", estilo_subtitulo))

    texto_mensal = (
        "A tabela mensal apresenta a média de preços por mês, permitindo visualizar "
        "em quais períodos o valor/kg médio ficou mais elevado ou mais reduzido."
    )

    elementos.append(Paragraph(texto_seguro(texto_mensal), estilo_normal))
    elementos.append(Spacer(1, 6))

    elementos.append(
        criar_tabela_pdf(
            tabela_mensal(dados["mensal"]),
            larguras=[70, 100, 100, 130, 130],
            fonte=FONTE_TABELA_PEQUENA,
            colunas_texto=[0]
        )
    )

    elementos.append(Spacer(1, 10))

    caminho_linha = criar_grafico_linha_mensal(
        dados["mensal"],
        dados["mensal_classe"]
    )
    graficos_temp.append(caminho_linha)

    inserir_imagem_grafico(
        elementos,
        caminho_linha,
        largura=465,
        altura=230
    )

    # ================= 5. RESUMO POR CLASSE =================
    elementos.append(Paragraph("5. Resumo por classe", estilo_subtitulo))

    texto_classe = (
        "O resumo por classe consolida a quantidade de produtos, registros e médias "
        "de preço em cada grupo de comercialização."
    )

    elementos.append(Paragraph(texto_seguro(texto_classe), estilo_normal))
    elementos.append(Spacer(1, 6))

    elementos.append(
        criar_tabela_pdf(
            tabela_resumo_classes(dados["resumo_classes"]),
            larguras=[100, 70, 85, 65, 105, 105],
            fonte=FONTE_TABELA_MEDIA,
            colunas_texto=[0]
        )
    )

    elementos.append(Spacer(1, 12))

    # ================= 6. MAIORES ALTAS =================
    elementos.append(Paragraph("6. Maiores altas do semestre", estilo_subtitulo))

    texto_altas = (
        "O ranking de altas considera a comparação entre o primeiro e o último registro "
        "válido de cada produto dentro do semestre."
    )

    elementos.append(Paragraph(texto_seguro(texto_altas), estilo_normal))
    elementos.append(Spacer(1, 6))

    caminho_altas = criar_grafico_barras_variacao(
        dados["ranking_altas"],
        "Top 10 maiores altas",
        tipo="alta"
    )
    graficos_temp.append(caminho_altas)

    inserir_imagem_grafico(
        elementos,
        caminho_altas,
        largura=465,
        altura=225
    )

    elementos.append(
        criar_tabela_pdf(
            tabela_ranking_variacao(dados["ranking_altas"]),
            larguras=[170, 85, 80, 80, 70, 45],
            fonte=FONTE_TABELA_MEDIA,
            colunas_texto=[0, 1]
        )
    )

    elementos.append(Spacer(1, 12))

    # ================= 7. MAIORES QUEDAS =================
    elementos.append(Paragraph("7. Maiores quedas do semestre", estilo_subtitulo))

    texto_quedas = (
        "O ranking de quedas evidencia os produtos que apresentaram maior redução "
        "do valor/kg no período analisado."
    )

    elementos.append(Paragraph(texto_seguro(texto_quedas), estilo_normal))
    elementos.append(Spacer(1, 6))

    caminho_quedas = criar_grafico_barras_variacao(
        dados["ranking_quedas"],
        "Top 10 maiores quedas",
        tipo="queda"
    )
    graficos_temp.append(caminho_quedas)

    inserir_imagem_grafico(
        elementos,
        caminho_quedas,
        largura=465,
        altura=225
    )

    elementos.append(
        criar_tabela_pdf(
            tabela_ranking_variacao(dados["ranking_quedas"]),
            larguras=[170, 85, 80, 80, 70, 45],
            fonte=FONTE_TABELA_MEDIA,
            colunas_texto=[0, 1]
        )
    )

    elementos.append(Spacer(1, 12))

    # ================= 8. ESTABILIDADE E INSTABILIDADE =================
    elementos.append(Paragraph("8. Produtos mais estáveis", estilo_subtitulo))

    elementos.append(
        Paragraph(
            texto_seguro(
                "Produtos mais estáveis são aqueles com menor oscilação relativa "
                "entre os valores registrados no semestre."
            ),
            estilo_normal
        )
    )
    elementos.append(Spacer(1, 6))

    elementos.append(
        criar_tabela_pdf(
            tabela_estabilidade(dados["produtos_estaveis"]),
            larguras=[145, 80, 70, 70, 70, 70, 45],
            fonte=FONTE_TABELA_MEDIA,
            colunas_texto=[0, 1]
        )
    )

    elementos.append(Spacer(1, 12))

    elementos.append(Paragraph("9. Produtos mais instáveis", estilo_subtitulo))

    elementos.append(
        Paragraph(
            texto_seguro(
                "Produtos mais instáveis são aqueles com maior amplitude percentual "
                "entre o menor e o maior valor/kg observado."
            ),
            estilo_normal
        )
    )
    elementos.append(Spacer(1, 6))

    elementos.append(
        criar_tabela_pdf(
            tabela_estabilidade(dados["produtos_instaveis"]),
            larguras=[145, 80, 70, 70, 70, 70, 45],
            fonte=FONTE_TABELA_MEDIA,
            colunas_texto=[0, 1]
        )
    )

    elementos.append(Spacer(1, 12))

    # ================= 10. MAIS CAROS E BARATOS =================
    elementos.append(Paragraph("10. Produtos com maior valor/kg médio", estilo_subtitulo))

    elementos.append(
        criar_tabela_pdf(
            tabela_preco_medio(dados["mais_caros"]),
            larguras=[170, 90, 90, 90, 90, 45],
            fonte=FONTE_TABELA_MEDIA,
            colunas_texto=[0, 1]
        )
    )

    elementos.append(Spacer(1, 12))

    elementos.append(Paragraph("11. Produtos com menor valor/kg médio", estilo_subtitulo))

    elementos.append(
        criar_tabela_pdf(
            tabela_preco_medio(dados["mais_baratos"]),
            larguras=[170, 90, 90, 90, 90, 45],
            fonte=FONTE_TABELA_MEDIA,
            colunas_texto=[0, 1]
        )
    )

    elementos.append(Spacer(1, 12))

    # ================= 12. COMPARAÇÃO TRIMESTRAL =================
    elementos.append(Paragraph("12. Comparação entre trimestres", estilo_subtitulo))

    elementos.append(
        Paragraph(
            texto_seguro(
                "A comparação entre as duas partes do semestre ajuda a identificar "
                "produtos que ficaram mais caros ou mais baratos ao longo do período."
            ),
            estilo_normal
        )
    )
    elementos.append(Spacer(1, 6))

    elementos.append(
        criar_tabela_pdf(
            tabela_trimestres(dados["comparacao_trimestres"]),
            larguras=[170, 90, 100, 100, 70],
            fonte=FONTE_TABELA_MEDIA,
            colunas_texto=[0, 1]
        )
    )

    elementos.append(Spacer(1, 10))

    # ================= 13. CONSIDERAÇÕES FINAIS =================
    elementos.append(Paragraph("13. Considerações finais", estilo_subtitulo))

    textos_finais = [
        (
            "O relatório semestral permite observar tendências que não aparecem de forma "
            "isolada na cotação diária, tornando possível acompanhar produtos com maior "
            "alta, maior queda, estabilidade e instabilidade."
        ),
        (
            "Os resultados apresentados devem ser utilizados como apoio à gestão, à comunicação "
            "institucional e ao acompanhamento do Mercado do Produtor de Juazeiro-BA."
        ),
        (
            "Produtos com grande variação devem ser avaliados com atenção, pois podem indicar "
            "alterações na oferta, na procura, no período de safra ou em condições externas "
            "que afetam a comercialização."
        )
    ]

    for texto in textos_finais:
        elementos.append(Paragraph(texto_seguro(texto), estilo_normal))
        elementos.append(Spacer(1, 5))

    elementos.append(Spacer(1, 12))

    # ================= 14. ANEXO =================
    elementos.append(Paragraph("14. Anexo - resumo por produto", estilo_subtitulo))

    elementos.append(
        Paragraph(
            texto_seguro(
                "A tabela abaixo apresenta um resumo geral por produto. "
                "Foram listados os produtos com maior número de registros no período."
            ),
            estilo_normal
        )
    )
    elementos.append(Spacer(1, 6))

    metricas_anexo = (
        dados["metricas"]
        .sort_values(["dias_cotados", "produto"], ascending=[False, True])
        .head(45)
        .copy()
    )

    elementos.append(
        criar_tabela_pdf(
            tabela_produtos_geral(metricas_anexo),
            larguras=[135, 75, 70, 70, 70, 70, 40],
            fonte=FONTE_TABELA_GRANDE,
            colunas_texto=[0, 1]
        )
    )

    doc.build(
        elementos,
        onFirstPage=adicionar_numero_pagina,
        onLaterPages=adicionar_numero_pagina
    )

    # Limpa arquivos temporários dos gráficos.
    for caminho in graficos_temp:
        try:
            if caminho and os.path.exists(caminho):
                os.remove(caminho)
        except Exception:
            pass

    return nome_pdf


# =========================================================
# TELA STREAMLIT
# =========================================================
def tela_relatorio_semestral(supabase):
    st.title("📘 Relatório Semestral")

    st.info(
        "Gere um relatório semestral em PDF no mesmo padrão visual dos relatórios diário e semanal."
    )

    try:
        df_todas = carregar_todas_cotacoes(supabase)
    except Exception as e:
        st.error(f"Erro ao carregar cotações: {e}")
        return

    if df_todas.empty:
        st.warning("Ainda não há cotações cadastradas.")
        return

    df_base = preparar_base_cotacoes(df_todas)

    if df_base.empty:
        st.warning("Não há cotações válidas com valor/kg maior que zero.")
        return

    anos = sorted(
        df_base["ano"].dropna().astype(int).unique().tolist(),
        reverse=True
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        ano = st.selectbox(
            "Ano",
            anos,
            key="relatorio_semestral_ano"
        )

    with col2:
        semestre = st.selectbox(
            "Semestre",
            ["1º semestre", "2º semestre"],
            key="relatorio_semestral_semestre"
        )

    with col3:
        classes = ["Todas"] + sorted(
            df_base["classe"].dropna().unique().tolist()
        )

        classe_sel = st.selectbox(
            "Classe",
            classes,
            key="relatorio_semestral_classe"
        )

    dados = preparar_relatorio_semestral(
        df_todas,
        ano,
        semestre,
        classe_sel
    )

    if dados is None:
        st.warning("Não foram encontradas cotações para o período selecionado.")
        return

    ind = dados["indicadores"]

    st.subheader("Prévia do período")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Dias com cotação", ind["dias_cotacao"])
    c2.metric("Produtos cotados", ind["produtos_cotados"])
    c3.metric("Registros", formatar_numero(ind["registros"]))
    c4.metric("Valor/kg médio", formatar_moeda(ind["valor_kg_medio"]))

    st.divider()

    col_altas, col_quedas = st.columns(2)

    with col_altas:
        st.subheader("Maiores altas")

        st.dataframe(
            pd.DataFrame(tabela_ranking_variacao(dados["ranking_altas"])[1:],
                         columns=tabela_ranking_variacao(dados["ranking_altas"])[0]),
            use_container_width=True,
            hide_index=True
        )

    with col_quedas:
        st.subheader("Maiores quedas")

        st.dataframe(
            pd.DataFrame(tabela_ranking_variacao(dados["ranking_quedas"])[1:],
                         columns=tabela_ranking_variacao(dados["ranking_quedas"])[0]),
            use_container_width=True,
            hide_index=True
        )

    st.divider()

    if st.button(
        "📄 Gerar Relatório Semestral em PDF",
        type="primary",
        key="btn_gerar_relatorio_semestral_pdf"
    ):
        try:
            nome_pdf = (
                f"relatorio_semestral_"
                f"{ind['ano']}_"
                f"{ind['semestre'].replace('º ', '').replace(' ', '_')}_"
                f"{classe_sel.replace(' ', '_')}.pdf"
            )

            caminho_pdf = gerar_pdf_relatorio_semestral(
                dados,
                nome_pdf,
                classe_sel
            )

            st.success("Relatório semestral gerado com sucesso.")

            with open(caminho_pdf, "rb") as f:
                st.download_button(
                    "📥 Baixar Relatório Semestral",
                    data=f,
                    file_name=nome_pdf,
                    mime="application/pdf"
                )

        except Exception as e:
            st.error(f"Erro ao gerar relatório semestral: {e}")
