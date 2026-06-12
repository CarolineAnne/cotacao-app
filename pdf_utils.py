import pandas as pd

from datetime import datetime

from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet

from utils import corrigir_classe


def adicionar_numero_pagina(canvas, doc):
    """Adiciona rodapé com número da página em todos os PDFs gerados."""
    canvas.saveState()

    largura, altura = A4
    numero_pagina = canvas.getPageNumber()

    canvas.setFont("Helvetica", 8)
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

# ================== GERAR PDF =========================
def gerar_pdf(df, nome_pdf):
    doc = SimpleDocTemplate(
        nome_pdf,
        pagesize=A4,
        leftMargin=10,
        rightMargin=10,
        topMargin=5,
        bottomMargin=5
    )

    styles = getSampleStyleSheet()
    elementos = []

    df = df.copy()

    if "preco_medio" in df.columns:
        df["preco_medio"] = pd.to_numeric(
            df["preco_medio"],
            errors="coerce"
        ).fillna(0)

        df = df[df["preco_medio"] > 0].copy()

    if df.empty:
        elementos.append(Paragraph(
            "Nenhum produto com preço maior que zero foi encontrado para gerar o relatório.",
            styles["Normal"]
        ))
        doc.build(
        elementos,
        onFirstPage=adicionar_numero_pagina,
        onLaterPages=adicionar_numero_pagina
    )
        return

    df["produto"] = df["produto"].astype(str).str.strip().str.upper()
    df["classe"] = df["classe"].apply(corrigir_classe)

    ordem_classes = ["Hortaliças", "Frutas", "Especiarias", "Cereais", "SEM CLASSE"]

    df["ordem_classe"] = df["classe"].map({
        "Hortaliças": 1,
        "Frutas": 2,
        "Especiarias": 3,
        "Cereais": 4,
        "SEM CLASSE": 99
    })

    df = df.sort_values(["ordem_classe", "produto"])

    if "data" not in df.columns:
        raise ValueError("Coluna data não existe")

    if "classe" not in df.columns:
        raise ValueError("Coluna classe não existe")

    classes = [c for c in ordem_classes if c in df["classe"].dropna().unique()]

    # 🔥 GARANTIA EXTRA
    if len(classes) == 0:
        raise ValueError("Nenhuma classe encontrada para gerar PDF.")

    for i, c in enumerate(classes):
        dados_classe = df[df["classe"] == c].copy()
        dados_classe = dados_classe.drop(columns=["ordem_classe"], errors="ignore")

        # 🔹 evita erro se não tiver dados
        if dados_classe.empty:
            continue

        # 🔹 PEGA A DATA DA COTAÇÃO (ANTES DE QUALQUER ALTERAÇÃO)
        if "data" not in dados_classe.columns:
            raise ValueError("Coluna 'data' não encontrada para gerar o PDF.")

        data_ref = dados_classe["data"].max()
        data_cotacao = pd.to_datetime(data_ref).strftime('%d/%m/%Y')
        
        # 🔹 REMOVE COLUNAS DESNECESSÁRIAS
        colunas_remover = [col for col in ["classe", "id"] if col in dados_classe.columns]
        dados_classe = dados_classe.drop(columns=colunas_remover)

        # 🔹 DEFINE ORDEM DAS COLUNAS (IMPORTANTE PRA NÃO BAGUNÇAR)
        colunas_ordem = [
            "produto",
            "unidade",
            "kg",
            "preco_min",
            "preco_max",
            "preco_medio",
            "valor_kg"
        ]

        colunas_existentes = [col for col in colunas_ordem if col in dados_classe.columns]
        dados_classe = dados_classe[colunas_existentes]

        # 🔹 RENOMEIA COLUNAS (CABEÇALHO BONITO NO PDF)
        nomes_colunas = {
            "produto": "Produto",
            "unidade": "Unidade",
            "kg": "Kg",
            "preco_min": "Preço Mín",
            "preco_max": "Preço Máx",
            "preco_medio": "Preço Médio",
            "valor_kg": "Valor/Kg"
        }

        dados_classe = dados_classe.rename(columns=nomes_colunas)

        # 🔹 FORMATA NÚMEROS
        cols_num = dados_classe.select_dtypes(include="number").columns
        
        for col in cols_num:
        
            # Kg inteiro, sem casas decimais
            if col == "Kg":
                dados_classe[col] = dados_classe[col].map(
                    lambda x: f"{int(x)}" if pd.notnull(x) else ""
                )
        
            # Preços e valores com duas casas decimais
            else:
                dados_classe[col] = dados_classe[col].map(
                    lambda x: f"{float(x):.2f}".replace(".", ",") if pd.notnull(x) else ""
                )

        # -------- CABEÇALHO -------- #
        try:
            from reportlab.platypus import Image
            logo = Image("logo.png", width=60, height=40)
            elementos.append(logo)
        except:
            pass  # se não encontrar o logo, não quebra o sistema

        from reportlab.lib.enums import TA_CENTER

        # Estilos centralizados
        estilo_titulo = styles["Title"].clone('titulo_centro')
        estilo_titulo.alignment = TA_CENTER
        estilo_titulo.fontSize = 14   # título principal
        estilo_titulo.leading = 12
        estilo_titulo.spaceAfter = 4
        estilo_titulo.spaceBefore = 6

        estilo_sub = styles["Italic"].clone('sub_centro')
        estilo_sub.alignment = TA_CENTER
        estilo_sub.fontSize = 8   # título principal
        estilo_sub.leading = 8  # padrão é maior → diminui aqui
        estilo_sub.spaceAfter = 2
        estilo_sub.spaceBefore = 0

        # -------- TÍTULOS CENTRALIZADOS -------- #
        elementos.append(Paragraph("AMA - Autarquia Municipal de Abastecimento", estilo_sub))
        elementos.append(Paragraph("Diretor Executivo: Celso Candido Almeida Leal", estilo_sub))
        elementos.append(Paragraph("Relatório de Cotação de Preços", estilo_titulo))
        elementos.append(Spacer(1, 6))

        # -------- CLASSE E DATA LADO A LADO -------- #

        # 🔹 DATA DE EMISSÃO (momento do PDF)
        data_emissao = datetime.now().strftime('%d/%m/%Y')

        # 🔹 LINHA DE INFORMAÇÕES
        info_dados = [[
            f"Classe: {c}",
            f"Data de Cotação: {data_cotacao}",
            f"Data de emissão: {data_emissao}"
        ]]

        info_tabela = Table(info_dados, colWidths=[145, 145, 145]) # criação da tabela e definição da largura das colunas
        info_tabela.setStyle([
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),

            # 🔹 REMOVE NEGRITO
            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),

            # 🔹 FONTE MENOR
            ("FONTSIZE", (0,0), (-1,-1), 7),

            # 🔹 MENOS ESPAÇO (mais compacto)
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ])

        elementos.append(info_tabela)
        elementos.append(Spacer(1, 6))

         # 🔹 REMOVE DATA DA TABELA (para não aparecer na tabela)
        if "data" in dados_classe.columns:
            dados_classe = dados_classe.drop(columns=["data"])

        # -------- TABELA -------- #
        tabela_dados = [list(dados_classe.columns)] + dados_classe.values.tolist()

        tabela = Table(
            tabela_dados,
            colWidths=[120, 40, 30, 50, 50, 60, 50], # largura da tabela
            rowHeights=11, # altura da tabela
            repeatRows=1
        )

        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1F4E79")),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),

            # 🔹 ALINHAMENTO HORIZONTAL
            ('ALIGN', (0,0), (-1,0), 'CENTER'),     # cabeçalho
            ('ALIGN', (0,1), (1,-1), 'LEFT'),       # produto
            ('ALIGN', (2,1), (-1,-1), 'RIGHT'),     # números

            # 🔹 ALINHAMENTO VERTICAL (UMA ÚNICA REGRA)
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),

            ('FONTNAME', (0,0),(-1,0),'Helvetica-Bold'),

            # LLINHAS FINAS
            ('GRID', (0,0), (-1,-1), 0.1, colors.grey),
            
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [
                colors.whitesmoke,
                colors.HexColor("#E8E8E8")
            ]),

            # 🔹 MELHORIA DE ESPAÇAMENTO (opcional, mas recomendado)
            ('LEFTPADDING', (0,0), (-1,-1), 2),
            ('RIGHTPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            
            # tamanho da fonte
            ('FONTSIZE', (0,0), (-1,0), 8),
            ('FONTSIZE', (0,1), (-1,-1), 7), 
        ]))

        tabela.hAlign = 'CENTER'

        elementos.append(tabela)
        elementos.append(Spacer(1, 8))

        # -------- RODAPÉ -------- #
        elementos.append(Paragraph("Grace Kelly Rodrigues da Silva Santos", estilo_sub))
        elementos.append(Paragraph("Supervisor de Estatística, Pesquisa e Controle de Qualidade", estilo_sub))

        # Nova página para próxima classe
        if i < len(classes) - 1:
            elementos.append(PageBreak())

    # 🔥 PROTEÇÃO: evita PDF vazio
    if not elementos:
        elementos.append(Paragraph(
            "Nenhum dado disponível para gerar o relatório.",
            styles["Normal"]
        ))
    
    doc.build(
        elementos,
        onFirstPage=adicionar_numero_pagina,
        onLaterPages=adicionar_numero_pagina
    )
# ====================================================

# ================== GERAR PDF SOBRE OS PRODUTOS =========================
def gerar_pdf_sobre_produtos(df, nome_pdf):

    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.styles import ParagraphStyle
    from xml.sax.saxutils import escape

    doc = SimpleDocTemplate(
        nome_pdf,
        pagesize=A4,
        leftMargin=25,
        rightMargin=25,
        topMargin=25,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    elementos = []

    estilo_titulo = styles["Title"].clone("titulo_sobre_produtos")
    estilo_titulo.alignment = TA_CENTER
    estilo_titulo.fontSize = 16
    estilo_titulo.spaceAfter = 12

    estilo_subtitulo = styles["Heading2"].clone("subtitulo_produto")
    estilo_subtitulo.fontSize = 11
    estilo_subtitulo.spaceBefore = 8
    estilo_subtitulo.spaceAfter = 4

    estilo_normal = styles["Normal"].clone("normal_sobre_produtos")
    estilo_normal.fontSize = 9
    estilo_normal.leading = 12
    estilo_normal.alignment = TA_LEFT

    estilo_info = ParagraphStyle(
        "info_produto",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.grey
    )

    elementos.append(Paragraph("Sobre os Produtos", estilo_titulo))
    elementos.append(Spacer(1, 8))

    data_emissao = datetime.now().strftime("%d/%m/%Y %H:%M")
    elementos.append(Paragraph(f"Data de emissão: {data_emissao}", estilo_info))
    elementos.append(Spacer(1, 12))

    if df.empty:
        elementos.append(Paragraph("Nenhuma informação encontrada.", estilo_normal))
    else:
        for _, row in df.iterrows():

            produto = escape(str(row.get("produto", "")))
            classe = escape(str(row.get("classe", "")))
            informacoes = escape(str(row.get("informacoes", ""))).replace("\n", "<br/>")
            atualizado_por = escape(str(row.get("atualizado_por", "")))
            nivel_usuario = escape(str(row.get("nivel_usuario", "")))
            hora = escape(str(row.get("hora_atualizacao", "")))

            data_txt = ""
            if "data_atualizacao" in row and pd.notnull(row.get("data_atualizacao")):
                try:
                    data_txt = pd.to_datetime(row.get("data_atualizacao")).strftime("%d/%m/%Y")
                except:
                    data_txt = ""

            elementos.append(Paragraph(f"Produto: {produto}", estilo_subtitulo))
            elementos.append(Paragraph(f"<b>Classe:</b> {classe}", estilo_normal))
            elementos.append(Spacer(1, 4))
            elementos.append(Paragraph(f"<b>Informações:</b><br/>{informacoes}", estilo_normal))
            elementos.append(Spacer(1, 4))

            elementos.append(
                Paragraph(
                    f"Atualizado por: {atualizado_por} ({nivel_usuario}) | Data: {data_txt} | Hora: {hora}",
                    estilo_info
                )
            )

            elementos.append(Spacer(1, 10))

    doc.build(
        elementos,
        onFirstPage=adicionar_numero_pagina,
        onLaterPages=adicionar_numero_pagina
    )
# =============================================================================



# ================== GERAR PDF ANALÍTICO DE PREÇOS =========================
def gerar_pdf_analise_precos(
    comparativo,
    alertas,
    media_mensal,
    df_periodo,
    observacoes,
    nome_pdf,
    data_inicial,
    data_final,
    classe_sel,
    produto_sel,
    volume_mensal=None,
    resumo_volume_classe=None,
    resumo_volume_geral=None,
    ajuste_volume_mensal_percentual=0.0,
    sensibilidade_preco=0.01,
    kg_por_caminhao=15000
):
    
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.styles import ParagraphStyle
    from xml.sax.saxutils import escape

    import os
    import tempfile
    import matplotlib.pyplot as plt
    from reportlab.platypus import Image

    doc = SimpleDocTemplate(
        nome_pdf,
        pagesize=A4,
        leftMargin=25,
        rightMargin=25,
        topMargin=25,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    elementos = []

    FONTE_CORPO = 12
    FONTE_TABELA = 9

    # ================= ESTILOS =================
    estilo_titulo = styles["Title"].clone("titulo_analise_precos")
    estilo_titulo.alignment = TA_CENTER
    estilo_titulo.fontSize = 16
    estilo_titulo.spaceAfter = 10

    estilo_subtitulo = styles["Heading2"].clone("subtitulo_analise_precos")
    estilo_subtitulo.fontSize = 12
    estilo_subtitulo.spaceBefore = 10
    estilo_subtitulo.spaceAfter = 6

    estilo_normal = styles["Normal"].clone("normal_analise_precos")
    estilo_normal.fontSize = FONTE_CORPO
    estilo_normal.leading = FONTE_CORPO + 4
    estilo_normal.alignment = TA_LEFT

    estilo_info = ParagraphStyle(
        "info_analise_precos",
        parent=styles["Normal"],
        fontSize=10,
        leading=12,
        textColor=colors.grey
    )

    estilo_celula_tabela = ParagraphStyle(
        "celula_tabela_analise",
        parent=styles["Normal"],
        fontSize=FONTE_TABELA,
        leading=FONTE_TABELA + 2,
        alignment=TA_LEFT
    )

    estilo_celula_tabela_menor = ParagraphStyle(
        "celula_tabela_analise_menor",
        parent=styles["Normal"],
        fontSize=FONTE_TABELA,
        leading=FONTE_TABELA + 2,
        alignment=TA_LEFT
    )

    # Estilos específicos das tabelas de volume: nomes mais legíveis e valores mais compactos.
    estilo_produto_volume = ParagraphStyle(
        "produto_volume",
        parent=styles["Normal"],
        fontSize=9.4,
        leading=10.8,
        alignment=TA_LEFT
    )

    estilo_classe_volume = ParagraphStyle(
        "classe_volume",
        parent=styles["Normal"],
        fontSize=10,
        leading=12,
        alignment=TA_LEFT
    )

    estilo_valor_volume = ParagraphStyle(
        "valor_volume",
        parent=styles["Normal"],
        fontSize=7.4,
        leading=8.6,
        alignment=TA_LEFT
    )

    estilo_cabecalho_tabela = ParagraphStyle(
        "cabecalho_tabela",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=FONTE_TABELA,
        leading=FONTE_TABELA + 1,
        alignment=TA_CENTER,
        textColor=colors.white
    )
    # ================= FUNÇÕES AUXILIARES =================
    def moeda(valor):
        try:
            return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "R$ 0,00"

    def percentual(valor):
        try:
            return f"{float(valor):.2f}%".replace(".", ",")
        except Exception:
            return "0,00%"

    def numero(valor, casas=2):
        try:
            return f"{float(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "0,00"

    def kg(valor):
        try:
            return f"{float(valor):,.2f} kg".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "0,00 kg"

    def texto_seguro(valor):
        return escape(str(valor))

    def celula_pdf(valor, estilo=None):
        return Paragraph(escape(str(valor)), estilo or estilo_celula_tabela)

    def cabecalho_pdf(valor):
        texto = escape(str(valor)).replace("\n", "<br/>")
        return Paragraph(texto, estilo_cabecalho_tabela)

    def criar_tabela(dados, larguras=None, fonte=FONTE_TABELA):
        tabela = Table(dados, colWidths=larguras, repeatRows=1)

        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),

            ("FONTSIZE", (0, 0), (-1, 0), fonte),
            ("FONTSIZE", (0, 1), (-1, -1), fonte),

            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),

            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.whitesmoke,
                colors.HexColor("#E8E8E8")
            ]),

            ("LEFTPADDING", (0, 0), (-1, -1), 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))

        return tabela
    #=====

    def gerar_grafico_ranking(df_ranking, titulo, nome_coluna_valor="variacao_percentual"):
        if df_ranking is None or df_ranking.empty:
            return None

        try:
            temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
            caminho = temp.name
            temp.close()

            df_plot = df_ranking.copy()

            df_plot = df_plot.sort_values(nome_coluna_valor, ascending=True)

            fig, ax = plt.subplots(figsize=(7, 3.2))

            ax.barh(
                df_plot["produto"].astype(str),
                df_plot[nome_coluna_valor].astype(float)
            )

            ax.set_title(titulo)
            ax.set_xlabel("Variação (%)")
            ax.grid(axis="x", alpha=0.3)

            fig.tight_layout()
            fig.savefig(caminho, dpi=180)
            plt.close(fig)

            return caminho

        except Exception:
            return None
    #==========================================

    def criar_legenda_variacao_pdf():
        dados_legenda = [
            ["Variação", "Classificação"],
            ["Acima de 60%", "Alta crítica"],
            ["De 30% a 59,99%", "Alta acentuada"],
            ["De 10% a 29,99%", "Alta moderada"],
            ["De -10% a -29,99%", "Queda relevante"],
            ["Abaixo de -30%", "Queda acentuada"],
            ["Entre -9,99% e 9,99%", "Variação normal"]
        ]

        tabela_legenda = criar_tabela(
            dados_legenda,
            larguras=[170, 170],
            fonte=FONTE_TABELA
        )

        tabela_legenda.hAlign = "CENTER"

        return tabela_legenda

    # ================= CABEÇALHO =================
    elementos.append(Paragraph("Relatório Analítico de Preços", estilo_titulo))
    elementos.append(Paragraph("AMA - Autarquia Municipal de Abastecimento", estilo_info))

    data_emissao = datetime.now().strftime("%d/%m/%Y %H:%M")

    elementos.append(Paragraph(f"Data de emissão: {data_emissao}", estilo_info))

    periodo_selecionado = (
        f"{data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}"
    )
    elementos.append(Paragraph(
        f"<b>Período selecionado:</b> {periodo_selecionado}",
        estilo_info
    ))

    elementos.append(Spacer(1, 10))

    # ================= FILTROS =================
    elementos.append(Paragraph("1. Filtros utilizados", estilo_subtitulo))

    filtros_dados = [
        ["Período", f"{data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}"],
        ["Classe", str(classe_sel)],
        ["Produto selecionado", str(produto_sel)]
    ]

    elementos.append(criar_tabela(filtros_dados, larguras=[120, 360], fonte=FONTE_TABELA))
    elementos.append(Spacer(1, 10))

    # ================= RESUMO =================
    elementos.append(Paragraph("2. Resumo do período", estilo_subtitulo))

    total_produtos = df_periodo["produto"].nunique() if "produto" in df_periodo.columns else 0
    total_registros = len(df_periodo)

    preco_medio_geral = 0
    valor_kg_medio = 0

    if not df_periodo.empty:
        if "preco_medio" in df_periodo.columns:
            preco_medio_geral = df_periodo["preco_medio"].mean()

        if "valor_kg" in df_periodo.columns:
            valor_kg_medio = df_periodo["valor_kg"].mean()

    resumo_dados = [
        ["Indicador", "Resultado"],
        ["Produtos analisados", total_produtos],
        ["Registros de cotação", total_registros],
        ["Preço médio geral", moeda(preco_medio_geral)],
        ["Valor/kg médio", moeda(valor_kg_medio)]
    ]

    elementos.append(criar_tabela(resumo_dados, larguras=[220, 260], fonte=FONTE_TABELA))
    elementos.append(Spacer(1, 10))

    # ================= SÍNTESE EXECUTIVA =================
    elementos.append(Paragraph("3. Síntese executiva", estilo_subtitulo))

    dados_sintese = [
        ["Indicador", "Resultado"],
        ["Produtos analisados", total_produtos],
        ["Registros de cotação", total_registros]
    ]

    if comparativo is not None and not comparativo.empty:
        maior_alta_sintese = comparativo.sort_values("variacao_percentual", ascending=False).iloc[0]
        maior_queda_sintese = comparativo.sort_values("variacao_percentual", ascending=True).iloc[0]

        dados_sintese.extend([
            ["Maior alta", f"{maior_alta_sintese.get('produto', '')} ({percentual(maior_alta_sintese.get('variacao_percentual', 0))})"],
            ["Maior queda", f"{maior_queda_sintese.get('produto', '')} ({percentual(maior_queda_sintese.get('variacao_percentual', 0))})"]
        ])

    total_alertas_sintese = 0 if alertas is None or alertas.empty else len(alertas)
    dados_sintese.append(["Alertas de variação", total_alertas_sintese])

    if resumo_volume_geral is not None and not resumo_volume_geral.empty:
        rg_sintese = resumo_volume_geral.iloc[0]
        dados_sintese.extend([
            ["Volume atual estimado", kg(rg_sintese.get("Volume total estimado (kg)", 0))],
            ["Variação do volume", percentual(rg_sintese.get("Variação volume (%)", 0))],
            ["Valor comercializado estimado", moeda(rg_sintese.get("Valor comercializado estimado", 0))],
            ["Crescimento em valor", percentual(rg_sintese.get("Crescimento valor (%)", 0))]
        ])

    elementos.append(criar_tabela(dados_sintese, larguras=[220, 260], fonte=FONTE_TABELA))
    elementos.append(Spacer(1, 10))

    # ================= INTERPRETAÇÃO AUTOMÁTICA =================
    elementos.append(Paragraph("4. Interpretação automática", estilo_subtitulo))

    if comparativo.empty:
        texto_interpretativo = (
            "Não há dados suficientes para identificar variações de preço no período selecionado."
        )
    else:
        maior_alta = comparativo.sort_values(
            "variacao_percentual",
            ascending=False
        ).iloc[0]

        maior_queda = comparativo.sort_values(
            "variacao_percentual",
            ascending=True
        ).iloc[0]

        texto_interpretativo = (
            f"No período analisado, o produto com maior alta foi "
            f"{maior_alta['produto']}, com variação de "
            f"{percentual(maior_alta['variacao_percentual'])}, passando de "
            f"{moeda(maior_alta['preco_medio_inicial'])} para "
            f"{moeda(maior_alta['preco_medio_final'])}. "
            f"O produto com maior queda foi {maior_queda['produto']}, com variação de "
            f"{percentual(maior_queda['variacao_percentual'])}, passando de "
            f"{moeda(maior_queda['preco_medio_inicial'])} para "
            f"{moeda(maior_queda['preco_medio_final'])}. "
        )

        if not alertas.empty:
            texto_interpretativo += (
                f"Foram identificados {len(alertas)} alerta(s) de variação relevante. "
                "Esses produtos devem ser avaliados com atenção, pois podem indicar "
                "mudanças de oferta, sazonalidade, aumento de custos, diferença de qualidade "
                "ou possível erro de digitação."
            )
        else:
            texto_interpretativo += (
                "Não foram identificadas variações críticas no período selecionado."
            )

    elementos.append(Paragraph(texto_seguro(texto_interpretativo), estilo_normal))
    elementos.append(Spacer(1, 10))

    # ================= ALERTAS =================
    elementos.append(Paragraph("5. Alertas de variação", estilo_subtitulo))

    elementos.append(Paragraph("Legenda de classificação das variações", estilo_normal))
    elementos.append(criar_legenda_variacao_pdf())
    elementos.append(Spacer(1, 10))

    if alertas.empty:
        elementos.append(Paragraph("Nenhum alerta relevante encontrado no período.", estilo_normal))
    else:
        alertas_pdf = alertas.copy()

        dados_alertas = [[
            "Produto",
            "Classe",
            "Preço inicial",
            "Preço final",
            "Variação",
            "Alerta"
        ]]

        def alerta_sem_emoji(valor):
            valor = str(valor)

            valor = valor.replace("🚨", "")
            valor = valor.replace("⚠️", "")
            valor = valor.replace("🟡", "")
            valor = valor.replace("📉", "")
            valor = valor.replace("🔵", "")
            valor = valor.replace("✅", "")

            return valor.strip()

        for _, row in alertas_pdf.iterrows():
            dados_alertas.append([
                str(row.get("produto", "")),
                str(row.get("classe", "")),
                moeda(row.get("preco_medio_inicial", 0)),
                moeda(row.get("preco_medio_final", 0)),
                percentual(row.get("variacao_percentual", 0)),
                alerta_sem_emoji(row.get("alerta", ""))
            ])

        elementos.append(
            criar_tabela(
                dados_alertas,
                larguras=[155, 55, 65, 65, 55, 95],
                fonte=FONTE_TABELA
            )
        )

    elementos.append(Spacer(1, 10))
    #======================

    # ================= OBSERVAÇÕES REGISTRADAS =================
    elementos.append(Spacer(1, 10))
    elementos.append(Paragraph("6. Observações registradas no período", estilo_subtitulo))

    if observacoes is None or observacoes.empty:
        elementos.append(Paragraph(
            "Nenhuma observação foi registrada para o período analisado.",
            estilo_normal
        ))
    else:
        obs_pdf = observacoes.copy()

        if "data_ref" in obs_pdf.columns:
            obs_pdf["data_ref"] = pd.to_datetime(
                obs_pdf["data_ref"],
                errors="coerce"
            )

        # limita para não ficar PDF enorme
        obs_pdf = obs_pdf.head(30)

        for _, row in obs_pdf.iterrows():
            data_txt = ""

            if "data_ref" in row and pd.notnull(row.get("data_ref")):
                data_txt = row["data_ref"].strftime("%d/%m/%Y")

            produto = escape(str(row.get("produto", "")))
            classe = escape(str(row.get("classe", "")))
            observacao = escape(str(row.get("observacao", ""))).replace("\n", "<br/>")
            criado_por = escape(str(row.get("criado_por", "")))

            elementos.append(Paragraph(
                f"<b>{data_txt} - {produto}</b> ({classe})",
                estilo_normal
            ))

            elementos.append(Paragraph(
                observacao,
                estilo_normal
            ))

            if criado_por:
                elementos.append(Paragraph(
                    f"Registrado por: {criado_por}",
                    estilo_info
                ))

            elementos.append(Spacer(1, 6))

        if len(observacoes) > 30:
            elementos.append(Paragraph(
                f"Observação: foram exibidas as 30 primeiras observações de um total de {len(observacoes)}.",
                estilo_info
            ))
    #==============================

    # ================= RANKINGS =================
    elementos.append(Paragraph("7. Ranking de maiores altas", estilo_subtitulo))

    ranking_altas = comparativo[
        comparativo["variacao_percentual"] > 0
    ].sort_values("variacao_percentual", ascending=False).head(10)

    if ranking_altas.empty:
        elementos.append(Paragraph("Nenhum produto com alta no período.", estilo_normal))
    else:
        caminho_grafico_altas = gerar_grafico_ranking(
            ranking_altas,
            "Ranking de maiores altas"
        )

        if caminho_grafico_altas:
            elementos.append(Image(caminho_grafico_altas, width=480, height=220))
            elementos.append(Spacer(1, 8))

        dados_altas = [["Produto", "Preço inicial", "Preço final", "Variação"]]

        for _, row in ranking_altas.iterrows():
            dados_altas.append([
                str(row.get("produto", "")),
                moeda(row.get("preco_medio_inicial", 0)),
                moeda(row.get("preco_medio_final", 0)),
                percentual(row.get("variacao_percentual", 0))
            ])

        elementos.append(
           criar_tabela(
                dados_altas,
                larguras=[180, 95, 95, 80],
                fonte=FONTE_TABELA
            )
        )

    elementos.append(PageBreak())

    elementos.append(Paragraph("8. Ranking de maiores quedas", estilo_subtitulo))

    ranking_quedas = comparativo[
        comparativo["variacao_percentual"] < 0
    ].sort_values("variacao_percentual", ascending=True).head(10)

    if ranking_quedas.empty:
        elementos.append(Paragraph("Nenhum produto com queda no período.", estilo_normal))
    else:
        caminho_grafico_quedas = gerar_grafico_ranking(
            ranking_quedas,
            "Ranking de maiores quedas"
        )

        if caminho_grafico_quedas:
            elementos.append(Image(caminho_grafico_quedas, width=480, height=220))
            elementos.append(Spacer(1, 8))

        dados_quedas = [["Produto", "Preço inicial", "Preço final", "Variação"]]

        for _, row in ranking_quedas.iterrows():
            dados_quedas.append([
                str(row.get("produto", "")),
                moeda(row.get("preco_medio_inicial", 0)),
                moeda(row.get("preco_medio_final", 0)),
                percentual(row.get("variacao_percentual", 0))
            ])

        elementos.append(
            criar_tabela(
                dados_quedas,
                larguras=[180, 95, 95, 80],
                fonte=FONTE_TABELA
            )
        )

    #elementos.append(PageBreak())

    # ================= MÉDIA MENSAL =================
    elementos.append(Paragraph("9. Média mensal dos preços", estilo_subtitulo))

    if media_mensal.empty:
        elementos.append(Paragraph("Nenhuma média mensal encontrada.", estilo_normal))
    else:
        media_pdf = media_mensal.copy()

        dados_media = [[
            "Classe",
            "Produto",
            "Unid.",
            "Kg",
            "Preço mín.",
            "Preço máx.",
            "Preço médio",
            "Valor/kg"
        ]]

        for _, row in media_pdf.iterrows():
            dados_media.append([
                celula_pdf(row.get("classe", ""), estilo_celula_tabela_menor),
                celula_pdf(row.get("produto", ""), estilo_celula_tabela_menor),
                str(row.get("unidade", "")),
                f"{float(row.get('kg', 0)):.0f}" if pd.notnull(row.get("kg", 0)) else "",
                moeda(row.get("preco_min", 0)),
                moeda(row.get("preco_max", 0)),
                moeda(row.get("preco_medio", 0)),
                moeda(row.get("valor_kg", 0))
            ])

        elementos.append(
                criar_tabela(
                    dados_media,
                    larguras=[60, 210, 28, 32, 52, 52, 60, 51],
                    fonte=FONTE_TABELA
                )
            )

    elementos.append(Spacer(1, 12))

    # A seção de volume começa em nova página para ganhar destaque e facilitar a leitura.
    elementos.append(PageBreak())

    # ================= VOLUME MENSAL ESTIMADO =================
    elementos.append(Paragraph("10. Volume mensal estimado e valor comercializado", estilo_subtitulo))

    if volume_mensal is None or volume_mensal.empty:
        elementos.append(Paragraph(
            "Nenhuma análise de volume mensal foi gerada para os filtros selecionados.",
            estilo_normal
        ))
    else:
        texto_volume = (
            "A análise de volume utiliza o volume do mesmo mês do ano anterior como base, "
            "aplica o ajuste mensal informado na tela e considera a variação do preço/kg médio "
            "para estimar a quantidade atual. O valor comercializado é calculado pela multiplicação "
            "entre a quantidade estimada e o preço/kg médio do mês atual."
        )
        elementos.append(Paragraph(texto_volume, estilo_normal))
        elementos.append(Spacer(1, 6))

        parametros_volume = [
            ["Parâmetro", "Valor"],
            ["Ajuste mensal do volume", percentual(ajuste_volume_mensal_percentual)],
            ["Sensibilidade ao preço", numero(sensibilidade_preco, 4)],
            ["Kg por caminhão", f"{float(kg_por_caminhao):,.0f} kg".replace(",", ".")]
        ]

        elementos.append(criar_tabela(parametros_volume, larguras=[220, 260], fonte=FONTE_TABELA))
        elementos.append(Spacer(1, 8))

        volume_pdf = volume_mensal.copy()

        # Garante que os campos numéricos estejam como número para os totais e comparações.
        for coluna in [
            "Quantidade ano anterior (kg)",
            "Quantidade (kg)",
            "Porcentagem (%)",
            "Caminhões",
            "Preço/kg ano anterior",
            "Preço/kg médio",
            "Variação preço (%)",
            "Valor ano anterior",
            "Valor comercializado",
            "Variação volume (%)"
        ]:
            if coluna in volume_pdf.columns:
                volume_pdf[coluna] = pd.to_numeric(volume_pdf[coluna], errors="coerce").fillna(0)

        # -------- Resumo geral --------
        if resumo_volume_geral is not None and not resumo_volume_geral.empty:
            rg = resumo_volume_geral.iloc[0]

            volume_anterior_total = float(rg.get("Volume ano anterior (kg)", volume_pdf.get("Quantidade ano anterior (kg)", pd.Series(dtype=float)).sum() if "Quantidade ano anterior (kg)" in volume_pdf.columns else 0))
            volume_atual_total = float(rg.get("Volume total estimado (kg)", volume_pdf.get("Quantidade (kg)", pd.Series(dtype=float)).sum() if "Quantidade (kg)" in volume_pdf.columns else 0))
            diferenca_volume_total = volume_atual_total - volume_anterior_total

            valor_anterior_total = float(rg.get("Valor ano anterior", volume_pdf.get("Valor ano anterior", pd.Series(dtype=float)).sum() if "Valor ano anterior" in volume_pdf.columns else 0))
            valor_atual_total = float(rg.get("Valor comercializado estimado", volume_pdf.get("Valor comercializado", pd.Series(dtype=float)).sum() if "Valor comercializado" in volume_pdf.columns else 0))
            diferenca_valor_total = valor_atual_total - valor_anterior_total

            variacao_volume_total = (
                (volume_atual_total / volume_anterior_total) - 1
            ) * 100 if volume_anterior_total > 0 else 0

            crescimento_valor_total = (
                (valor_atual_total / valor_anterior_total) - 1
            ) * 100 if valor_anterior_total > 0 else 0

            dados_resumo_volume = [
                ["Indicador", "Resultado"],
                ["Volume ano anterior", kg(volume_anterior_total)],
                ["Volume atual estimado", kg(volume_atual_total)],
                ["Diferença de volume", kg(diferenca_volume_total)],
                ["Variação do volume", percentual(variacao_volume_total)],
                ["Caminhões estimados", numero(rg.get("Caminhões estimados", 0), 2)],
                ["Valor ano anterior", moeda(valor_anterior_total)],
                ["Valor comercializado estimado", moeda(valor_atual_total)],
                ["Diferença de valor", moeda(diferenca_valor_total)],
                ["Crescimento do valor", percentual(crescimento_valor_total)]
            ]

            elementos.append(Paragraph("Resumo geral do volume", estilo_normal))
            elementos.append(criar_tabela(dados_resumo_volume, larguras=[220, 260], fonte=FONTE_TABELA))
            elementos.append(Spacer(1, 8))

        # -------- Total por classe --------
        if resumo_volume_classe is not None and not resumo_volume_classe.empty:
            elementos.append(Paragraph("Total por classe", estilo_normal))

            classe_pdf = resumo_volume_classe.copy()
            for coluna in [
                "Quantidade ano anterior (kg)",
                "Quantidade (kg)",
                "Caminhões",
                "Valor ano anterior",
                "Valor comercializado",
                "Variação volume (%)",
                "Crescimento valor (%)"
            ]:
                if coluna in classe_pdf.columns:
                    classe_pdf[coluna] = pd.to_numeric(classe_pdf[coluna], errors="coerce").fillna(0)

            # Se vier de uma versão antiga sem variação de volume, calcula aqui.
            if "Variação volume (%)" not in classe_pdf.columns and {"Quantidade ano anterior (kg)", "Quantidade (kg)"}.issubset(classe_pdf.columns):
                classe_pdf["Variação volume (%)"] = classe_pdf.apply(
                    lambda r: ((r["Quantidade (kg)"] / r["Quantidade ano anterior (kg)"]) - 1) * 100
                    if r["Quantidade ano anterior (kg)"] > 0 else 0,
                    axis=1
                )

            dados_classe = [[
                "Classe",
                "Qtd. ant.",
                "Qtd. atual",
                "Var. vol.",
                "Caminh.",
                "Valor ant.",
                "Valor atual",
                "Cresc. valor"
            ]]

            for _, row in classe_pdf.iterrows():
                dados_classe.append([
                    celula_pdf(row.get("Classe", ""), estilo_classe_volume),
                    celula_pdf(numero(row.get("Quantidade ano anterior (kg)", 0), 0), estilo_valor_volume),
                    celula_pdf(numero(row.get("Quantidade (kg)", 0), 0), estilo_valor_volume),
                    celula_pdf(percentual(row.get("Variação volume (%)", 0)), estilo_valor_volume),
                    celula_pdf(numero(row.get("Caminhões", 0), 1), estilo_valor_volume),
                    celula_pdf(moeda(row.get("Valor ano anterior", 0)), estilo_valor_volume),
                    celula_pdf(moeda(row.get("Valor comercializado", 0)), estilo_valor_volume),
                    celula_pdf(percentual(row.get("Crescimento valor (%)", 0)), estilo_valor_volume)
                ])

            elementos.append(criar_tabela(
                dados_classe,
                larguras=[82, 58, 58, 43, 43, 73, 73, 55],
                fonte=FONTE_TABELA
            ))
            elementos.append(Spacer(1, 8))

        # -------- Tabela completa por produto --------
        if not volume_pdf.empty:
            elementos.append(Paragraph("Tabela completa de volume por produto", estilo_normal))

            dados_volume = [[
                cabecalho_pdf("Produto"),
                cabecalho_pdf("Qtd. ano\nant."),
                cabecalho_pdf("Qtd.\natual"),
                cabecalho_pdf("Var.\nvol."),
                cabecalho_pdf("R$/kg\nant."),
                cabecalho_pdf("R$/kg\natual"),
                cabecalho_pdf("Var.\npreço"),
                cabecalho_pdf("Valor\nant."),
                cabecalho_pdf("Valor\natual")
            ]]

            for _, row in volume_pdf.iterrows():
                dados_volume.append([
                    celula_pdf(row.get("Produto", ""), estilo_produto_volume),
                    celula_pdf(numero(row.get("Quantidade ano anterior (kg)", 0), 0), estilo_valor_volume),
                    celula_pdf(numero(row.get("Quantidade (kg)", 0), 0), estilo_valor_volume),
                    celula_pdf(percentual(row.get("Variação volume (%)", 0)), estilo_valor_volume),
                    celula_pdf(moeda(row.get("Preço/kg ano anterior", 0)).replace("R$ ", ""), estilo_valor_volume),
                    celula_pdf(moeda(row.get("Preço/kg médio", 0)).replace("R$ ", ""), estilo_valor_volume),
                    celula_pdf(percentual(row.get("Variação preço (%)", 0)), estilo_valor_volume),
                    celula_pdf(moeda(row.get("Valor ano anterior", 0)).replace("R$ ", ""), estilo_valor_volume),
                    celula_pdf(moeda(row.get("Valor comercializado", 0)).replace("R$ ", ""), estilo_valor_volume)
                ])

            elementos.append(criar_tabela(
                dados_volume,
                larguras=[132, 52, 52, 42, 48, 50, 44, 61, 61],
                fonte=FONTE_TABELA
            ))
            elementos.append(Spacer(1, 8))

        # -------- Comparação final com o ano anterior --------
        elementos.append(Paragraph("Comparação final com o ano anterior", estilo_subtitulo))

        volume_anterior_total = volume_pdf["Quantidade ano anterior (kg)"].sum() if "Quantidade ano anterior (kg)" in volume_pdf.columns else 0
        volume_atual_total = volume_pdf["Quantidade (kg)"].sum() if "Quantidade (kg)" in volume_pdf.columns else 0
        dif_volume_total = volume_atual_total - volume_anterior_total
        var_volume_total = ((volume_atual_total / volume_anterior_total) - 1) * 100 if volume_anterior_total > 0 else 0

        valor_anterior_total = volume_pdf["Valor ano anterior"].sum() if "Valor ano anterior" in volume_pdf.columns else 0
        valor_atual_total = volume_pdf["Valor comercializado"].sum() if "Valor comercializado" in volume_pdf.columns else 0
        dif_valor_total = valor_atual_total - valor_anterior_total
        var_valor_total = ((valor_atual_total / valor_anterior_total) - 1) * 100 if valor_anterior_total > 0 else 0

        comparacao_geral = [
            ["Indicador", "Ano anterior", "Ano atual estimado", "Diferença", "Variação"],
            [
                "Volume total",
                kg(volume_anterior_total),
                kg(volume_atual_total),
                kg(dif_volume_total),
                percentual(var_volume_total)
            ],
            [
                "Valor comercializado",
                moeda(valor_anterior_total),
                moeda(valor_atual_total),
                moeda(dif_valor_total),
                percentual(var_valor_total)
            ]
        ]

        elementos.append(criar_tabela(
            comparacao_geral,
            larguras=[105, 105, 115, 105, 60],
            fonte=FONTE_TABELA
        ))
        elementos.append(Spacer(1, 8))

        if resumo_volume_classe is not None and not resumo_volume_classe.empty:
            elementos.append(Paragraph("Comparação por classe", estilo_normal))

            classe_comp = resumo_volume_classe.copy()
            for coluna in [
                "Quantidade ano anterior (kg)",
                "Quantidade (kg)",
                "Valor ano anterior",
                "Valor comercializado"
            ]:
                if coluna in classe_comp.columns:
                    classe_comp[coluna] = pd.to_numeric(classe_comp[coluna], errors="coerce").fillna(0)

            dados_comp_classe = [[
                "Classe",
                "Dif. volume",
                "Var. volume",
                "Dif. valor",
                "Var. valor"
            ]]

            for _, row in classe_comp.iterrows():
                qtd_ant = row.get("Quantidade ano anterior (kg)", 0)
                qtd_atual = row.get("Quantidade (kg)", 0)
                val_ant = row.get("Valor ano anterior", 0)
                val_atual = row.get("Valor comercializado", 0)

                dif_qtd = qtd_atual - qtd_ant
                var_qtd = ((qtd_atual / qtd_ant) - 1) * 100 if qtd_ant > 0 else 0
                dif_val = val_atual - val_ant
                var_val = ((val_atual / val_ant) - 1) * 100 if val_ant > 0 else 0

                dados_comp_classe.append([
                    celula_pdf(row.get("Classe", ""), estilo_classe_volume),
                    kg(dif_qtd),
                    percentual(var_qtd),
                    moeda(dif_val),
                    percentual(var_val)
                ])

            elementos.append(criar_tabela(
                dados_comp_classe,
                larguras=[95, 110, 70, 120, 70],
                fonte=FONTE_TABELA
            ))
            elementos.append(Spacer(1, 8))

        # -------- Interpretação final do volume --------
        situacao_volume = "crescimento" if var_volume_total >= 0 else "queda"
        situacao_valor = "crescimento" if var_valor_total >= 0 else "queda"
        comparacao_intensidade = (
            "superior" if abs(var_valor_total) > abs(var_volume_total) else "inferior"
        )

        texto_interpretacao_volume = (
            f"Em comparação com o mesmo mês do ano anterior, o volume total estimado apresentou "
            f"{situacao_volume} de {percentual(var_volume_total)}, passando de "
            f"{kg(volume_anterior_total)} para {kg(volume_atual_total)}. "
            f"O valor comercializado estimado apresentou {situacao_valor} de "
            f"{percentual(var_valor_total)}, passando de {moeda(valor_anterior_total)} para "
            f"{moeda(valor_atual_total)}. A variação em valor foi {comparacao_intensidade} "
            f"à variação física do volume, indicando influência dos preços médios na composição "
            f"do resultado final."
        )

        elementos.append(Paragraph("Interpretação final do volume", estilo_normal))
        elementos.append(Paragraph(texto_seguro(texto_interpretacao_volume), estilo_normal))

    elementos.append(Spacer(1, 12))

    # ================= OBSERVAÇÃO FINAL =================
    elementos.append(Paragraph("11. Observação", estilo_subtitulo))

    elementos.append(Paragraph(
        "Este relatório apresenta uma análise automática com base nas cotações cadastradas no sistema. "
        "As variações destacadas devem ser interpretadas considerando o contexto do mercado, "
        "a oferta dos produtos, os custos de produção, a sazonalidade e as informações fornecidas pelos permissionários.",
        estilo_normal
    ))

    doc.build(
        elementos,
        onFirstPage=adicionar_numero_pagina,
        onLaterPages=adicionar_numero_pagina
    )

    for caminho in [
        locals().get("caminho_grafico_altas"),
        locals().get("caminho_grafico_quedas")
    ]:
        if caminho and os.path.exists(caminho):
            try:
                os.remove(caminho)
            except Exception:
                pass
#=============================================================================

# ================== GERAR PDF INDIVIDUAL DO PRODUTO =========================
def gerar_pdf_produto_analise(
    df_produto,
    observacoes,
    nome_pdf,
    produto_sel,
    data_inicial,
    data_final
):
    import os
    import tempfile
    import matplotlib.pyplot as plt

    from reportlab.platypus import Image
    from reportlab.lib.enums import TA_CENTER, TA_LEFT
    from reportlab.lib.styles import ParagraphStyle
    from xml.sax.saxutils import escape

    doc = SimpleDocTemplate(
        nome_pdf,
        pagesize=A4,
        leftMargin=25,
        rightMargin=25,
        topMargin=25,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    elementos = []

    estilo_titulo = styles["Title"].clone("titulo_produto_analise")
    estilo_titulo.alignment = TA_CENTER
    estilo_titulo.fontSize = 16
    estilo_titulo.spaceAfter = 10

    estilo_subtitulo = styles["Heading2"].clone("subtitulo_produto_analise")
    estilo_subtitulo.fontSize = 12
    estilo_subtitulo.spaceBefore = 10
    estilo_subtitulo.spaceAfter = 6

    estilo_normal = styles["Normal"].clone("normal_produto_analise")
    estilo_normal.fontSize = 9
    estilo_normal.leading = 12
    estilo_normal.alignment = TA_LEFT

    estilo_info = ParagraphStyle(
        "info_produto_analise",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=colors.grey
    )

    def moeda(valor):
        try:
            return f"R$ {float(valor):.2f}".replace(".", ",")
        except Exception:
            return "R$ 0,00"

    def percentual(valor):
        try:
            return f"{float(valor):.2f}%".replace(".", ",")
        except Exception:
            return "0,00%"

    def criar_tabela(dados, larguras=None, fonte=FONTE_TABELA):
        tabela = Table(dados, colWidths=larguras, repeatRows=1)

        tabela.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E79")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), fonte),
            ("FONTSIZE", (0, 1), (-1, -1), fonte),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [
                colors.whitesmoke,
                colors.HexColor("#E8E8E8")
            ]),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))

        return tabela
    
    def criar_legenda_variacao_pdf():
        dados_legenda = [
            ["Variação", "Classificação"],
            ["Acima de 60%", "Alta crítica"],
            ["De 30% a 59,99%", "Alta acentuada"],
            ["De 10% a 29,99%", "Alta moderada"],
            ["De -10% a -29,99%", "Queda relevante"],
            ["Abaixo de -30%", "Queda acentuada"],
            ["Entre -9,99% e 9,99%", "Variação normal"]
        ]

        return criar_tabela(
            dados_legenda,
            larguras=[170, 300],
            fonte=FONTE_TABELA
        )

    df_produto = df_produto.copy()
    df_produto["data"] = pd.to_datetime(df_produto["data"], errors="coerce")
    df_produto = df_produto.dropna(subset=["data"])
    df_produto = df_produto.sort_values("data")

    elementos.append(Paragraph(f"Relatório Analítico do Produto: {escape(str(produto_sel))}", estilo_titulo))
    elementos.append(Paragraph("AMA - Autarquia Municipal de Abastecimento", estilo_info))
    elementos.append(Paragraph(f"Data de emissão: {datetime.now().strftime('%d/%m/%Y %H:%M')}", estilo_info))
    elementos.append(Spacer(1, 10))

    elementos.append(Paragraph("1. Período analisado", estilo_subtitulo))

    filtros = [
        ["Produto", str(produto_sel)],
        ["Período", f"{data_inicial.strftime('%d/%m/%Y')} a {data_final.strftime('%d/%m/%Y')}"]
    ]

    elementos.append(criar_tabela(filtros, larguras=[120, 360], fonte=FONTE_TABELA))
    elementos.append(Spacer(1, 10))

    if df_produto.empty:
        elementos.append(Paragraph("Não há dados para o produto selecionado no período.", estilo_normal))
        doc.build(
        elementos,
        onFirstPage=adicionar_numero_pagina,
        onLaterPages=adicionar_numero_pagina
    )
        return

    menor = df_produto["preco_medio"].min()
    maior = df_produto["preco_medio"].max()
    media = df_produto["preco_medio"].mean()
    amplitude = maior - menor

    preco_inicial = df_produto.iloc[0]["preco_medio"]
    preco_final = df_produto.iloc[-1]["preco_medio"]

    variacao = 0

    if preco_inicial > 0:
        variacao = ((preco_final - preco_inicial) / preco_inicial) * 100

    elementos.append(Paragraph("2. Resumo do produto", estilo_subtitulo))

    resumo = [
        ["Indicador", "Resultado"],
        ["Menor preço médio", moeda(menor)],
        ["Maior preço médio", moeda(maior)],
        ["Média do período", moeda(media)],
        ["Amplitude", moeda(amplitude)],
        ["Preço inicial", moeda(preco_inicial)],
        ["Preço final", moeda(preco_final)],
        ["Variação no período", percentual(variacao)]
    ]

    elementos.append(criar_tabela(resumo, larguras=[220, 260], fonte=FONTE_TABELA))
    elementos.append(Spacer(1, 10))

    elementos.append(Paragraph("Legenda de classificação da variação", estilo_subtitulo))
    elementos.append(criar_legenda_variacao_pdf())
    elementos.append(Spacer(1, 10))

    elementos.append(Paragraph("3. Gráfico histórico de preço médio", estilo_subtitulo))

    caminho_grafico = None

    try:
        temp = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        caminho_grafico = temp.name
        temp.close()

        fig, ax = plt.subplots(figsize=(7, 3))

        ax.plot(
            df_produto["data"],
            df_produto["preco_medio"],
            marker="o"
        )

        ax.set_title(f"Evolução do preço médio - {produto_sel}")
        ax.set_xlabel("Data")
        ax.set_ylabel("Preço médio (R$)")
        ax.grid(True, alpha=0.3)

        fig.autofmt_xdate()
        fig.tight_layout()

        fig.savefig(caminho_grafico, dpi=180)
        plt.close(fig)

        elementos.append(Image(caminho_grafico, width=480, height=220))
        elementos.append(Spacer(1, 10))

    except Exception:
        elementos.append(Paragraph("Não foi possível gerar o gráfico do produto.", estilo_normal))

    elementos.append(Paragraph("4. Histórico de preços", estilo_subtitulo))

    dados_historico = [[
        "Data",
        "Unid.",
        "Kg",
        "Preço mín.",
        "Preço máx.",
        "Preço médio",
        "Valor/kg"
    ]]

    for _, row in df_produto.iterrows():
        dados_historico.append([
            row["data"].strftime("%d/%m/%Y"),
            str(row.get("unidade", "")),
            str(int(row.get("kg", 0))) if pd.notnull(row.get("kg", 0)) else "",
            moeda(row.get("preco_min", 0)),
            moeda(row.get("preco_max", 0)),
            moeda(row.get("preco_medio", 0)),
            moeda(row.get("valor_kg", 0))
        ])

    elementos.append(
        criar_tabela(
            dados_historico,
            larguras=[65, 45, 35, 70, 70, 80, 70],
            fonte=FONTE_TABELA
        )
    )

    elementos.append(Spacer(1, 10))

    elementos.append(Paragraph("5. Observações registradas", estilo_subtitulo))

    if observacoes is None or observacoes.empty:
        elementos.append(Paragraph("Nenhuma observação registrada para este produto no período.", estilo_normal))
    else:
        observacoes = observacoes.copy()
        observacoes["data_ref"] = pd.to_datetime(
            observacoes["data_ref"],
            errors="coerce"
        )

        for _, row in observacoes.iterrows():
            data_txt = ""

            if pd.notnull(row.get("data_ref")):
                data_txt = row["data_ref"].strftime("%d/%m/%Y")

            texto_obs = escape(str(row.get("observacao", ""))).replace("\n", "<br/>")

            elementos.append(
                Paragraph(
                    f"<b>{data_txt}</b> - {texto_obs}",
                    estilo_normal
                )
            )

            elementos.append(Spacer(1, 5))

    elementos.append(Paragraph("6. Interpretação automática", estilo_subtitulo))

    if variacao >= 60:
        interpretacao = (
            "O produto apresentou alta crítica no período analisado. "
            "Recomenda-se verificar fatores como baixa oferta, aumento de custos de produção, "
            "sazonalidade, transporte, qualidade do produto e relatos dos permissionários."
        )
    elif variacao >= 30:
        interpretacao = (
            "O produto apresentou alta acentuada no período analisado. "
            "Essa variação merece atenção e deve ser acompanhada nos próximos registros."
        )
    elif variacao <= -30:
        interpretacao = (
            "O produto apresentou queda acentuada no período analisado. "
            "Essa redução pode estar relacionada a maior oferta, menor demanda ou normalização do abastecimento."
        )
    elif abs(variacao) < 10:
        interpretacao = (
            "O produto apresentou variação considerada normal no período analisado."
        )
    else:
        interpretacao = (
            "O produto apresentou variação relevante no período analisado, recomendando-se acompanhamento."
        )

    elementos.append(Paragraph(escape(interpretacao), estilo_normal))

    elementos.append(Spacer(1, 10))

    elementos.append(Paragraph(
        "Este relatório foi gerado automaticamente a partir das cotações cadastradas e das observações registradas no sistema.",
        estilo_info
    ))

    doc.build(
        elementos,
        onFirstPage=adicionar_numero_pagina,
        onLaterPages=adicionar_numero_pagina
    )

    if caminho_grafico and os.path.exists(caminho_grafico):
        try:
            os.remove(caminho_grafico)
        except Exception:
            pass
#========================================================================================================