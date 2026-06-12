import os
import re
import uuid
import requests

from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.blocking import BlockingScheduler
from supabase import create_client
from dotenv import load_dotenv


# ================= CONFIGURAÇÕES INICIAIS =================

load_dotenv()

TZ = ZoneInfo("America/Bahia")

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID")
WHATSAPP_API_VERSION = os.getenv("WHATSAPP_API_VERSION", "v21.0")

WHATSAPP_TEMPLATE_NAME = os.getenv("WHATSAPP_TEMPLATE_NAME", "link_cotacao_diaria")
WHATSAPP_TEMPLATE_LANGUAGE = os.getenv("WHATSAPP_TEMPLATE_LANGUAGE", "pt_BR")


if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("SUPABASE_URL e SUPABASE_KEY não foram configurados no .env.")

if not WHATSAPP_TOKEN or not WHATSAPP_PHONE_NUMBER_ID:
    raise ValueError(
        "Configure WHATSAPP_TOKEN e WHATSAPP_PHONE_NUMBER_ID no .env."
    )


supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ================= FUNÇÕES DE DATA E HORA =================

def agora_brasil():
    return datetime.now(TZ)


def data_hoje_brasil():
    return agora_brasil().date()


def normalizar_hora(valor, padrao="07:00"):
    """
    Recebe hora como texto vindo do banco, exemplo:
    07:00:00, 07:00 ou vazio.
    Retorna HH:MM.
    """
    if not valor:
        return padrao

    valor = str(valor).strip()

    if len(valor) >= 5:
        return valor[:5]

    return padrao


# ================= FUNÇÕES DE WHATSAPP =================

def limpar_whatsapp(numero):
    """
    Limpa o número e garante o DDI 55.
    Exemplo:
    74999999999 -> 5574999999999
    """
    if not numero:
        return None

    numero_limpo = re.sub(r"\D", "", str(numero))

    if numero_limpo.startswith("55"):
        return numero_limpo

    if len(numero_limpo) in [10, 11]:
        return "55" + numero_limpo

    return numero_limpo


def enviar_template_whatsapp(telefone, nome, mensagem, link, valido_ate, config):
    """
    Envia mensagem template pela API oficial do WhatsApp Cloud API.

    O template precisa ter 4 variáveis:
    {{1}} nome
    {{2}} mensagem
    {{3}} link
    {{4}} hora de validade
    """

    url = (
        f"https://graph.facebook.com/"
        f"{WHATSAPP_API_VERSION}/"
        f"{WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }

    template_nome = str(
        config.get("template_nome")
        or WHATSAPP_TEMPLATE_NAME
        or "link_cotacao_diaria"
    ).strip()

    idioma = str(
        config.get("idioma")
        or WHATSAPP_TEMPLATE_LANGUAGE
        or "pt_BR"
    ).strip()

    hora_validade = valido_ate.strftime("%H:%M")

    payload = {
        "messaging_product": "whatsapp",
        "to": telefone,
        "type": "template",
        "template": {
            "name": template_nome,
            "language": {
                "code": idioma
            },
            "components": [
                {
                    "type": "body",
                    "parameters": [
                        {
                            "type": "text",
                            "text": str(nome)
                        },
                        {
                            "type": "text",
                            "text": str(mensagem)
                        },
                        {
                            "type": "text",
                            "text": str(link)
                        },
                        {
                            "type": "text",
                            "text": str(hora_validade)
                        }
                    ]
                }
            ]
        }
    }

    resposta = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )

    try:
        resposta_json = resposta.json()
    except Exception:
        resposta_json = {"resposta": resposta.text}

    return resposta.status_code, resposta_json


# ================= CONFIGURAÇÃO DO SISTEMA =================

def carregar_config_whatsapp():
    """
    Usa a mesma tabela da tela de Permissionários.
    Essa tabela é salva pelo permissionarios.py.
    """
    resp = (
        supabase
        .table("config_permissionarios")
        .select("*")
        .eq("id", 1)
        .execute()
    )

    if not resp.data:
        return None

    return resp.data[0]


def buscar_permissionarios_ativos():
    resp = (
        supabase
        .table("permissionarios")
        .select("id, nome, whatsapp, ativo")
        .eq("ativo", True)
        .execute()
    )

    return resp.data or []


# ================= LINKS DOS PERMISSIONÁRIOS =================

def montar_validade_link(config):
    data_hoje = data_hoje_brasil()

    hora_limite_txt = normalizar_hora(
        config.get("hora_limite"),
        padrao="09:00"
    )

    hora_limite = datetime.strptime(hora_limite_txt, "%H:%M").time()

    valido_ate = datetime.combine(
        data_hoje,
        hora_limite,
        tzinfo=TZ
    )

    return valido_ate


def gerar_ou_atualizar_link(permissionario_id, config):
    data_hoje = data_hoje_brasil().isoformat()
    valido_ate = montar_validade_link(config)

    base_url = str(config.get("base_url") or "").strip().rstrip("/")

    if not base_url:
        raise ValueError("A URL base do sistema não está configurada.")

    resp_link = (
        supabase
        .table("links_permissionarios")
        .select("*")
        .eq("permissionario_id", int(permissionario_id))
        .eq("data", data_hoje)
        .limit(1)
        .execute()
    )

    if resp_link.data:
        link_existente = resp_link.data[0]
        token = link_existente["token"]

        (
            supabase
            .table("links_permissionarios")
            .update({
                "valido_ate": valido_ate.isoformat(),
                "usado": False
            })
            .eq("id", link_existente["id"])
            .execute()
        )

    else:
        token = uuid.uuid4().hex

        (
            supabase
            .table("links_permissionarios")
            .insert({
                "permissionario_id": int(permissionario_id),
                "data": data_hoje,
                "token": token,
                "valido_ate": valido_ate.isoformat(),
                "usado": False
            })
            .execute()
        )

    # Mesmo padrão usado na geração manual dos links
    link = f"{base_url}?token={token}"

    return link, valido_ate


# ================= LOGS DE DISPARO =================

def envio_ja_realizado(permissionario_id, data_cotacao):
    resp = (
        supabase
        .table("disparos_whatsapp")
        .select("id, status")
        .eq("permissionario_id", int(permissionario_id))
        .eq("data_cotacao", data_cotacao)
        .eq("status", "enviado")
        .execute()
    )

    return bool(resp.data)


def registrar_disparo(
    data_cotacao,
    permissionario_id,
    permissionario_nome,
    whatsapp,
    link,
    status,
    message_id=None,
    erro=None
):
    dados = {
        "data_cotacao": data_cotacao,
        "permissionario_id": int(permissionario_id),
        "permissionario_nome": permissionario_nome,
        "whatsapp": whatsapp,
        "link": link,
        "status": status,
        "message_id": message_id,
        "erro": erro,
        "enviado_em": agora_brasil().isoformat()
    }

    resp = (
        supabase
        .table("disparos_whatsapp")
        .select("id")
        .eq("data_cotacao", data_cotacao)
        .eq("permissionario_id", int(permissionario_id))
        .limit(1)
        .execute()
    )

    if resp.data:
        registro_id = resp.data[0]["id"]

        (
            supabase
            .table("disparos_whatsapp")
            .update(dados)
            .eq("id", registro_id)
            .execute()
        )

    else:
        (
            supabase
            .table("disparos_whatsapp")
            .insert(dados)
            .execute()
        )


# ================= REGRA DE HORÁRIO =================

def pode_enviar_agora(config):
    """
    Envia a partir do horário configurado, mas antes do horário limite.
    Isso evita depender exatamente do minuto correto.
    """

    agora = agora_brasil()

    hora_atual = agora.strftime("%H:%M")

    hora_envio = normalizar_hora(
        config.get("hora_envio"),
        padrao="07:00"
    )

    hora_limite = normalizar_hora(
        config.get("hora_limite"),
        padrao="09:00"
    )

    if hora_atual < hora_envio:
        print(
            f"Ainda não está no horário de envio. "
            f"Atual: {hora_atual} | Envio: {hora_envio}"
        )
        return False

    if hora_atual > hora_limite:
        print(
            f"Horário limite já passou. "
            f"Atual: {hora_atual} | Limite: {hora_limite}"
        )
        return False

    return True


# ================= AUTOMAÇÃO PRINCIPAL =================

def automacao_whatsapp():
    agora = agora_brasil()
    data_hoje = agora.date().isoformat()
    hora_atual = agora.strftime("%H:%M")

    print(f"Verificando automação: {data_hoje} {hora_atual}")

    config = carregar_config_whatsapp()

    if not config:
        print("Configuração dos permissionários não encontrada.")
        print("Cadastre as configurações na tela Permissionários > Links e mensagens.")
        return

    if not config.get("ativo", False):
        print("Automação desativada.")
        return

    if not pode_enviar_agora(config):
        return

    mensagem = str(config.get("mensagem") or "").strip()

    if not mensagem:
        mensagem = (
            "Bom dia! Por favor, informe os preços dos produtos solicitados "
            "para a cotação de hoje."
        )

    permissionarios = buscar_permissionarios_ativos()

    if not permissionarios:
        print("Nenhum permissionário ativo encontrado.")
        return

    print(f"{len(permissionarios)} permissionário(s) ativo(s) encontrado(s).")

    for p in permissionarios:
        permissionario_id = p.get("id")
        nome = str(p.get("nome") or "").strip()
        whatsapp = limpar_whatsapp(p.get("whatsapp"))

        if not permissionario_id or not nome or not whatsapp:
            print(f"Permissionário ignorado por dados incompletos: {p}")
            continue

        if envio_ja_realizado(permissionario_id, data_hoje):
            print(f"Já enviado hoje para {nome}.")
            continue

        link = ""

        try:
            link, valido_ate = gerar_ou_atualizar_link(
                permissionario_id,
                config
            )

            status_code, resposta = enviar_template_whatsapp(
                telefone=whatsapp,
                nome=nome,
                mensagem=mensagem,
                link=link,
                valido_ate=valido_ate,
                config=config
            )

            if status_code in [200, 201]:
                message_id = None

                try:
                    message_id = resposta.get("messages", [{}])[0].get("id")
                except Exception:
                    pass

                registrar_disparo(
                    data_cotacao=data_hoje,
                    permissionario_id=permissionario_id,
                    permissionario_nome=nome,
                    whatsapp=whatsapp,
                    link=link,
                    status="enviado",
                    message_id=message_id,
                    erro=None
                )

                print(f"Enviado para {nome} - {whatsapp}")

            else:
                registrar_disparo(
                    data_cotacao=data_hoje,
                    permissionario_id=permissionario_id,
                    permissionario_nome=nome,
                    whatsapp=whatsapp,
                    link=link,
                    status="erro",
                    message_id=None,
                    erro=str(resposta)
                )

                print(f"Erro ao enviar para {nome}: {resposta}")

        except Exception as e:
            registrar_disparo(
                data_cotacao=data_hoje,
                permissionario_id=permissionario_id,
                permissionario_nome=nome,
                whatsapp=whatsapp or "",
                link=link,
                status="erro",
                message_id=None,
                erro=str(e)
            )

            print(f"Erro geral para {nome}: {e}")


# ================= EXECUÇÃO AGENDADA =================

if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone=str(TZ))

    scheduler.add_job(
        automacao_whatsapp,
        "interval",
        minutes=1,
        id="envio_whatsapp_cotacao",
        replace_existing=True
    )

    print("Automação do WhatsApp iniciada.")
    print("O sistema verificará o horário de envio a cada 1 minuto.")

    scheduler.start()