from datetime import datetime
from xml.sax.saxutils import escape

import streamlit as st
import pandas as pd

from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT

from dados_utils import carregar_todas_cotacoes
from observacoes_produtos import carregar_observacoes_periodo
from utils import corrigir_classe


# =========================================================
# CONFIGURAÇÃO DOS TAMANHOS DAS FONTES
# =========================================================
# Aqui ficam os tamanhos principais do relatório.
# Se quiser aumentar ou diminuir depois, mexa somente aqui.

FONTE_TITULO = 18
FONTE_SUBTITULO = 14
FONTE_TEXTO = 10.5
FONTE_INFO = 9
FONTE_RODAPE = 8

# Tabelas pequenas: resumo executivo, destaques e resumo por classe.
FONTE_TABELA_PEQUENA = 9.5

# Tabelas médias: alertas de variação.
FONTE_TABELA_MEDIA = 8.5

# Tabela grande: cotação completa por classe.
# Não recomendo passar muito de 7.5, pois pode estourar a largura da página.
FONTE_TABELA_GRANDE = 8.5


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
    """
    Evita erro no PDF caso o texto tenha caracteres especiais como &, < ou >.
    """
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
    else:
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

    colunas_ordem = ["_ordem_classe"]

    if coluna_produto in df.columns:
        colunas_ordem.append(coluna_produto)

    df = df.sort_values(colunas_ordem)
    df = df.drop(columns=["_ordem_classe"], errors="ignore")

    return df


# =========================================================
# PREPARAÇÃO DOS DADOS
# =========================================================
def preparar_relatorio_diario(df_todas, data_ref, classe_sel="Todas"):
    df = df_todas.copy()

    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    df = df.dropna(subset=["data"])

    df["produto"] = df["produto"].astype(str).str.strip().str.upper()
    df["classe"] = df["classe"].astype(str).str.strip().apply(corrigir_classe)

    for col in ["kg", "preco_min", "preco_max", "preco_medio", "valor_kg"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    data_ref = pd.to_datetime(data_ref).date()

    df_dia = df[df["data"].dt.date == data_ref].copy()

    if classe_sel != "Todas":
        df_dia = df_dia[df_dia["classe"] == classe_sel].copy()

    df_dia = df_dia[df_dia["preco_medio"] > 0].copy()

    if df_dia.empty:
        return None

    df_dia = ordenar_classes(df_dia)

    datas_anteriores = df[df["data"].dt.date < data_ref]["data"].dropna()

    if datas_anteriores.empty:
        data_anterior = None
        df_anterior = pd.DataFrame()
    else:
        data_anterior = datas_anteriores.max().date()
        df_anterior = df[df["data"].dt.date == data_anterior].copy()

        if classe_sel != "Todas":
            df_anterior = df_anterior[df_anterior["classe"] == classe_sel].copy()

    comparativo = df_dia[
        [
            "produto",
            "classe",
            "unidade",
            "kg",
            "preco_medio",
            "valor_kg"
        ]
    ].copy()

    comparativo = comparativo.rename(columns={
        "preco_medio": "preco_medio_atual",
        "valor_kg": "valor_kg_atual"
    })

    if not df_anterior.empty:
        anterior_resumo = (
            df_anterior
            .sort_values("data")
            .drop_duplicates(subset=["produto"], keep="last")
            [
                [
                    "produto",
                    "preco_medio",
                    "valor_kg"
                ]
            ]
            .rename(columns={
                "preco_medio": "preco_medio_anterior",
                "valor_kg": "valor_kg_anterior"
            })
        )

        comparativo = comparativo.merge(
            anterior_resumo,
            on="produto",
            how="left"
        )
    else:
        comparativo["preco_medio_anterior"] = 0
        comparativo["valor_kg_anterior"] = 0

    comparativo["preco_medio_anterior"] = pd.to_numeric(
        comparativo["preco_medio_anterior"],
        errors="coerce"
    ).fillna(0)

    comparativo["valor_kg_anterior"] = pd.to_numeric(
        comparativo["valor_kg_anterior"],
        errors="coerce"
    ).fillna(0)

    # A variação do relatório diário agora é calculada pelo VALOR/KG,
    # não pelo preço médio da caixa/unidade.
    comparativo["diferenca"] = (
        comparativo["valor_kg_atual"] -
        comparativo["valor_kg_anterior"]
    )

    comparativo["variacao_percentual"] = comparativo.apply(
        lambda row: (
            (row["diferenca"] / row["valor_kg_anterior"]) * 100
            if row["valor_kg_anterior"] > 0 else 0
        ),
        axis=1
    )

    comparativo["alerta"] = comparativo["variacao_percentual"].apply(classificar_alerta)

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
        alertas["_ordem_alerta"] = alertas["alerta"].map(ordem_alertas).fillna(99)
        alertas = alertas.sort_values(
            ["_ordem_alerta", "classe", "produto"]
        ).drop(columns=["_ordem_alerta"])

    # Considera nos rankings somente produtos que possuem valor/kg anterior
    # válido. Isso evita tratar produto sem histórico como alta ou queda de 0%.
    comparaveis = comparativo[
        comparativo["valor_kg_anterior"] > 0
    ].copy()

    ranking_altas = comparaveis[
        comparaveis["variacao_percentual"] > 0
    ].sort_values(
        "variacao_percentual",
        ascending=False
    ).head(5).copy()

    ranking_quedas = comparaveis[
        comparaveis["variacao_percentual"] < 0
    ].sort_values(
        "variacao_percentual",
        ascending=True
    ).head(5).copy()

    if not ranking_altas.empty:
        maior_alta = ranking_altas.iloc[0]
    else:
        maior_alta = pd.Series({
            "produto": "Nenhum produto",
            "variacao_percentual": 0.0,
            "valor_kg_anterior": 0.0,
            "valor_kg_atual": 0.0
        })

    if not ranking_quedas.empty:
        maior_queda = ranking_quedas.iloc[0]
    else:
        maior_queda = pd.Series({
            "produto": "Nenhum produto",
            "variacao_percentual": 0.0,
            "valor_kg_anterior": 0.0,
            "valor_kg_atual": 0.0
        })

    maior_preco_kg = df_dia.sort_values(
        "valor_kg",
        ascending=False
    ).iloc[0]

    df_valor_positivo = df_dia[df_dia["valor_kg"] > 0].copy()

    if df_valor_positivo.empty:
        menor_preco_kg = df_dia.sort_values(
            "valor_kg",
            ascending=True
        ).iloc[0]
    else:
        menor_preco_kg = df_valor_positivo.sort_values(
            "valor_kg",
            ascending=True
        ).iloc[0]

    resumo_classe = (
        df_dia
        .groupby("classe", as_index=False)
        .agg(
            produtos=("produto", "nunique"),
            preco_medio_classe=("preco_medio", "mean"),
            valor_kg_medio=("valor_kg", "mean")
        )
    )

    resumo_classe = ordenar_classes(
        resumo_classe,
        coluna_classe="classe",
        coluna_produto="classe"
    )

    resultado = {
        "df_dia": df_dia,
        "comparativo": comparativo,
        "alertas": alertas,
        "resumo_classe": resumo_classe,
        "data_anterior": data_anterior,
        "comparaveis": comparaveis,
        "ranking_altas": ranking_altas,
        "ranking_quedas": ranking_quedas,
        "maior_alta": maior_alta,
        "maior_queda": maior_queda,
        "maior_preco_kg": maior_preco_kg,
        "menor_preco_kg": menor_preco_kg
    }

    return resultado


# =========================================================
# PDF - FUNÇÕES AUXILIARES
# =========================================================
def criar_estilos_pdf():
    styles = getSampleStyleSheet()

    estilo_titulo = styles["Title"].clone("titulo_relatorio_diario")
    estilo_titulo.alignment = TA_CENTER
    estilo_titulo.fontSize = FONTE_TITULO
    estilo_titulo.leading = FONTE_TITULO + 3
    estilo_titulo.spaceAfter = 10

    estilo_subtitulo = styles["Heading2"].clone("subtitulo_relatorio_diario")
    estilo_subtitulo.fontSize = FONTE_SUBTITULO
    estilo_subtitulo.leading = FONTE_SUBTITULO + 3
    estilo_subtitulo.spaceBefore = 10
    estilo_subtitulo.spaceAfter = 6

    estilo_normal = styles["Normal"].clone("normal_relatorio_diario")
    estilo_normal.fontSize = FONTE_TEXTO
    estilo_normal.leading = FONTE_TEXTO + 3
    estilo_normal.alignment = TA_LEFT

    estilo_info = ParagraphStyle(
        "info_relatorio_diario",
        parent=styles["Normal"],
        fontSize=FONTE_INFO,
        leading=FONTE_INFO + 2,
        textColor=colors.grey
    )

    return estilo_titulo, estilo_subtitulo, estilo_normal, estilo_info


def adicionar_numero_pagina(canvas, doc):
    """
    Adiciona rodapé e número de página em todas as páginas do PDF.
    """
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
    """
    Cria tabela em PDF com fonte controlada.

    colunas_texto:
    Informe os índices das colunas que têm textos maiores.
    Essas colunas são transformadas em Paragraph para quebrar linha corretamente.
    Exemplo: colunas_texto=[0, 1]
    """
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
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
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
# PDF - RELATÓRIO DIÁRIO
# =========================================================
def gerar_pdf_relatorio_diario(
    dados,
    observacoes,
    nome_pdf,
    data_ref,
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

    estilo_titulo, estilo_subtitulo, estilo_normal, estilo_info = criar_estilos_pdf()

    df_dia = dados["df_dia"]
    alertas = dados["alertas"]
    resumo_classe = dados["resumo_classe"]
    data_anterior = dados["data_anterior"]

    maior_alta = dados["maior_alta"]
    maior_queda = dados["maior_queda"]
    maior_preco_kg = dados["maior_preco_kg"]
    menor_preco_kg = dados["menor_preco_kg"]

    data_ref = pd.to_datetime(data_ref).date()
    data_txt = data_ref.strftime("%d/%m/%Y")

    elementos.append(Paragraph(f"Relatório Diário de Cotação - {data_txt}", estilo_titulo))
    elementos.append(Paragraph("AMA - Autarquia Municipal de Abastecimento", estilo_info))
    elementos.append(Paragraph("Mercado do Produtor de Juazeiro-BA", estilo_info))
    #elementos.append(Paragraph(f"Data da cotação: {data_txt}", estilo_info))
    #elementos.append(Paragraph(f"Data de emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}", estilo_info))
    elementos.append(Spacer(1, 10))

    # ================= 1. RESUMO EXECUTIVO =================
    elementos.append(Paragraph("1. Resumo executivo", estilo_subtitulo))

    total_produtos = df_dia["produto"].nunique()
    total_registros = len(df_dia)
    preco_medio_geral = df_dia["preco_medio"].mean()
    valor_kg_medio = df_dia["valor_kg"].mean()

    resumo = [
        ["Indicador", "Resultado"],
        ["Data da cotação", data_txt],
        ["Data comparada", data_anterior.strftime("%d/%m/%Y") if data_anterior else "Sem data anterior"],
        ["Classe filtrada", str(classe_sel)],
        ["Produtos cotados", str(total_produtos)],
        ["Preço médio geral", formatar_moeda(preco_medio_geral)],
        ["Valor/kg médio", formatar_moeda(valor_kg_medio)],
        ["Total de alertas", str(len(alertas))]
    ]

    elementos.append(
        criar_tabela_pdf(
            resumo,
            larguras=[190, 340],
            fonte=FONTE_TABELA_PEQUENA,
            colunas_texto=[0, 1]
        )
    )
    elementos.append(Spacer(1, 10))

    # ================= 2. DESTAQUES DO DIA =================
    elementos.append(Paragraph("2. Destaques do dia", estilo_subtitulo))

    destaques = [
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
            "Maior preço/kg",
            str(maior_preco_kg.get("produto", "")),
            formatar_moeda(maior_preco_kg.get("valor_kg", 0))
        ],
        [
            "Menor preço/kg",
            str(menor_preco_kg.get("produto", "")),
            formatar_moeda(menor_preco_kg.get("valor_kg", 0))
        ]
    ]

    elementos.append(
        criar_tabela_pdf(
            destaques,
            larguras=[120, 300, 110],
            fonte=FONTE_TABELA_PEQUENA,
            colunas_texto=[0, 1]
        )
    )
    elementos.append(Spacer(1, 10))

    # ================= 3. ALERTAS DE VARIAÇÃO =================
    elementos.append(Paragraph("3. Alertas de variação", estilo_subtitulo))

    if alertas.empty:
        elementos.append(Paragraph(
            "Nenhuma variação relevante foi identificada na data selecionada.",
            estilo_normal
        ))
    else:
        dados_alertas = [[
            "Produto",
            "Classe",
            "Valor/kg ant.",
            "Valor/kg atual",
            "Variação",
            "Alerta"
        ]]

        for _, row in alertas.iterrows():
            dados_alertas.append([
                str(row.get("produto", "")),
                str(row.get("classe", "")),
                formatar_moeda(row.get("valor_kg_anterior", 0)),
                formatar_moeda(row.get("valor_kg_atual", 0)),
                formatar_percentual(row.get("variacao_percentual", 0)),
                str(row.get("alerta", ""))
            ])

        elementos.append(
            criar_tabela_pdf(
                dados_alertas,
                larguras=[150, 70, 75, 75, 65, 95],
                fonte=FONTE_TABELA_MEDIA,
                colunas_texto=[0, 1, 5]
            )
        )

    elementos.append(Spacer(1, 10))

    # ================= 4. RESUMO POR CLASSE =================
    elementos.append(Paragraph("4. Resumo por classe", estilo_subtitulo))

    dados_classe = [[
        "Classe",
        "Produtos",
        "Preço médio",
        "Valor/kg médio"
    ]]

    for _, row in resumo_classe.iterrows():
        dados_classe.append([
            str(row.get("classe", "")),
            str(int(row.get("produtos", 0))),
            formatar_moeda(row.get("preco_medio_classe", 0)),
            formatar_moeda(row.get("valor_kg_medio", 0))
        ])

    elementos.append(
        criar_tabela_pdf(
            dados_classe,
            larguras=[160, 90, 140, 140],
            fonte=FONTE_TABELA_PEQUENA,
            colunas_texto=[0]
        )
    )

    elementos.append(Spacer(1, 10))

    # ================= 5. COTAÇÃO COMPLETA POR CLASSE =================
    elementos.append(Paragraph("5. Cotação completa por classe", estilo_subtitulo))

    cotacao = df_dia.copy()

    dados_cotacao = [[
        "Classe",
        "Produto",
        "Unid.",
        "Kg",
        "Preço mín.",
        "Preço máx.",
        "Preço médio",
        "Valor/kg"
    ]]

    for _, row in cotacao.iterrows():
        dados_cotacao.append([
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
            dados_cotacao,
            larguras=[62, 155, 36, 34, 61, 61, 68, 53],
            fonte=FONTE_TABELA_GRANDE,
            colunas_texto=[0, 1, 2]
        )
    )

    elementos.append(Spacer(1, 10))

    # ================= 6. OBSERVAÇÕES DO DIA =================
    elementos.append(Paragraph("6. Observações do dia", estilo_subtitulo))

    if observacoes is None or observacoes.empty:
        elementos.append(Paragraph(
            "Nenhuma observação foi registrada para esta data.",
            estilo_normal
        ))
    else:
        obs = observacoes.copy()

        if "data_ref" in obs.columns:
            obs["data_ref"] = pd.to_datetime(obs["data_ref"], errors="coerce")

        obs = obs.head(30)

        for _, row in obs.iterrows():
            produto = texto_seguro(row.get("produto", ""))
            classe = texto_seguro(row.get("classe", ""))
            observacao = texto_seguro(row.get("observacao", ""))

            elementos.append(Paragraph(
                f"<b>{produto}</b> ({classe})",
                estilo_normal
            ))

            elementos.append(Paragraph(
                observacao.replace("\n", "<br/>"),
                estilo_normal
            ))

            elementos.append(Spacer(1, 5))

        if len(observacoes) > 30:
            elementos.append(Paragraph(
                f"Foram exibidas as 30 primeiras observações de um total de {len(observacoes)}.",
                estilo_info
            ))

    elementos.append(Spacer(1, 10))

    # ================= 7. CONSIDERAÇÕES AUTOMÁTICAS =================
    elementos.append(Paragraph("7. Considerações automáticas", estilo_subtitulo))

    texto = (
        f"Na cotação de {data_txt}, foram analisados {total_produtos} produtos. "
        f"O preço médio geral foi de {formatar_moeda(preco_medio_geral)} e o valor/kg médio foi de "
        f"{formatar_moeda(valor_kg_medio)}. "
        f"Considerando a variação do valor/kg, o produto com maior alta foi "
        f"{maior_alta.get('produto', '')}, com variação de "
        f"{formatar_percentual(maior_alta.get('variacao_percentual', 0))}. "
        f"A maior queda no valor/kg foi observada em {maior_queda.get('produto', '')}, "
        f"com variação de {formatar_percentual(maior_queda.get('variacao_percentual', 0))}. "
        "As variações devem ser interpretadas considerando oferta, sazonalidade, custos de produção, "
        "qualidade dos produtos, logística e comportamento do mercado no período analisado."
    )

    elementos.append(Paragraph(texto_seguro(texto), estilo_normal))

    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph(
        "Relatório gerado automaticamente pelo Sistema de Cotação.",
        estilo_info
    ))

    doc.build(
        elementos,
        onFirstPage=adicionar_numero_pagina,
        onLaterPages=adicionar_numero_pagina
    )


# =========================================================
# TELA STREAMLIT
# =========================================================
def tela_relatorio_diario(supabase):
    st.title("📄 Relatório Diário")

    st.info(
        "Gere um relatório diário com resumo executivo, destaques do dia, alertas de variação, "
        "cotação completa por classe, observações e considerações automáticas. "
        "As altas, quedas e alertas são calculados pelo valor/kg, considerando "
        "nos rankings apenas produtos que também possuem cotação na data anterior."
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

    df["classe"] = df["classe"].astype(str).str.strip().apply(corrigir_classe)

    st.subheader("🔎 Filtros")

    datas_disponiveis = sorted(
        df["data"].dt.date.dropna().unique().tolist(),
        reverse=True
    )

    col1, col2 = st.columns(2)

    with col1:
        data_ref = st.selectbox(
            "Data da cotação",
            datas_disponiveis,
            format_func=lambda d: d.strftime("%d/%m/%Y"),
            key="relatorio_diario_data"
        )

    with col2:
        classe_sel = st.selectbox(
            "Classe",
            ["Todas"] + sorted(df["classe"].dropna().unique().tolist()),
            key="relatorio_diario_classe"
        )

    dados = preparar_relatorio_diario(
        df_todas=df,
        data_ref=data_ref,
        classe_sel=classe_sel
    )

    if dados is None:
        st.warning("Nenhum dado encontrado para gerar o relatório diário.")
        return

    df_dia = dados["df_dia"]
    alertas = dados["alertas"]
    resumo_classe = dados["resumo_classe"]

    st.divider()
    st.subheader("📌 Prévia do resumo")

    total_produtos = df_dia["produto"].nunique()
    total_registros = len(df_dia)
    preco_medio_geral = df_dia["preco_medio"].mean()
    valor_kg_medio = df_dia["valor_kg"].mean()

    c1, c2, c3, c4, c5 = st.columns(5)

    c1.metric("Produtos cotados", total_produtos)
    c2.metric("Registros", total_registros)
    c3.metric("Preço médio geral", formatar_moeda(preco_medio_geral))
    c4.metric("Valor/kg médio", formatar_moeda(valor_kg_medio))
    c5.metric("Alertas", len(alertas))

    st.markdown("#### Destaques do dia")

    destaques_tela = pd.DataFrame([
        {
            "Destaque": "Maior alta no valor/kg",
            "Produto": dados["maior_alta"].get("produto", ""),
            "Resultado": formatar_percentual(dados["maior_alta"].get("variacao_percentual", 0))
        },
        {
            "Destaque": "Maior queda no valor/kg",
            "Produto": dados["maior_queda"].get("produto", ""),
            "Resultado": formatar_percentual(dados["maior_queda"].get("variacao_percentual", 0))
        },
        {
            "Destaque": "Maior preço/kg",
            "Produto": dados["maior_preco_kg"].get("produto", ""),
            "Resultado": formatar_moeda(dados["maior_preco_kg"].get("valor_kg", 0))
        },
        {
            "Destaque": "Menor preço/kg",
            "Produto": dados["menor_preco_kg"].get("produto", ""),
            "Resultado": formatar_moeda(dados["menor_preco_kg"].get("valor_kg", 0))
        }
    ])

    st.dataframe(
        destaques_tela,
        use_container_width=True,
        hide_index=True
    )

    st.markdown("#### Resumo por classe")

    resumo_classe_tela = resumo_classe.copy()

    resumo_classe_tela["preco_medio_classe"] = resumo_classe_tela["preco_medio_classe"].apply(formatar_moeda)
    resumo_classe_tela["valor_kg_medio"] = resumo_classe_tela["valor_kg_medio"].apply(formatar_moeda)

    resumo_classe_tela = resumo_classe_tela.rename(columns={
        "classe": "Classe",
        "produtos": "Produtos",
        "preco_medio_classe": "Preço médio",
        "valor_kg_medio": "Valor/kg médio"
    })

    st.dataframe(
        resumo_classe_tela,
        use_container_width=True,
        hide_index=True
    )

    if not alertas.empty:
        st.markdown("#### Alertas de variação")

        alertas_tela = alertas.copy()

        for col in ["valor_kg_anterior", "valor_kg_atual", "diferenca"]:
            if col in alertas_tela.columns:
                alertas_tela[col] = alertas_tela[col].apply(formatar_moeda)

        alertas_tela["variacao_percentual"] = alertas_tela["variacao_percentual"].apply(formatar_percentual)

        alertas_tela = alertas_tela.rename(columns={
            "produto": "Produto",
            "classe": "Classe",
            "valor_kg_anterior": "Valor/kg anterior",
            "valor_kg_atual": "Valor/kg atual",
            "variacao_percentual": "Variação",
            "alerta": "Alerta"
        })

        colunas_alerta = [
            "Produto",
            "Classe",
            "Valor/kg anterior",
            "Valor/kg atual",
            "Variação",
            "Alerta"
        ]

        st.dataframe(
            alertas_tela[colunas_alerta],
            use_container_width=True,
            hide_index=True
        )

    st.divider()
    st.subheader("📄 Gerar PDF")

    if st.button("📄 Gerar Relatório Diário em PDF", type="primary"):
        try:
            observacoes = carregar_observacoes_periodo(
                supabase=supabase,
                data_inicial=data_ref,
                data_final=data_ref,
                produto=None
            )

            nome_pdf = f"relatorio_diario_{data_ref.strftime('%d-%m-%Y')}.pdf"

            gerar_pdf_relatorio_diario(
                dados=dados,
                observacoes=observacoes,
                nome_pdf=nome_pdf,
                data_ref=data_ref,
                classe_sel=classe_sel
            )

            with open(nome_pdf, "rb") as f:
                st.download_button(
                    "📥 Baixar Relatório Diário",
                    f,
                    file_name=nome_pdf,
                    mime="application/pdf"
                )

            st.success("Relatório diário gerado com sucesso.")

        except Exception as e:
            st.error(f"Erro ao gerar relatório diário: {e}")
