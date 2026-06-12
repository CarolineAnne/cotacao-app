import re
from datetime import datetime


def limpar_nome_arquivo(nome):
    nome = str(nome).lower().strip()
    nome = re.sub(r"[^\w\s.-]", "", nome)
    nome = re.sub(r"\s+", "_", nome)
    return nome


def carregar_info_produto(supabase, produto_id):
    try:
        resp = (
            supabase
            .table("produtos_info")
            .select("*")
            .eq("produto_id", int(produto_id))
            .execute()
        )

        if resp.data:
            return resp.data[0]

        return None

    except Exception as e:
        raise Exception(f"Erro ao carregar informações do produto: {e}")


def upload_foto_produto(supabase, produto_id, arquivo):
    if arquivo is None:
        return None, None

    try:
        nome_original = limpar_nome_arquivo(arquivo.name)

        if "." in nome_original:
            extensao = nome_original.split(".")[-1]
        else:
            extensao = "png"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        caminho = f"{produto_id}/produto_{produto_id}_{timestamp}.{extensao}"

        conteudo = arquivo.getvalue()

        supabase.storage.from_("produtos").upload(
            path=caminho,
            file=conteudo,
            file_options={
                "content-type": arquivo.type
            }
        )

        foto_url = supabase.storage.from_("produtos").get_public_url(caminho)

        return foto_url, caminho

    except Exception as e:
        raise Exception(f"Erro ao enviar foto do produto: {e}")


def salvar_info_produto(supabase, dados):
    try:
        resp = (
            supabase
            .table("produtos_info")
            .upsert(
                dados,
                on_conflict="produto_id"
            )
            .execute()
        )

        return resp

    except Exception as e:
        raise Exception(f"Erro ao salvar informações do produto: {e}")