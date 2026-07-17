TABELA_COTACOES = "cotacoes"

CAMPOS_COTACAO = (
    "data",
    "classe",
    "produto",
    "unidade",
    "kg",
    "preco_min",
    "preco_max",
    "preco_medio",
    "valor_kg",
    "precos_digitados"
)


def preparar_registro_cotacao(registro):
    return {
        campo: registro.get(campo)
        for campo in CAMPOS_COTACAO
        if campo in registro
    }


def preparar_registros_cotacao(registros):
    return [
        preparar_registro_cotacao(registro)
        for registro in registros
    ]


def montar_query_cotacoes(supabase, data_str, produto=None):
    query = (
        supabase
        .table(TABELA_COTACOES)
        .select("*")
        .eq("data", data_str)
    )

    if produto:
        query = query.eq("produto", produto)

    return query


def carregar_cotacoes_existentes(supabase, data_str, produto=None):
    resposta = montar_query_cotacoes(
        supabase,
        data_str,
        produto=produto
    ).execute()

    return resposta.data or []


def apagar_cotacoes(supabase, data_str, produto=None):
    query = (
        supabase
        .table(TABELA_COTACOES)
        .delete()
        .eq("data", data_str)
    )

    if produto:
        query = query.eq("produto", produto)

    return query.execute()


def inserir_cotacoes(supabase, registros):
    return (
        supabase
        .table(TABELA_COTACOES)
        .insert(preparar_registros_cotacao(registros))
        .execute()
    )


def restaurar_cotacoes(supabase, registros):
    if not registros:
        return None

    return inserir_cotacoes(
        supabase,
        preparar_registros_cotacao(registros)
    )


def salvar_cotacoes_com_protecao(supabase, data_str, registros, produto=None):
    """
    Salva cotações preservando os dados antigos quando há substituição.

    Se já existiam registros para o alvo informado, eles são buscados antes
    da exclusão. Caso a nova gravação falhe ou não seja confirmada pelo banco,
    o sistema tenta restaurar automaticamente os registros anteriores.
    """
    registros = preparar_registros_cotacao(registros)

    if not registros:
        raise ValueError("Nenhuma cotação válida para salvar.")

    registros_anteriores = carregar_cotacoes_existentes(
        supabase,
        data_str,
        produto=produto
    )

    apagou_registros_anteriores = False

    try:
        if registros_anteriores:
            apagar_cotacoes(
                supabase,
                data_str,
                produto=produto
            )
            apagou_registros_anteriores = True

        resposta = inserir_cotacoes(supabase, registros)

        if resposta.data:
            return resposta

        raise RuntimeError("O banco não confirmou a gravação.")

    except Exception as erro:
        if registros_anteriores and apagou_registros_anteriores:
            try:
                apagar_cotacoes(
                    supabase,
                    data_str,
                    produto=produto
                )
                restaurar_cotacoes(
                    supabase,
                    registros_anteriores
                )
            except Exception as erro_restauracao:
                raise RuntimeError(
                    "A gravação falhou e os dados anteriores não puderam "
                    f"ser restaurados automaticamente: {erro_restauracao}"
                ) from erro

            raise RuntimeError(
                f"{erro} Os dados anteriores foram restaurados automaticamente."
            ) from erro

        raise
