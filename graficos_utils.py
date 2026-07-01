MARCADORES = [
    "o",   # círculo
    "s",   # quadrado
    "^",   # triângulo
    "D",   # losango
    "v",   # triângulo invertido
    "P",   # cruz preenchida
    "X"    # X
]

ESTILOS_LINHA = [
    "-",
    "--",
    ":",
    "-."
]

HACHURAS = [
    "///",
    r"\\",
    "...",
    "xxx",
    "---",
    "+++"
]


def obter_estilo_linha(indice):
    """Retorna um marcador e um estilo de linha conforme o índice."""
    marcador = MARCADORES[
        indice % len(MARCADORES)
    ]

    estilo_linha = ESTILOS_LINHA[
        indice % len(ESTILOS_LINHA)
    ]

    return marcador, estilo_linha


def obter_hachura(indice):
    """Retorna uma hachura conforme o índice."""
    return HACHURAS[
        indice % len(HACHURAS)
    ]


def aplicar_estilo_impressao(eixo):
    """Aplica um padrão legível em tela e em impressão preto e branco."""
    eixo.grid(
        True,
        linestyle=":",
        linewidth=0.6,
        alpha=0.6
    )

    eixo.set_axisbelow(True)
    eixo.spines["top"].set_visible(False)
    eixo.spines["right"].set_visible(False)
