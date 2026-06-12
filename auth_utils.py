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
    senha_salva = str(senha_salva or "")
    return senha_salva.startswith(f"{HASH_PREFIX}$")


def verificar_senha(senha_digitada, senha_salva):
    """
    Verifica senha criptografada.
    Também aceita senha antiga em texto puro para não travar usuários antigos.
    """
    senha_digitada = str(senha_digitada or "")
    senha_salva = str(senha_salva or "")

    if senha_salva.startswith(f"{HASH_PREFIX}$"):
        try:
            _, iteracoes, salt, hash_salvo = senha_salva.split("$", 3)

            hash_teste = hashlib.pbkdf2_hmac(
                "sha256",
                senha_digitada.encode("utf-8"),
                salt.encode("utf-8"),
                int(iteracoes)
            ).hex()

            return hmac.compare_digest(hash_teste, hash_salvo)

        except Exception:
            return False

    # Compatibilidade com usuários antigos que ainda estão com senha sem hash.
    return hmac.compare_digest(senha_digitada, senha_salva)


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
        resp = (
            supabase
            .table("usuarios")
            .select("*")
            .eq("usuario", usuario)
            .limit(1)
            .execute()
        )

        dados = resp.data or []

        if not dados:
            return None

        usuario_db = dados[0]
        senha_salva = str(usuario_db.get("senha", ""))

        if not verificar_senha(senha, senha_salva):
            return None

        # Migração automática: se a senha estava sem hash, salva com hash depois do login correto.
        if not senha_esta_com_hash(senha_salva):
            try:
                senha_hash = gerar_hash_senha(senha)
                supabase.table("usuarios").update({
                    "senha": senha_hash
                }).eq("id", int(usuario_db["id"])).execute()
            except Exception:
                pass

        return {
            "id": usuario_db.get("id"),
            "nome": usuario_db.get("nome"),
            "usuario": usuario_db.get("usuario"),
            "nivel": usuario_db.get("nivel")
        }

    except Exception:
        return None
