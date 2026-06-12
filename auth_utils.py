import hashlib
import hmac
import secrets


HASH_PREFIX = "pbkdf2_sha256"
ITERACOES_PADRAO = 260000


def gerar_hash_senha(senha, iteracoes=ITERACOES_PADRAO):
    """
    Gera hash seguro para senha usando PBKDF2-SHA256.
    Formato salvo no banco:
    pbkdf2_sha256$iteracoes$salt$hash
    """
    senha = str(senha or "")
    salt = secrets.token_hex(16)

    hash_bytes = hashlib.pbkdf2_hmac(
        "sha256",
        senha.encode("utf-8"),
        salt.encode("utf-8"),
        int(iteracoes)
    )

    hash_hex = hash_bytes.hex()
    return f"{HASH_PREFIX}${int(iteracoes)}${salt}${hash_hex}"


def senha_esta_com_hash(senha_salva):
    senha_salva = str(senha_salva or "").strip()
    return senha_salva.startswith(f"{HASH_PREFIX}$")


def verificar_senha(senha_digitada, senha_salva):
    """
    Verifica senha criptografada.
    Também aceita senha antiga em texto puro para não bloquear usuários antigos.
    """
    senha_digitada = str(senha_digitada or "")
    senha_salva = str(senha_salva or "")

    senha_salva_limpa = senha_salva.strip()

    # Senha já protegida com hash.
    if senha_salva_limpa.startswith(f"{HASH_PREFIX}$"):
        try:
            _, iteracoes, salt, hash_salvo = senha_salva_limpa.split("$", 3)

            hash_teste = hashlib.pbkdf2_hmac(
                "sha256",
                senha_digitada.encode("utf-8"),
                salt.encode("utf-8"),
                int(iteracoes)
            ).hex()

            return hmac.compare_digest(hash_teste, hash_salvo)

        except Exception:
            return False

    # Compatibilidade com senha antiga em texto puro.
    # Aqui aceitamos com e sem espaços, para evitar erro por espaço salvo/digitado.
    return (
        hmac.compare_digest(senha_digitada, senha_salva) or
        hmac.compare_digest(senha_digitada.strip(), senha_salva_limpa)
    )


def buscar_usuario_login(supabase, usuario):
    """
    Busca usuário de forma mais tolerante.
    Primeiro tenta igual ao banco. Se não achar, busca todos e compara ignorando maiúsculas/minúsculas.
    """
    usuario = str(usuario or "").strip()

    if not usuario:
        return None

    # 1) Busca exata
    resp = (
        supabase
        .table("usuarios")
        .select("*")
        .eq("usuario", usuario)
        .limit(1)
        .execute()
    )

    dados = resp.data or []

    if dados:
        return dados[0]

    # 2) Busca tolerante para casos como Admin/admin ou espaço no banco
    resp = (
        supabase
        .table("usuarios")
        .select("*")
        .execute()
    )

    todos = resp.data or []
    usuario_norm = usuario.lower().strip()

    for item in todos:
        usuario_banco = str(item.get("usuario", "") or "").lower().strip()

        if usuario_banco == usuario_norm:
            return item

    return None


def verificar_login_seguro(supabase, usuario, senha):
    """
    Faz login usando hash de senha.
    Se a senha antiga estiver em texto puro e o login der certo,
    o sistema atualiza automaticamente para hash.
    """
    usuario = str(usuario or "").strip()
    senha = str(senha or "")

    if not usuario or not senha:
        return None

    try:
        usuario_db = buscar_usuario_login(supabase, usuario)

        if not usuario_db:
            return None

        senha_salva = str(usuario_db.get("senha", "") or "")

        if not verificar_senha(senha, senha_salva):
            return None

        # Migração automática: se a senha estava sem hash, salva com hash depois do login correto.
        if not senha_esta_com_hash(senha_salva):
            try:
                senha_hash = gerar_hash_senha(senha.strip())
                supabase.table("usuarios").update({
                    "senha": senha_hash
                }).eq("id", int(usuario_db["id"])).execute()
            except Exception:
                pass

        nivel = str(usuario_db.get("nivel", "") or "").strip()

        if nivel == "visitante":
            nivel = "requisitante"

        return {
            "id": usuario_db.get("id"),
            "nome": usuario_db.get("nome"),
            "usuario": usuario_db.get("usuario"),
            "nivel": nivel
        }

    except Exception:
        return None
