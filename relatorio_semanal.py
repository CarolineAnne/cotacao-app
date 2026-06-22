from datetime import datetime, timedelta
from io import BytesIO
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
    Image
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from dados_utils import carregar_todas_cotacoes
from observacoes_produtos import carregar_observacoes_periodo
from utils import corrigir_classe


# =========================================================
# CONFIGURAÇÃO DAS FONTES
# =========================================================
FONTE_TITULO = 18
FONTE_SUBTITULO = 14
FONTE_TEXTO = 10.5
FONTE_INFO = 9
FONTE_RODAPE = 8

FONTE_TABELA_PEQUENA = 9.2
FONTE_TABELA_MEDIA = 8.0
FONTE_TABELA_GRANDE = 6.8


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


def classificar_alerta(valor):
    try:
        valor = float(valor)
    except Exception:
        return "Variação normal"

    if valor >= 60:
        return "Alta crítica"
    elif valor >= 30:
        return "Alta acentuada"
    elif valor >= 10:
        return "Alta moderada"
    elif valor <= -30:
        return "Queda acentuada"
    elif valor <= -10:
        return "Queda relevante"
    return "Variação normal"


def ordenar_classes(df, coluna_classe="classe", coluna_produto="produto"):
    ordem = {
        "Hortaliças": 1,
        "Frutas": 2,
        "Especiarias": 3,
        "Cereais": 4,
        "SEM CLASSE": 99
    }

    df = df.copy()

    if coluna_classe in df.columns:
        df["_ordem_classe"] = df[coluna_classe].map(ordem).fillna(99)
    else:
        df["_ordem_classe"] = 99

    colunas = ["_ordem_classe"]

    if coluna_produto in df.columns:
        colunas.append(coluna_produto)

    df = df.sort_values(colunas)
    return df.drop(columns=["_ordem_classe"], errors="ignore")


def obter_periodo_semana(data_ref):
    data_ref = pd.to_datetime(data_ref).date()
    inicio = data_ref - timedelta(days=data_ref.weekday())
    fim = inicio + timedelta(days=6)
    inicio_anterior = inicio - timedelta(days=7)
    fim_anterior = fim - timedelta(days=7)

    return inicio, fim, inicio_anterior, fim_anterior


# =========================================================
# PRODUTOS QUE MAIS VARIARAM NA SEMANA
# =========================================================
def calcular_top_3_variacoes_semana(df_semana):
    base = df_semana.copy()

    if base.empty:
        return pd.DataFrame(), pd.DataFrame()

    base["data"] = pd.to_datetime(base["data"], errors="coerce")
    base["valor_kg"] = pd.to_numeric(
        base["valor_kg"],
        errors="coerce"
    )

    base = base.dropna(subset=["data", "produto", "valor_kg"])
    base = base[base["valor_kg"] > 0].copy()

    if base.empty:
        return pd.DataFrame(), pd.DataFrame()

    # Consolida eventuais registros repetidos do mesmo produto no mesmo dia.
    evolucao = (
        base
        .groupby(
            [base["data"].dt.date, "produto"],
            as_index=False
        )
        .agg(valor_kg=("valor_kg", "mean"))
        .rename(columns={"data": "data"})
    )

    evolucao["data"] = pd.to_datetime(
        evolucao["data"],
        errors="coerce"
    )

    resumo_variacao = (
        evolucao
        .groupby("produto", as_index=False)
        .agg(
            menor_valor_kg=("valor_kg", "min"),
            maior_valor_kg=("valor_kg", "max"),
            dias_cotados=("data", "nunique")
        )
    )

    # Para calcular variação real durante a semana, o produto
    # precisa ter cotação em pelo menos dois dias.
    resumo_variacao = resumo_variacao[
        resumo_variacao["dias_cotados"] >= 2
    ].copy()

    if resumo_variacao.empty:
        return pd.DataFrame(), pd.DataFrame()

    resumo_variacao["variacao_percentual_semana"] = (
        (
            resumo_variacao["maior_valor_kg"] -
            resumo_variacao["menor_valor_kg"]
        )
        / resumo_variacao["menor_valor_kg"]
        * 100
    )

    top_3 = (
        resumo_variacao
        .sort_values(
            "variacao_percentual_semana",
            ascending=False
        )
        .head(3)
        .reset_index(drop=True)
    )

    produtos_top_3 = top_3["produto"].tolist()

    evolucao_top_3 = evolucao[
        evolucao["produto"].isin(produtos_top_3)
    ].copy()

    evolucao_top_3 = evolucao_top_3.sort_values(
        ["data", "produto"]
    )

    return top_3, evolucao_top_3


# =========================================================
# PREPARAÇÃO DOS DADOS
# =========================================================
def preparar_relatorio_semanal(df_todas, data_ref, classe_sel="Todas"):
    df = df_todas.copy()

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"])

    if df.empty:
        return None

    df["produto"] = df["produto"].astype(str).str.strip().str.upper()
    df["classe"] = df["classe"].astype(str).str.strip().apply(corrigir_classe)

    for col in ["kg", "preco_min", "preco_max", "preco_medio", "valor_kg"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    inicio, fim, inicio_anterior, fim_anterior = obter_periodo_semana(data_ref)

    df_semana = df[
        (df["data"].dt.date >= inicio) &
        (df["data"].dt.date <= fim)
    ].copy()

    df_semana_anterior = df[
        (df["data"].dt.date >= inicio_anterior) &
        (df["data"].dt.date <= fim_anterior)
    ].copy()

    if classe_sel != "Todas":
        df_semana = df_semana[df_semana["classe"] == classe_sel].copy()
        df_semana_anterior = df_semana_anterior[
            df_semana_anterior["classe"] == classe_sel
        ].copy()

    df_semana = df_semana[df_semana["preco_medio"] > 0].copy()
    df_semana_anterior = df_semana_anterior[
        df_semana_anterior["preco_medio"] > 0
    ].copy()

    if df_semana.empty:
        return None

    # Média e amplitude semanal por produto.
    resumo_produto = (
        df_semana
        .groupby(["produto", "classe"], as_index=False)
        .agg(
            unidade=("unidade", "first"),
            kg=("kg", "mean"),
            preco_min=("preco_min", "min"),
            preco_max=("preco_max", "max"),
            preco_medio=("preco_medio", "mean"),
            valor_kg=("valor_kg", "mean"),
            qtd_cotacoes=("data", "count"),
            dias_cotados=("data", lambda s: s.dt.date.nunique())
        )
    )

    resumo_produto = ordenar_classes(resumo_produto)

    if not df_semana_anterior.empty:
        resumo_anterior = (
            df_semana_anterior
            .groupby(["produto", "classe"], as_index=False)
            .agg(
                valor_kg_anterior=("valor_kg", "mean"),
                preco_medio_anterior=("preco_medio", "mean"),
                qtd_cotacoes_anterior=("data", "count")
            )
        )

        comparativo = resumo_produto.merge(
            resumo_anterior,
            on=["produto", "classe"],
            how="left"
        )
    else:
        comparativo = resumo_produto.copy()
        comparativo["valor_kg_anterior"] = 0
        comparativo["preco_medio_anterior"] = 0
        comparativo["qtd_cotacoes_anterior"] = 0

    for col in [
        "valor_kg_anterior",
        "preco_medio_anterior",
        "qtd_cotacoes_anterior"
    ]:
        comparativo[col] = pd.to_numeric(
            comparativo[col],
            errors="coerce"
        ).fillna(0)

    comparativo["diferenca_valor_kg"] = (
        comparativo["valor_kg"] -
        comparativo["valor_kg_anterior"]
    )

    comparativo["variacao_percentual"] = comparativo.apply(
        lambda row: (
            (row["diferenca_valor_kg"] / row["valor_kg_anterior"]) * 100
            if row["valor_kg_anterior"] > 0 else 0
        ),
        axis=1
    )

    comparativo["alerta"] = comparativo[
        "variacao_percentual"
    ].apply(classificar_alerta)

    alertas = comparativo[
        comparativo["alerta"] != "Variação normal"
    ].copy()

    ordem_alertas = {
        "Alta crítica": 1,
        "Alta acentuada": 2,
        "Alta moderada": 3,
        "Queda acentuada": 4,
        "Queda relevante": 5,
        "Variação normal": 6
    }

    if not alertas.empty:
        alertas["_ordem_alerta"] = (
            alertas["alerta"].map(ordem_alertas).fillna(99)
        )

        alertas = alertas.sort_values(
            ["_ordem_alerta", "classe", "produto"]
        ).drop(columns=["_ordem_alerta"])

    comparaveis = comparativo[
        comparativo["valor_kg_anterior"] > 0
    ].copy()

    if comparaveis.empty:
        comparaveis = comparativo.copy()

    maior_alta = comparaveis.sort_values(
        "variacao_percentual",
        ascending=False
    ).iloc[0]

    maior_queda = comparaveis.sort_values(
        "variacao_percentual",
        ascending=True
    ).iloc[0]

    maior_preco_kg = resumo_produto.sort_values(
        "valor_kg",
        ascending=False
    ).iloc[0]

    valores_positivos = resumo_produto[
        resumo_produto["valor_kg"] > 0
    ].copy()

    if valores_positivos.empty:
        menor_preco_kg = resumo_produto.sort_values(
            "valor_kg",
            ascending=True
        ).iloc[0]
    else:
        menor_preco_kg = valores_positivos.sort_values(
            "valor_kg",
            ascending=True
        ).iloc[0]

    resumo_classe = (
        df_semana
        .groupby("classe", as_index=False)
        .agg(
            produtos=("produto", "nunique"),
            registros=("produto", "count"),
            preco_medio_classe=("preco_medio", "mean"),
            valor_kg_medio=("valor_kg", "mean")
        )
    )

    resumo_classe = ordenar_classes(
        resumo_classe,
        coluna_classe="classe",
        coluna_produto="classe"
    )

    evolucao_diaria = (
        df_semana
        .groupby(df_semana["data"].dt.date, as_index=False)
        .agg(
            produtos=("produto", "nunique"),
            registros=("produto", "count"),
            preco_medio=("preco_medio", "mean"),
            valor_kg_medio=("valor_kg", "mean")
        )
    )

    evolucao_diaria = evolucao_diaria.rename(columns={"data": "data"})
    evolucao_diaria["data"] = pd.to_datetime(
        evolucao_diaria["data"],
        errors="coerce"
    )

    top_3_variacoes, evolucao_top_3 = (
        calcular_top_3_variacoes_semana(df_semana)
    )

    return {
        "df_semana": df_semana,
        "resumo_produto": resumo_produto,
        "comparativo": comparativo,
        "alertas": alertas,
        "resumo_classe": resumo_classe,
        "evolucao_diaria": evolucao_diaria,
        "top_3_variacoes": top_3_variacoes,
        "evolucao_top_3": evolucao_top_3,
        "inicio": inicio,
        "fim": fim,
        "inicio_anterior": inicio_anterior,
        "fim_anterior": fim_anterior,
        "maior_alta": maior_alta,
        "maior_queda": maior_queda,
        "maior_preco_kg": maior_preco_kg,
        "menor_preco_kg": menor_preco_kg
    }


# =========================================================
# PDF - FUNÇÕES AUXILIARES
# =========================================================
def criar_estilos_pdf():
    styles = getSampleStyleSheet()

    estilo_titulo = styles["Title"].clone("titulo_relatorio_semanal")
    estilo_titulo.alignment = TA_CENTER
    estilo_titulo.fontSize = FONTE_TITULO
    estilo_titulo.leading = FONTE_TITULO + 3
    estilo_titulo.spaceAfter = 10

    estilo_subtitulo = styles["Heading2"].clone("subtitulo_relatorio_semanal")
    estilo_subtitulo.fontSize = FONTE_SUBTITULO
    estilo_subtitulo.leading = FONTE_SUBTITULO + 3
    estilo_subtitulo.spaceBefore = 10
    estilo_subtitulo.spaceAfter = 6

    estilo_normal = styles["Normal"].clone("normal_relatorio_semanal")
    estilo_normal.fontSize = FONTE_TEXTO
    estilo_normal.leading = FONTE_TEXTO + 3
    estilo_normal.alignment = TA_LEFT

    estilo_info = ParagraphStyle(
        "info_relatorio_semanal",
        parent=styles["Normal"],
        fontSize=FONTE_INFO,
        leading=FONTE_INFO + 2,
        textColor=colors.grey
    )

    return estilo_titulo, estilo_subtitulo, estilo_normal, estilo_info


def adicionar_numero_pagina(canvas, doc):
    canvas.saveState()

    largura, _ = A4
    numero_pagina = canvas.getPageNumber()

    canvas.setFont("Helvetica", FONTE_RODAPE)
    canvas.setFillColor(colors.grey)

    canvas.drawString(25, 15, "AMA | Sistema de Cotação")
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
        "cabecalho_tabela_semanal",
        fontName="Helvetica-Bold",
        fontSize=fonte,
        leading=fonte + 2,
        textColor=colors.white,
        alignment=TA_CENTER
    )

    estilo_celula = ParagraphStyle(
        "celula_tabela_semanal",
        fontName="Helvetica",
        fontSize=fonte,
        leading=fonte + 2,
        textColor=colors.black,
        alignment=TA_CENTER
    )

    estilo_celula_texto = ParagraphStyle(
        "celula_texto_tabela_semanal",
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
            elif j in colunas_texto:
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
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
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
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3)
    ])

    for coluna in colunas_texto:
        estilo.add("ALIGN", (coluna, 1), (coluna, -1), "LEFT")

    tabela.setStyle(estilo)
    return tabela


def criar_grafico_top_3_pdf(evolucao_top_3):
    if evolucao_top_3 is None or evolucao_top_3.empty:
        return None

    figura, eixo = plt.subplots(figsize=(7.4, 3.6))

    for produto, grupo in evolucao_top_3.groupby("produto"):
        grupo = grupo.sort_values("data")

        eixo.plot(
            grupo["data"],
            grupo["valor_kg"],
            marker="o",
            linewidth=2,
            label=str(produto)
        )

    eixo.set_title(
        "Evolução diária dos 3 produtos que mais variaram"
    )
    eixo.set_xlabel("Data")
    eixo.set_ylabel("Valor/kg médio (R$)")
    eixo.grid(True, alpha=0.25)
    eixo.legend(
        loc="best",
        fontsize=8
    )

    figura.autofmt_xdate()
    figura.tight_layout()

    memoria = BytesIO()
    figura.savefig(
        memoria,
        format="png",
        dpi=180,
        bbox_inches="tight"
    )
    plt.close(figura)
    memoria.seek(0)

    return Image(
        memoria,
        width=530,
        height=255
    )


# =========================================================
# PDF - RELATÓRIO SEMANAL
# =========================================================
def gerar_pdf_relatorio_semanal(
    dados,
    observacoes,
    nome_pdf,
    classe_sel
):
    doc = SimpleDocTemplate(
        nome_pdf,
        pagesize=A4,
        leftMargin=22,
        rightMargin=22,
        topMargin=25,
        bottomMargin=28
    )

    elementos = []

    estilo_titulo, estilo_subtitulo, estilo_normal, estilo_info = (
        criar_estilos_pdf()
    )

    df_semana = dados["df_semana"]
    resumo_produto = dados["resumo_produto"]
    alertas = dados["alertas"]
    resumo_classe = dados["resumo_classe"]
    evolucao_diaria = dados["evolucao_diaria"]
    top_3_variacoes = dados["top_3_variacoes"]
    evolucao_top_3 = dados["evolucao_top_3"]

    inicio = dados["inicio"]
    fim = dados["fim"]
    inicio_anterior = dados["inicio_anterior"]
    fim_anterior = dados["fim_anterior"]

    maior_alta = dados["maior_alta"]
    maior_queda = dados["maior_queda"]
    maior_preco_kg = dados["maior_preco_kg"]
    menor_preco_kg = dados["menor_preco_kg"]

    periodo_txt = (
        f"{inicio.strftime('%d/%m/%Y')} a "
        f"{fim.strftime('%d/%m/%Y')}"
    )

    periodo_anterior_txt = (
        f"{inicio_anterior.strftime('%d/%m/%Y')} a "
        f"{fim_anterior.strftime('%d/%m/%Y')}"
    )

    elementos.append(
        Paragraph("Relatório Semanal de Cotação", estilo_titulo)
    )
    elementos.append(
        Paragraph(
            "AMA - Autarquia Municipal de Abastecimento",
            estilo_info
        )
    )
    elementos.append(
        Paragraph(
            "Mercado do Produtor de Juazeiro-BA",
            estilo_info
        )
    )
    elementos.append(
        Paragraph(
            f"Data de emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            estilo_info
        )
    )
    elementos.append(Spacer(1, 10))

    # ================= 1. RESUMO EXECUTIVO =================
    elementos.append(
        Paragraph("1. Resumo executivo", estilo_subtitulo)
    )

    total_produtos = df_semana["produto"].nunique()
    total_registros = len(df_semana)
    dias_com_cotacao = df_semana["data"].dt.date.nunique()
    preco_medio_geral = df_semana["preco_medio"].mean()
    valor_kg_medio = df_semana["valor_kg"].mean()

    resumo = [
        ["Indicador", "Resultado"],
        ["Semana analisada", periodo_txt],
        ["Semana comparada", periodo_anterior_txt],
        ["Classe filtrada", str(classe_sel)],
        ["Produtos cotados", str(total_produtos)],
        ["Registros realizados", str(total_registros)],
        ["Dias com cotação", str(dias_com_cotacao)],
        ["Preço médio geral", formatar_moeda(preco_medio_geral)],
        ["Valor/kg médio", formatar_moeda(valor_kg_medio)],
        ["Total de alertas", str(len(alertas))]
    ]

    elementos.append(
        criar_tabela_pdf(
            resumo,
            larguras=[190, 340],
            fonte=10,
            colunas_texto=[0, 1]
        )
    )
    elementos.append(Spacer(1, 10))

    # ================= 2. DESTAQUES =================
    elementos.append(
        Paragraph("2. Destaques da semana", estilo_subtitulo)
    )

    destaques = [
        ["Destaque", "Produto", "Resultado"],
        [
            "Maior alta no valor/kg médio",
            str(maior_alta.get("produto", "")),
            formatar_percentual(
                maior_alta.get("variacao_percentual", 0)
            )
        ],
        [
            "Maior queda no valor/kg médio",
            str(maior_queda.get("produto", "")),
            formatar_percentual(
                maior_queda.get("variacao_percentual", 0)
            )
        ],
        [
            "Maior valor/kg médio",
            str(maior_preco_kg.get("produto", "")),
            formatar_moeda(maior_preco_kg.get("valor_kg", 0))
        ],
        [
            "Menor valor/kg médio",
            str(menor_preco_kg.get("produto", "")),
            formatar_moeda(menor_preco_kg.get("valor_kg", 0))
        ]
    ]

    elementos.append(
        criar_tabela_pdf(
            destaques,
            larguras=[150, 270, 110],
            fonte=FONTE_TABELA_PEQUENA,
            colunas_texto=[0, 1]
        )
    )
    elementos.append(Spacer(1, 10))

    # ================= 3. ALERTAS =================
    elementos.append(
        Paragraph(
            "3. Comparação com a semana anterior",
            estilo_subtitulo
        )
    )

    if alertas.empty:
        elementos.append(
            Paragraph(
                "Nenhuma variação relevante foi identificada em relação à semana anterior.",
                estilo_normal
            )
        )
    else:
        tabela_alertas = [[
            "Produto",
            "Classe",
            "Valor/kg ant.",
            "Valor/kg atual",
            "Variação",
            "Alerta"
        ]]

        for _, row in alertas.iterrows():
            tabela_alertas.append([
                str(row.get("produto", "")),
                str(row.get("classe", "")),
                formatar_moeda(row.get("valor_kg_anterior", 0)),
                formatar_moeda(row.get("valor_kg", 0)),
                formatar_percentual(
                    row.get("variacao_percentual", 0)
                ),
                str(row.get("alerta", ""))
            ])

        elementos.append(
            criar_tabela_pdf(
                tabela_alertas,
                larguras=[150, 70, 78, 78, 65, 90],
                fonte=10,
                colunas_texto=[0, 1, 5]
            )
        )

    elementos.append(Spacer(1, 10))

    # ================= 4. EVOLUÇÃO DIÁRIA =================
    elementos.append(
        Paragraph("4. Evolução diária da semana", estilo_subtitulo)
    )

    tabela_diaria = [[
        "Data",
        "Produtos",
        "Registros",
        "Preço médio",
        "Valor/kg médio"
    ]]

    for _, row in evolucao_diaria.iterrows():
        tabela_diaria.append([
            row["data"].strftime("%d/%m/%Y"),
            str(int(row.get("produtos", 0))),
            str(int(row.get("registros", 0))),
            formatar_moeda(row.get("preco_medio", 0)),
            formatar_moeda(row.get("valor_kg_medio", 0))
        ])

    elementos.append(
        criar_tabela_pdf(
            tabela_diaria,
            larguras=[90, 80, 80, 140, 140],
            fonte=10
        )
    )
    elementos.append(Spacer(1, 10))

    # ================= 5. PRODUTOS QUE MAIS VARIARAM =================
    elementos.append(
        Paragraph(
            "5. Três produtos que mais variaram na semana",
            estilo_subtitulo
        )
    )

    grafico_top_3 = criar_grafico_top_3_pdf(
        evolucao_top_3
    )

    if grafico_top_3 is None:
        elementos.append(
            Paragraph(
                "Não há produtos com cotações em pelo menos dois dias "
                "para gerar este gráfico.",
                estilo_normal
            )
        )
    else:
        elementos.append(grafico_top_3)
        elementos.append(Spacer(1, 6))

        nomes_top_3 = ", ".join(
            top_3_variacoes["produto"].astype(str).tolist()
        )

        elementos.append(
            Paragraph(
                texto_seguro(
                    "Produtos selecionados pela maior amplitude percentual "
                    f"do valor/kg na semana: {nomes_top_3}."
                ),
                estilo_info
            )
        )

    elementos.append(Spacer(1, 10))

    # ================= 6. RESUMO POR CLASSE =================
    elementos.append(
        Paragraph("6. Resumo por classe", estilo_subtitulo)
    )

    tabela_classe = [[
        "Classe",
        "Produtos",
        "Registros",
        "Preço médio",
        "Valor/kg médio"
    ]]

    for _, row in resumo_classe.iterrows():
        tabela_classe.append([
            str(row.get("classe", "")),
            str(int(row.get("produtos", 0))),
            str(int(row.get("registros", 0))),
            formatar_moeda(row.get("preco_medio_classe", 0)),
            formatar_moeda(row.get("valor_kg_medio", 0))
        ])

    elementos.append(
        criar_tabela_pdf(
            tabela_classe,
            larguras=[150, 80, 80, 110, 110],
            fonte=10,
            colunas_texto=[0]
        )
    )
    elementos.append(Spacer(1, 10))

    # ================= 7. MÉDIAS SEMANAIS =================
    elementos.append(
        Paragraph(
            "7. Médias semanais por produto",
            estilo_subtitulo
        )
    )

    tabela_produtos = [[
        "Classe",
        "Produto",
        "Unid.",
        "Kg",
        "Mín.",
        "Máx.",
        "Médio",
        "Valor/kg"
    ]]

    for _, row in resumo_produto.iterrows():
        tabela_produtos.append([
            str(row.get("classe", "")),
            str(row.get("produto", "")),
            str(row.get("unidade", "")),
            formatar_numero(row.get("kg", 0), 0),
            formatar_moeda(row.get("preco_min", 0)),
            formatar_moeda(row.get("preco_max", 0)),
            formatar_moeda(row.get("preco_medio", 0)),
            formatar_moeda(row.get("valor_kg", 0))
        ])

    elementos.append(
        criar_tabela_pdf(
            tabela_produtos,
            larguras=[58, 145, 42, 32, 55, 55, 65, 55, 44],
            fonte=9,
            colunas_texto=[0, 1, 2]
        )
    )
    elementos.append(Spacer(1, 10))

    # ================= 8. OBSERVAÇÕES =================
    elementos.append(
        Paragraph("8. Observações da semana", estilo_subtitulo)
    )

    if observacoes is None or observacoes.empty:
        elementos.append(
            Paragraph(
                "Nenhuma observação foi registrada para a semana analisada.",
                estilo_normal
            )
        )
    else:
        obs = observacoes.copy()

        if "data_ref" in obs.columns:
            obs["data_ref"] = pd.to_datetime(
                obs["data_ref"],
                errors="coerce"
            )

        obs = obs.head(40)

        for _, row in obs.iterrows():
            produto = texto_seguro(row.get("produto", ""))
            classe = texto_seguro(row.get("classe", ""))
            observacao = texto_seguro(row.get("observacao", ""))

            data_obs = ""
            if "data_ref" in row and pd.notnull(row.get("data_ref")):
                try:
                    data_obs = row.get("data_ref").strftime("%d/%m/%Y")
                except Exception:
                    data_obs = ""

            cabecalho_obs = f"<b>{produto}</b> ({classe})"
            if data_obs:
                cabecalho_obs += f" - {data_obs}"

            elementos.append(
                Paragraph(cabecalho_obs, estilo_normal)
            )
            elementos.append(
                Paragraph(
                    observacao.replace("\n", "<br/>"),
                    estilo_normal
                )
            )
            elementos.append(Spacer(1, 5))

        if len(observacoes) > 40:
            elementos.append(
                Paragraph(
                    f"Foram exibidas as 40 primeiras observações de um total de {len(observacoes)}.",
                    estilo_info
                )
            )

    elementos.append(Spacer(1, 10))

    # ================= 9. CONSIDERAÇÕES =================
    elementos.append(
        Paragraph(
            "9. Considerações automáticas",
            estilo_subtitulo
        )
    )

    texto = (
        f"Na semana de {periodo_txt}, foram analisados "
        f"{total_produtos} produtos em {dias_com_cotacao} dia(s) com cotação. "
        f"O preço médio geral foi de {formatar_moeda(preco_medio_geral)} "
        f"e o valor/kg médio foi de {formatar_moeda(valor_kg_medio)}. "
        f"Em comparação com a semana anterior, a maior alta no valor/kg médio "
        f"foi observada em {maior_alta.get('produto', '')}, com "
        f"{formatar_percentual(maior_alta.get('variacao_percentual', 0))}. "
        f"A maior queda ocorreu em {maior_queda.get('produto', '')}, com "
        f"{formatar_percentual(maior_queda.get('variacao_percentual', 0))}. "
        "As variações devem ser interpretadas considerando oferta, sazonalidade, "
        "custos de produção, qualidade, logística e comportamento do mercado."
    )

    elementos.append(
        Paragraph(texto_seguro(texto), estilo_normal)
    )

    elementos.append(Spacer(1, 10))
    elementos.append(
        Paragraph(
            "Relatório gerado automaticamente pelo Sistema de Cotação.",
            estilo_info
        )
    )

    doc.build(
        elementos,
        onFirstPage=adicionar_numero_pagina,
        onLaterPages=adicionar_numero_pagina
    )


# =========================================================
# TELA STREAMLIT
# =========================================================
def tela_relatorio_semanal(supabase):
    st.title("📅 Relatório Semanal")

    st.info(
        "Gere um relatório da semana com comparação com a semana anterior, "
        "destaques, alertas pelo valor/kg, evolução diária, resumo por classe, "
        "médias semanais por produto e observações."
    )

    try:
        df = carregar_todas_cotacoes(supabase)
    except Exception as e:
        st.error(f"Erro ao carregar cotações: {e}")
        return

    if df.empty:
        st.warning("Ainda não há cotações cadastradas.")
        return

    df = df.copy()
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"])

    if df.empty:
        st.warning("Não há datas válidas nas cotações.")
        return

    df["classe"] = (
        df["classe"]
        .astype(str)
        .str.strip()
        .apply(corrigir_classe)
    )

    st.subheader("🔎 Filtros")

    datas_disponiveis = sorted(
        df["data"].dt.date.dropna().unique().tolist(),
        reverse=True
    )

    col1, col2 = st.columns(2)

    with col1:
        data_ref = st.selectbox(
            "Escolha uma data da semana",
            datas_disponiveis,
            format_func=lambda d: d.strftime("%d/%m/%Y"),
            key="relatorio_semanal_data"
        )

    with col2:
        classe_sel = st.selectbox(
            "Classe",
            ["Todas"] + sorted(
                df["classe"].dropna().unique().tolist()
            ),
            key="relatorio_semanal_classe"
        )

    dados = preparar_relatorio_semanal(
        df_todas=df,
        data_ref=data_ref,
        classe_sel=classe_sel
    )

    inicio, fim, inicio_anterior, fim_anterior = (
        obter_periodo_semana(data_ref)
    )

    st.caption(
        f"Semana analisada: {inicio.strftime('%d/%m/%Y')} a "
        f"{fim.strftime('%d/%m/%Y')} | Semana anterior: "
        f"{inicio_anterior.strftime('%d/%m/%Y')} a "
        f"{fim_anterior.strftime('%d/%m/%Y')}"
    )

    if dados is None:
        st.warning(
            "Nenhuma cotação foi encontrada na semana selecionada."
        )
        return

    df_semana = dados["df_semana"]
    alertas = dados["alertas"]
    resumo_classe = dados["resumo_classe"]
    evolucao_diaria = dados["evolucao_diaria"]
    resumo_produto = dados["resumo_produto"]
    top_3_variacoes = dados["top_3_variacoes"]
    evolucao_top_3 = dados["evolucao_top_3"]

    st.divider()
    st.subheader("📌 Prévia do resumo")

    total_produtos = df_semana["produto"].nunique()
    total_registros = len(df_semana)
    dias_com_cotacao = df_semana["data"].dt.date.nunique()
    preco_medio_geral = df_semana["preco_medio"].mean()
    valor_kg_medio = df_semana["valor_kg"].mean()

    c1, c2, c3, c4, c5, c6 = st.columns(6)

    c1.metric("Produtos", total_produtos)
    c2.metric("Registros", total_registros)
    c3.metric("Dias cotados", dias_com_cotacao)
    c4.metric("Preço médio", formatar_moeda(preco_medio_geral))
    c5.metric("Valor/kg médio", formatar_moeda(valor_kg_medio))
    c6.metric("Alertas", len(alertas))

    st.markdown("#### Destaques da semana")

    destaques_tela = pd.DataFrame([
        {
            "Destaque": "Maior alta no valor/kg médio",
            "Produto": dados["maior_alta"].get("produto", ""),
            "Resultado": formatar_percentual(
                dados["maior_alta"].get(
                    "variacao_percentual",
                    0
                )
            )
        },
        {
            "Destaque": "Maior queda no valor/kg médio",
            "Produto": dados["maior_queda"].get("produto", ""),
            "Resultado": formatar_percentual(
                dados["maior_queda"].get(
                    "variacao_percentual",
                    0
                )
            )
        },
        {
            "Destaque": "Maior valor/kg médio",
            "Produto": dados["maior_preco_kg"].get("produto", ""),
            "Resultado": formatar_moeda(
                dados["maior_preco_kg"].get("valor_kg", 0)
            )
        },
        {
            "Destaque": "Menor valor/kg médio",
            "Produto": dados["menor_preco_kg"].get("produto", ""),
            "Resultado": formatar_moeda(
                dados["menor_preco_kg"].get("valor_kg", 0)
            )
        }
    ])

    st.dataframe(
        destaques_tela,
        use_container_width=True,
        hide_index=True
    )

    st.markdown("#### Evolução diária")

    evolucao_tela = evolucao_diaria.copy()
    evolucao_tela["Data"] = evolucao_tela["data"].dt.strftime(
        "%d/%m/%Y"
    )

    grafico = evolucao_tela[
        ["data", "valor_kg_medio"]
    ].set_index("data")

    st.line_chart(grafico)

    evolucao_tabela = evolucao_tela.rename(columns={
        "produtos": "Produtos",
        "registros": "Registros",
        "preco_medio": "Preço médio",
        "valor_kg_medio": "Valor/kg médio"
    })

    evolucao_tabela["Preço médio"] = (
        evolucao_tabela["Preço médio"].apply(formatar_moeda)
    )
    evolucao_tabela["Valor/kg médio"] = (
        evolucao_tabela["Valor/kg médio"].apply(formatar_moeda)
    )

    st.dataframe(
        evolucao_tabela[
            [
                "Data",
                "Produtos",
                "Registros",
                "Preço médio",
                "Valor/kg médio"
            ]
        ],
        use_container_width=True,
        hide_index=True
    )

    st.markdown(
        "#### Três produtos que mais variaram na semana"
    )

    if evolucao_top_3.empty:
        st.info(
            "Não há produtos com cotações em pelo menos dois dias "
            "para gerar este gráfico."
        )
    else:
        grafico_top_3_tela = (
            evolucao_top_3
            .pivot(
                index="data",
                columns="produto",
                values="valor_kg"
            )
            .sort_index()
        )

        st.line_chart(grafico_top_3_tela)

        tabela_top_3_tela = top_3_variacoes.copy()

        tabela_top_3_tela[
            "variacao_percentual_semana"
        ] = tabela_top_3_tela[
            "variacao_percentual_semana"
        ].apply(formatar_percentual)

        tabela_top_3_tela = tabela_top_3_tela.rename(
            columns={
                "produto": "Produto",
                "menor_valor_kg": "Menor valor/kg",
                "maior_valor_kg": "Maior valor/kg",
                "dias_cotados": "Dias cotados",
                "variacao_percentual_semana": "Variação na semana"
            }
        )

        tabela_top_3_tela["Menor valor/kg"] = (
            tabela_top_3_tela["Menor valor/kg"]
            .apply(formatar_moeda)
        )

        tabela_top_3_tela["Maior valor/kg"] = (
            tabela_top_3_tela["Maior valor/kg"]
            .apply(formatar_moeda)
        )

        st.dataframe(
            tabela_top_3_tela[
                [
                    "Produto",
                    "Menor valor/kg",
                    "Maior valor/kg",
                    "Variação na semana"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

    st.markdown("#### Resumo por classe")

    resumo_classe_tela = resumo_classe.copy()

    resumo_classe_tela["preco_medio_classe"] = (
        resumo_classe_tela[
            "preco_medio_classe"
        ].apply(formatar_moeda)
    )

    resumo_classe_tela["valor_kg_medio"] = (
        resumo_classe_tela[
            "valor_kg_medio"
        ].apply(formatar_moeda)
    )

    resumo_classe_tela = resumo_classe_tela.rename(columns={
        "classe": "Classe",
        "produtos": "Produtos",
        "registros": "Registros",
        "preco_medio_classe": "Preço médio",
        "valor_kg_medio": "Valor/kg médio"
    })

    st.dataframe(
        resumo_classe_tela,
        use_container_width=True,
        hide_index=True
    )

    if not alertas.empty:
        st.markdown(
            "#### Alertas em relação à semana anterior"
        )

        alertas_tela = alertas.copy()

        for col in [
            "valor_kg_anterior",
            "valor_kg",
            "diferenca_valor_kg"
        ]:
            alertas_tela[col] = (
                alertas_tela[col].apply(formatar_moeda)
            )

        alertas_tela["variacao_percentual"] = (
            alertas_tela[
                "variacao_percentual"
            ].apply(formatar_percentual)
        )

        alertas_tela = alertas_tela.rename(columns={
            "produto": "Produto",
            "classe": "Classe",
            "valor_kg_anterior": "Valor/kg semana anterior",
            "valor_kg": "Valor/kg semana atual",
            "variacao_percentual": "Variação",
            "alerta": "Alerta"
        })

        st.dataframe(
            alertas_tela[
                [
                    "Produto",
                    "Classe",
                    "Valor/kg semana anterior",
                    "Valor/kg semana atual",
                    "Variação",
                    "Alerta"
                ]
            ],
            use_container_width=True,
            hide_index=True
        )

    with st.expander("📋 Ver médias semanais por produto"):
        tabela_produtos = resumo_produto.copy()

        for col in [
            "preco_min",
            "preco_max",
            "preco_medio",
            "valor_kg"
        ]:
            tabela_produtos[col] = (
                tabela_produtos[col].apply(formatar_moeda)
            )

        tabela_produtos = tabela_produtos.rename(columns={
            "classe": "Classe",
            "produto": "Produto",
            "unidade": "Unidade",
            "kg": "Kg",
            "preco_min": "Preço mínimo",
            "preco_max": "Preço máximo",
            "preco_medio": "Preço médio",
            "valor_kg": "Valor/kg médio",
            "qtd_cotacoes": "Cotações",
            "dias_cotados": "Dias cotados"
        })

        st.dataframe(
            tabela_produtos,
            use_container_width=True,
            hide_index=True
        )

    st.divider()
    st.subheader("📄 Gerar PDF")

    if st.button(
        "📄 Gerar Relatório Semanal em PDF",
        type="primary"
    ):
        try:
            observacoes = carregar_observacoes_periodo(
                supabase=supabase,
                data_inicial=inicio,
                data_final=fim,
                produto=None
            )

            nome_pdf = (
                f"relatorio_semanal_"
                f"{inicio.strftime('%d-%m-%Y')}_a_"
                f"{fim.strftime('%d-%m-%Y')}.pdf"
            )

            gerar_pdf_relatorio_semanal(
                dados=dados,
                observacoes=observacoes,
                nome_pdf=nome_pdf,
                classe_sel=classe_sel
            )

            with open(nome_pdf, "rb") as f:
                st.download_button(
                    "📥 Baixar Relatório Semanal",
                    f,
                    file_name=nome_pdf,
                    mime="application/pdf"
                )

            st.success(
                "Relatório semanal gerado com sucesso."
            )

        except Exception as e:
            st.error(
                f"Erro ao gerar relatório semanal: {e}"
            )
