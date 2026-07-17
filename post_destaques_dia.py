import os
import tempfile
import textwrap

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch

from dados_utils import carregar_todas_cotacoes
from relatorio_diario import preparar_relatorio_diario
from utils import corrigir_classe


# =========================================================
# CORES
# =========================================================
AZUL_ESCURO = "#123B63"
AZUL_BARRA = "#1E5D8C"
AZUL_CLARO = "#E7F0F7"

VERMELHO = "#A93E3E"
VERMELHO_BARRA = "#8E2E2E"
VERMELHO_CLARO = "#F7E8E8"

CINZA_TEXTO = "#263238"
CINZA_MEDIO = "#65727B"
CINZA_CLARO = "#EEF1F4"
FUNDO = "#F7F9FB"
BRANCO = "#FFFFFF"


# =========================================================
# FORMATAÇÕES
# =========================================================
def formatar_moeda(valor):
    try:
        return (
            f"R$ {float(valor):,.2f}"
            .replace(",", "X")
            .replace(".", ",")
            .replace("X", ".")
        )
    except Exception:
        return "R$ 0,00"


def formatar_percentual(valor):
    try:
        return f"{float(valor):.2f}%".replace(".", ",")
    except Exception:
        return "0,00%"


def limitar_texto(texto, limite=28):
    texto = str(texto or "").strip()

    if len(texto) <= limite:
        return texto

    return texto[: limite - 3] + "..."


def quebrar_texto(texto, largura=42):
    return textwrap.fill(
        str(texto or ""),
        width=largura,
        break_long_words=False,
        break_on_hyphens=False
    )



# =========================================================
# PREPARAÇÃO DOS DADOS
# =========================================================
def garantir_coluna_numerica(df, coluna):
    if coluna not in df.columns:
        df[coluna] = 0.0

    df[coluna] = pd.to_numeric(
        df[coluna],
        errors="coerce"
    ).fillna(0)

    return df


def preparar_destaques_post(dados, quantidade=3):
    comparativo = dados.get(
        "comparativo",
        pd.DataFrame()
    ).copy()

    colunas_numericas = [
        "valor_kg_anterior",
        "valor_kg_atual",
        "preco_medio_anterior",
        "preco_medio_atual",
        "variacao_percentual"
    ]

    for coluna in colunas_numericas:
        comparativo = garantir_coluna_numerica(
            comparativo,
            coluna
        )

    if "produto" not in comparativo.columns:
        comparativo["produto"] = ""

    comparaveis = comparativo[
        comparativo["valor_kg_anterior"] > 0
    ].copy()

    ranking_altas = (
        comparaveis[
            comparaveis["variacao_percentual"] > 0
        ]
        .sort_values(
            "variacao_percentual",
            ascending=False
        )
        .head(quantidade)
        .copy()
    )

    ranking_quedas = (
        comparaveis[
            comparaveis["variacao_percentual"] < 0
        ]
        .sort_values(
            "variacao_percentual",
            ascending=True
        )
        .head(quantidade)
        .copy()
    )

    return {
        "comparativo": comparativo,
        "ranking_altas": ranking_altas,
        "ranking_quedas": ranking_quedas,
        "data_anterior": dados.get("data_anterior"),
        "df_dia": dados.get(
            "df_dia",
            pd.DataFrame()
        )
    }

def criar_tabela_top3_dataframe(
    ranking_altas,
    ranking_quedas
):
    partes = []

    if ranking_altas is not None and not ranking_altas.empty:
        altas = ranking_altas.copy()
        altas["produto"] = "▲ " + altas["produto"].astype(str)
        partes.append(altas)

    if ranking_quedas is not None and not ranking_quedas.empty:
        quedas = ranking_quedas.copy()
        quedas["produto"] = "▼ " + quedas["produto"].astype(str)
        partes.append(quedas)

    if not partes:
        return pd.DataFrame(
            columns=[
                "produto",
                "valor_kg_anterior",
                "valor_kg_atual",
                "preco_medio_anterior",
                "preco_medio_atual",
                "variacao_percentual"
            ]
        )

    tabela = pd.concat(
        partes,
        ignore_index=True
    )

    colunas = [
        "produto",
        "valor_kg_anterior",
        "valor_kg_atual",
        "preco_medio_anterior",
        "preco_medio_atual",
        "variacao_percentual"
    ]

    for coluna in colunas:
        if coluna not in tabela.columns:
            tabela[coluna] = 0 if coluna != "produto" else ""

    return tabela[colunas].copy()


def formatar_tabela_top3_tela(tabela):
    tabela = tabela.copy()

    tabela = tabela.rename(
        columns={
            "produto": "Produto",
            "valor_kg_anterior": "Valor/kg ant.",
            "valor_kg_atual": "Valor/kg atual",
            "preco_medio_anterior": "Preço médio ant.",
            "preco_medio_atual": "Preço médio atual",
            "variacao_percentual": "Variação"
        }
    )

    for coluna in [
        "Valor/kg ant.",
        "Valor/kg atual",
        "Preço médio ant.",
        "Preço médio atual"
    ]:
        tabela[coluna] = tabela[coluna].apply(
            formatar_moeda
        )

    tabela["Variação"] = tabela["Variação"].apply(
        formatar_percentual
    )

    return tabela


def gerar_resumo_cotacao(
    dados_post,
    data_ref
):
    comparativo = dados_post.get(
        "comparativo",
        pd.DataFrame()
    ).copy()

    df_dia = dados_post.get(
        "df_dia",
        pd.DataFrame()
    ).copy()

    ranking_altas = dados_post.get(
        "ranking_altas",
        pd.DataFrame()
    )

    ranking_quedas = dados_post.get(
        "ranking_quedas",
        pd.DataFrame()
    )

    total_produtos = (
        df_dia["produto"].nunique()
        if (
            not df_dia.empty
            and "produto" in df_dia.columns
        )
        else 0
    )

    comparaveis = comparativo[
        comparativo["valor_kg_anterior"] > 0
    ].copy()

    quantidade_comparaveis = len(
        comparaveis
    )

    quantidade_altas = int(
        (
            comparaveis["variacao_percentual"] > 0
        ).sum()
    )

    quantidade_quedas = int(
        (
            comparaveis["variacao_percentual"] < 0
        ).sum()
    )

    quantidade_estaveis = int(
        (
            comparaveis["variacao_percentual"] == 0
        ).sum()
    )

    linhas = []

    linhas.append(
        (
            f"Na cotação de {pd.to_datetime(data_ref).strftime('%d/%m/%Y')}, "
            f"foram registrados {total_produtos} produtos."
        )
    )

    if quantidade_comparaveis > 0:
        linhas.append(
            (
                f"Entre os {quantidade_comparaveis} produtos com histórico comparável, "
                f"{quantidade_altas} apresentaram alta, "
                f"{quantidade_quedas} apresentaram queda e "
                f"{quantidade_estaveis} permaneceram sem alteração."
            )
        )
    else:
        linhas.append(
            "Não havia histórico anterior suficiente para comparar os preços desta cotação."
        )

    if ranking_altas is not None and not ranking_altas.empty:
        maior_alta = ranking_altas.iloc[0]

        linhas.append(
            (
                f"A maior alta foi de {maior_alta.get('produto', '')}, "
                f"com variação de {formatar_percentual(maior_alta.get('variacao_percentual', 0))}, "
                f"passando de {formatar_moeda(maior_alta.get('valor_kg_anterior', 0))}/kg "
                f"para {formatar_moeda(maior_alta.get('valor_kg_atual', 0))}/kg."
            )
        )

    if ranking_quedas is not None and not ranking_quedas.empty:
        maior_queda = ranking_quedas.iloc[0]

        linhas.append(
            (
                f"A maior queda foi de {maior_queda.get('produto', '')}, "
                f"com variação de {formatar_percentual(maior_queda.get('variacao_percentual', 0))}, "
                f"passando de {formatar_moeda(maior_queda.get('valor_kg_anterior', 0))}/kg "
                f"para {formatar_moeda(maior_queda.get('valor_kg_atual', 0))}/kg."
            )
        )

    return linhas


# =========================================================
# ELEMENTOS VISUAIS
# =========================================================
def adicionar_card(
    fig,
    x,
    y,
    largura,
    altura,
    cor_fundo=BRANCO,
    cor_borda="#D5DCE3",
    sombra=True
):
    if sombra:
        sombra_card = FancyBboxPatch(
            (x + 0.004, y - 0.004),
            largura,
            altura,
            boxstyle="round,pad=0.006,rounding_size=0.018",
            transform=fig.transFigure,
            facecolor="#000000",
            edgecolor="none",
            alpha=0.07,
            zorder=0
        )
        fig.patches.append(sombra_card)

    card = FancyBboxPatch(
        (x, y),
        largura,
        altura,
        boxstyle="round,pad=0.006,rounding_size=0.018",
        transform=fig.transFigure,
        facecolor=cor_fundo,
        edgecolor=cor_borda,
        linewidth=0.9,
        zorder=1
    )
    fig.patches.append(card)

    return card


def criar_card_indicador(
    fig,
    posicao,
    titulo,
    valor,
    complemento,
    cor_destaque
):
    x, y, largura, altura = posicao

    adicionar_card(
        fig,
        x,
        y,
        largura,
        altura
    )

    ax = fig.add_axes(
        [x, y, largura, altura],
        zorder=3
    )
    ax.axis("off")

    ax.add_line(
        Line2D(
            [0.04, 0.04],
            [0.20, 0.80],
            transform=ax.transAxes,
            color=cor_destaque,
            linewidth=5,
            solid_capstyle="round"
        )
    )

    ax.text(
        0.10,
        0.70,
        titulo,
        fontsize=9.5,
        color=cor_destaque,
        fontweight="bold",
        transform=ax.transAxes
    )

    ax.text(
        0.10,
        0.40,
        valor,
        fontsize=16.5,
        color=CINZA_TEXTO,
        fontweight="bold",
        transform=ax.transAxes
    )

    ax.text(
        0.10,
        0.13,
        limitar_texto(complemento, 25),
        fontsize=7.7,
        color=CINZA_MEDIO,
        fontweight="bold",
        transform=ax.transAxes
    )

    return ax


def plotar_ranking(
    ax,
    ranking,
    titulo,
    tipo="alta"
):
    ax.set_facecolor(BRANCO)

    if ranking is None or ranking.empty:
        ax.axis("off")
        ax.text(
            0.5,
            0.55,
            "Sem variações",
            ha="center",
            va="center",
            fontsize=11,
            fontweight="bold",
            color=CINZA_TEXTO,
            transform=ax.transAxes
        )
        return

    df_plot = ranking.copy()

    if tipo == "alta":
        df_plot = df_plot.sort_values(
            "variacao_percentual",
            ascending=True
        )
        cor_barra = AZUL_BARRA
        cor_titulo = AZUL_ESCURO
    else:
        df_plot = df_plot.sort_values(
            "variacao_percentual",
            ascending=False
        )
        cor_barra = VERMELHO_BARRA
        cor_titulo = VERMELHO

    valores = pd.to_numeric(
        df_plot["variacao_percentual"],
        errors="coerce"
    ).fillna(0).tolist()

    produtos = [
        quebrar_texto(
            limitar_texto(nome, 25),
            13
        )
        for nome in df_plot["produto"].astype(str).tolist()
    ]

    posicoes = list(
        range(len(df_plot))
    )

    barras = ax.barh(
        posicoes,
        valores,
        color=cor_barra,
        edgecolor="none",
        linewidth=0,
        height=0.56
    )

    ax.set_yticks(posicoes)
    ax.set_yticklabels(
        produtos,
        fontsize=7.5,
        color=CINZA_TEXTO,
        rotation=10,
        ha="right",
        va="center",
        rotation_mode="anchor"
    )

    limite = max(
        max(abs(valor) for valor in valores),
        1
    )

    margem = limite * 0.12

    if tipo == "alta":
        ax.set_xlim(
            0,
            limite + margem
        )

        for barra, valor in zip(
            barras,
            valores
        ):
            ax.text(
                valor * 0.96,
                barra.get_y() + barra.get_height() / 2,
                formatar_percentual(valor),
                va="center",
                ha="right",
                fontsize=7.7,
                fontweight="bold",
                color=BRANCO
            )
    else:
        ax.set_xlim(
            -(limite + margem),
            0
        )

        for barra, valor in zip(
            barras,
            valores
        ):
            ax.text(
                valor * 0.96,
                barra.get_y() + barra.get_height() / 2,
                formatar_percentual(valor),
                va="center",
                ha="left",
                fontsize=7.7,
                fontweight="bold",
                color=BRANCO
            )

    ax.set_title(
        titulo,
        fontsize=12.2,
        fontweight="bold",
        color=cor_titulo,
        pad=8
    )

    ax.grid(False)
    ax.tick_params(
        axis="x",
        bottom=False,
        labelbottom=False
    )
    ax.tick_params(
        axis="y",
        length=0
    )

    for lado in [
        "top",
        "right",
        "left",
        "bottom"
    ]:
        ax.spines[lado].set_visible(False)


def desenhar_tabela_top3(
    fig,
    posicao,
    tabela
):
    x, y, largura, altura = posicao

    adicionar_card(
        fig,
        x,
        y,
        largura,
        altura
    )

    ax = fig.add_axes(
        [
            x + 0.018,
            y + 0.018,
            largura - 0.036,
            altura - 0.032
        ],
        zorder=4
    )
    ax.axis("off")

    ax.text(
        0.0,
        0.97,
        "Top 3 — preços anteriores e atuais",
        fontsize=13.2,
        fontweight="bold",
        color=AZUL_ESCURO,
        va="top",
        transform=ax.transAxes
    )

    if tabela is None or tabela.empty:
        ax.text(
            0.5,
            0.45,
            "Sem produtos comparáveis.",
            ha="center",
            va="center",
            fontsize=10,
            color=CINZA_MEDIO,
            transform=ax.transAxes
        )
        return

    dados = []

    for _, row in tabela.iterrows():
        dados.append(
            [
                limitar_texto(
                    row.get("produto", ""),
                    25
                ),
                formatar_moeda(
                    row.get(
                        "valor_kg_anterior",
                        0
                    )
                ),
                formatar_moeda(
                    row.get(
                        "valor_kg_atual",
                        0
                    )
                ),
                formatar_moeda(
                    row.get(
                        "preco_medio_anterior",
                        0
                    )
                ),
                formatar_moeda(
                    row.get(
                        "preco_medio_atual",
                        0
                    )
                ),
                formatar_percentual(
                    row.get(
                        "variacao_percentual",
                        0
                    )
                )
            ]
        )

    colunas = [
        "Produto",
        "Valor/kg ant.",
        "Valor/kg atual",
        "Preço médio ant.",
        "Preço médio atual",
        "Variação"
    ]

    tabela_mpl = ax.table(
        cellText=dados,
        colLabels=colunas,
        cellLoc="center",
        colLoc="center",
        colWidths=[
            0.27,
            0.145,
            0.145,
            0.155,
            0.155,
            0.13
        ],
        bbox=[
            0.0,
            0.0,
            1.0,
            0.82
        ]
    )

    tabela_mpl.auto_set_font_size(False)
    tabela_mpl.set_fontsize(8.2)
    tabela_mpl.scale(
        1,
        1.42
    )
    for (
        linha,
        coluna
    ), celula in tabela_mpl.get_celld().items():

        celula.set_edgecolor("#D7DEE4")
        celula.set_linewidth(0.55)

        if linha == 0:
            celula.set_facecolor(
                AZUL_ESCURO
            )
            celula.get_text().set_color(
                BRANCO
            )
            celula.get_text().set_fontweight(
                "bold"
            )
            celula.get_text().set_fontsize(
                8.2
            )

        else:
            celula.get_text().set_fontsize(
                8.5
            )

            produto = str(
                tabela.iloc[
                    linha - 1
                ]["produto"]
            )

            if produto.startswith("▲"):
                celula.set_facecolor(
                    AZUL_CLARO
                )
            else:
                celula.set_facecolor(
                    VERMELHO_CLARO
                )

            if coluna == 0:
                celula.get_text().set_ha(
                    "left"
                )
                celula.get_text().set_fontweight(
                    "bold"
                )
                celula.get_text().set_fontsize(
                    8.7
                )

            if coluna == 5:
                celula.get_text().set_fontweight(
                    "bold"
                )
                celula.get_text().set_fontsize(
                    8.7
                )

def desenhar_resumo_cotacao(
    fig,
    posicao,
    resumo
):
    x, y, largura, altura = posicao

    adicionar_card(
        fig,
        x,
        y,
        largura,
        altura
    )

    ax = fig.add_axes(
        [
            x + 0.025,
            y + 0.022,
            largura - 0.050,
            altura - 0.044
        ],
        zorder=4
    )
    ax.axis("off")

    ax.text(
        0.0,
        0.95,
        "Resumo da cotação",
        fontsize=17,
        fontweight="bold",
        color=AZUL_ESCURO,
        va="top",
        transform=ax.transAxes
    )

    ax.add_line(
        Line2D(
            [0.0, 0.16],
            [0.82, 0.82],
            transform=ax.transAxes,
            color=VERMELHO,
            linewidth=2.8,
            solid_capstyle="round"
        )
    )

    if isinstance(resumo, str):
        resumo = [resumo]

    y_atual = 0.68

    for indice, linha in enumerate(resumo):

        # Pula uma linha antes do terceiro parágrafo
        if indice == 2:
            y_atual -= 0.08

        texto_formatado = quebrar_texto(
            linha,
            95
        )

        ax.text(
            0.0,
            y_atual,
            texto_formatado,
            fontsize=11.4,
            color=CINZA_TEXTO,
            va="top",
            linespacing=1.45,
            transform=ax.transAxes,
            parse_math=False
        )

        quantidade_linhas = (
            texto_formatado.count("\n") + 1
        )

        y_atual -= (
            0.12
            + (quantidade_linhas - 1) * 0.08
        )


# =========================================================
# GERAÇÃO DO POST EM UMA ÚNICA PÁGINA
# =========================================================
def gerar_post_destaques_dia(
    dados,
    data_ref,
    classe_sel="Todas",
    logo_path=None
):
    dados_post = preparar_destaques_post(
        dados,
        quantidade=3
    )

    ranking_altas = dados_post[
        "ranking_altas"
    ]
    ranking_quedas = dados_post[
        "ranking_quedas"
    ]
    data_anterior = dados_post[
        "data_anterior"
    ]
    df_dia = dados_post[
        "df_dia"
    ]

    tabela_top3 = criar_tabela_top3_dataframe(
        ranking_altas,
        ranking_quedas
    )

    resumo_cotacao = gerar_resumo_cotacao(
        dados_post,
        data_ref
    )

    data_ref = pd.to_datetime(
        data_ref
    ).date()

    fig = plt.figure(
        figsize=(
            10.8,
            13.5
        ),
        facecolor=FUNDO
    )

    ax_fundo = fig.add_axes(
        [0, 0, 1, 1],
        zorder=-10
    )
    ax_fundo.axis("off")
    ax_fundo.set_facecolor(
        FUNDO
    )

    ax_fundo.add_patch(
        FancyBboxPatch(
            (
                -0.04,
                0.875
            ),
            1.08,
            0.17,
            boxstyle=(
                "round,pad=0.01,"
                "rounding_size=0.04"
            ),
            transform=ax_fundo.transAxes,
            facecolor=AZUL_ESCURO,
            edgecolor="none"
        )
    )

    # ---------------- CABEÇALHO ----------------
    ax_header = fig.add_axes(
        [
            0.06,
            0.895,
            0.88,
            0.085
        ],
        zorder=4
    )
    ax_header.axis("off")

    if (
        logo_path
        and os.path.exists(logo_path)
    ):
        try:
            imagem_logo = plt.imread(
                logo_path
            )
            ax_logo = fig.add_axes(
                [
                    0.075,
                    0.91,
                    0.17,
                    0.06
                ],
                zorder=5
            )
            ax_logo.imshow(
                imagem_logo
            )
            ax_logo.axis("off")
        except Exception:
            ax_header.text(
                0.02,
                0.50,
                "AMA",
                fontsize=34,
                color=BRANCO,
                fontweight="bold",
                va="center",
                transform=ax_header.transAxes
            )
    else:
        ax_header.text(
            0.02,
            0.50,
            "AMA",
            fontsize=34,
            color=BRANCO,
            fontweight="bold",
            va="center",
            transform=ax_header.transAxes
        )

    ax_header.text(
        0.31,
        0.72,
        "MERCADO DO PRODUTOR DE JUAZEIRO-BA",
        fontsize=10.5,
        color="#DCE9F4",
        fontweight="bold",
        transform=ax_header.transAxes
    )

    ax_header.text(
        0.31,
        0.34,
        "Destaques do Dia",
        fontsize=29,
        color=BRANCO,
        fontweight="bold",
        transform=ax_header.transAxes
    )

    data_anterior_txt = (
        data_anterior.strftime(
            "%d/%m/%Y"
        )
        if data_anterior
        else "Sem data anterior"
    )

    ax_header.text(
        0.31,
        0.02,
        (
            f"Cotação: "
            f"{data_ref.strftime('%d/%m/%Y')}"
            f"  |  Comparação: "
            f"{data_anterior_txt}"
            f"  |  Classe: "
            f"{classe_sel}"
        ),
        fontsize=8.6,
        color="#DCE9F4",
        transform=ax_header.transAxes
    )

    total_produtos = (
        df_dia["produto"].nunique()
        if (
            not df_dia.empty
            and "produto" in df_dia.columns
        )
        else 0
    )

    maior_alta_valor = (
        formatar_percentual(
            ranking_altas.iloc[
                0
            ]["variacao_percentual"]
        )
        if not ranking_altas.empty
        else "Sem alta"
    )

    maior_alta_produto = (
        ranking_altas.iloc[
            0
        ]["produto"]
        if not ranking_altas.empty
        else "Nenhum produto"
    )

    maior_queda_valor = (
        formatar_percentual(
            ranking_quedas.iloc[
                0
            ]["variacao_percentual"]
        )
        if not ranking_quedas.empty
        else "Sem queda"
    )

    maior_queda_produto = (
        ranking_quedas.iloc[
            0
        ]["produto"]
        if not ranking_quedas.empty
        else "Nenhum produto"
    )

    # ---------------- INDICADORES ----------------
    criar_card_indicador(
        fig,
        [
            0.065,
            0.815,
            0.27,
            0.055
        ],
        "MAIOR ALTA",
        maior_alta_valor,
        maior_alta_produto,
        AZUL_BARRA
    )

    criar_card_indicador(
        fig,
        [
            0.365,
            0.815,
            0.27,
            0.055
        ],
        "MAIOR QUEDA",
        maior_queda_valor,
        maior_queda_produto,
        VERMELHO_BARRA
    )

    criar_card_indicador(
        fig,
        [
            0.665,
            0.815,
            0.27,
            0.055
        ],
        "PRODUTOS COTADOS",
        str(total_produtos),
        "na data selecionada",
        AZUL_ESCURO
    )

    # ---------------- GRÁFICOS ----------------
    adicionar_card(
        fig,
        0.06,
        0.625,
        0.42,
        0.165
    )

    ax_altas = fig.add_axes(
        [
            0.16,
            0.655,
            0.28,
            0.09
        ],
        zorder=4
    )

    plotar_ranking(
        ax_altas,
        ranking_altas,
        "Top 3 altas",
        tipo="alta"
    )

    adicionar_card(
        fig,
        0.52,
        0.625,
        0.42,
        0.165
    )

    ax_quedas = fig.add_axes(
        [
            0.64,
            0.655,
            0.26,
            0.09
        ],
        zorder=4
    )

    plotar_ranking(
        ax_quedas,
        ranking_quedas,
        "Top 3 quedas",
        tipo="queda"
    )

    # ---------------- TABELA TOP 3 ----------------
    desenhar_tabela_top3(
        fig,
        [
            0.06,
            0.355,
            0.88,
            0.235
        ],
        tabela_top3
    )

    # ---------------- RESUMO DA COTAÇÃO ----------------
    desenhar_resumo_cotacao(
        fig,
        [
            0.06,
            0.115,
            0.88,
            0.205
        ],
        resumo_cotacao
    )

    # ---------------- RODAPÉ ----------------
    ax_rodape = fig.add_axes(
        [
            0.06,
            0.035,
            0.88,
            0.045
        ],
        zorder=4
    )
    ax_rodape.axis("off")

    ax_rodape.text(
        0.5,
        0.68,
        (
            "Acompanhe a cotação diária do "
            "Mercado do Produtor de Juazeiro"
        ),
        fontsize=9.7,
        color=AZUL_ESCURO,
        fontweight="bold",
        ha="center",
        transform=ax_rodape.transAxes
    )

    ax_rodape.text(
        0.5,
        0.22,
        "@mercadodoprodutorjuazeiro",
        fontsize=9,
        color=CINZA_MEDIO,
        ha="center",
        transform=ax_rodape.transAxes
    )

    caminho_temp = tempfile.NamedTemporaryFile(
        delete=False,
        suffix=".png"
    )
    caminho_png = caminho_temp.name
    caminho_temp.close()

    fig.savefig(
        caminho_png,
        dpi=180,
        facecolor=fig.get_facecolor()
    )
    plt.close(fig)

    return caminho_png


# =========================================================
# TELA STREAMLIT
# =========================================================
def tela_post_destaques_dia(supabase):
    st.title("Destaques do Dia")

    st.info(
        "O post reúne gráficos, preços anteriores e atuais "
        "e um resumo da cotação em uma única página."
    )

    try:
        df = carregar_todas_cotacoes(
            supabase
        )
    except Exception as erro:
        st.error(
            f"Erro ao carregar as cotações: {erro}"
        )
        return

    if df.empty:
        st.warning(
            "Ainda não há cotações cadastradas."
        )
        return

    df = df.copy()

    df["data"] = pd.to_datetime(
        df["data"],
        errors="coerce"
    )

    df = df.dropna(
        subset=["data"]
    )

    if df.empty:
        st.warning(
            "Não há datas válidas nas cotações."
        )
        return

    df["classe"] = (
        df["classe"]
        .astype(str)
        .str.strip()
        .apply(corrigir_classe)
    )

    datas_disponiveis = sorted(
        df["data"]
        .dt.date
        .unique()
        .tolist(),
        reverse=True
    )

    classes_disponiveis = (
        ["Todas"]
        + sorted(
            df["classe"]
            .dropna()
            .unique()
            .tolist()
        )
    )

    col1, col2 = st.columns(2)

    with col1:
        data_ref = st.selectbox(
            "Data da cotação",
            datas_disponiveis,
            format_func=lambda data: (
                data.strftime(
                    "%d/%m/%Y"
                )
            ),
            key="post_destaques_data"
        )

    with col2:
        classe_sel = st.selectbox(
            "Classe",
            classes_disponiveis,
            key="post_destaques_classe"
        )

    dados = preparar_relatorio_diario(
        df_todas=df,
        data_ref=data_ref,
        classe_sel=classe_sel
    )

    if dados is None:
        st.warning(
            "Nenhuma cotação foi encontrada "
            "para os filtros selecionados."
        )
        return

    dados_post = preparar_destaques_post(
        dados,
        quantidade=3
    )

    ranking_altas = dados_post[
        "ranking_altas"
    ]
    ranking_quedas = dados_post[
        "ranking_quedas"
    ]

    tabela_top3 = criar_tabela_top3_dataframe(
        ranking_altas,
        ranking_quedas
    )

    st.subheader(
        "Top 3 — preços anteriores e atuais"
    )

    if tabela_top3.empty:
        st.info(
            "Não há produtos comparáveis."
        )
    else:
        st.dataframe(
            formatar_tabela_top3_tela(
                tabela_top3
            ),
            width="stretch",
            hide_index=True
        )

    resumo_cotacao = gerar_resumo_cotacao(
        dados_post,
        data_ref
    )

    st.subheader(
        "Resumo da cotação"
    )

    st.write(
        resumo_cotacao
    )

    if st.button(
        "Gerar post em uma única página",
        type="primary",
        key="btn_gerar_post_destaques"
    ):
        try:
            logo_path = None

            for caminho_logo in [
                "logo_novo.png",
                "logo.png"
            ]:
                if os.path.exists(
                    caminho_logo
                ):
                    logo_path = caminho_logo
                    break

            caminho_png = (
                gerar_post_destaques_dia(
                    dados=dados,
                    data_ref=data_ref,
                    classe_sel=classe_sel,
                    logo_path=logo_path
                )
            )

            st.success(
                "Post gerado com sucesso."
            )

            st.image(
                caminho_png,
                caption=(
                    "Prévia do post "
                    "Destaques do Dia"
                ),
                width="stretch"
            )

            nome_arquivo = (
                "post_destaques_"
                f"{data_ref.strftime('%d-%m-%Y')}"
                ".png"
            )

            with open(
                caminho_png,
                "rb"
            ) as arquivo:
                st.download_button(
                    "Baixar post em PNG",
                    data=arquivo,
                    file_name=nome_arquivo,
                    mime="image/png"
                )

        except Exception as erro:
            st.error(
                f"Erro ao gerar o post: {erro}"
            )
