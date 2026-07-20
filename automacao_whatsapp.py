import argparse
import os
import re
import uuid

from datetime import datetime
from zoneinfo import ZoneInfo

import requests

from apscheduler.schedulers.blocking import BlockingScheduler
from dotenv import load_dotenv
from supabase import create_client

from url_utils import normalizar_base_url_publica


TZ = ZoneInfo("America/Bahia")
MENSAGEM_PADRAO = (
    "Bom dia! Por favor, informe os preços dos produtos solicitados "
    "para a cotação de hoje."
)
VARIAVEIS_SUPABASE_OBRIGATORIAS = ("SUPABASE_URL", "SUPABASE_KEY")
VARIAVEIS_WHATSAPP_ENVIO_REAL = (
    "WHATSAPP_TOKEN",
    "WHATSAPP_PHONE_NUMBER_ID",
)


def agora_brasil():
    return datetime.now(TZ)


def data_hoje_brasil():
    return agora_brasil().date()


def normalizar_hora(valor, padrao="07:00"):
    if not valor:
        return padrao

    valor = str(valor).strip()

    if len(valor) >= 5:
        return valor[:5]

    return padrao


def limpar_whatsapp(numero):
    if not numero:
        return None

    numero_limpo = re.sub(r"\D", "", str(numero))

    if numero_limpo.startswith("55"):
        return numero_limpo

    if len(numero_limpo) in [10, 11]:
        return "55" + numero_limpo

    return numero_limpo


def variaveis_faltando(config, nomes):
    return [
        nome
        for nome in nomes
        if not str(config.get(nome.lower()) or "").strip()
    ]


def mensagem_env_incompleto(variaveis, contexto):
    nomes = ", ".join(variaveis)
    return (
        f"{contexto} Informe {nomes} no arquivo .env. "
        "Use o modelo do README e não envie esse arquivo ao Git."
    )


def carregar_config_ambiente(dry_run=True):
    load_dotenv()

    config = {
        "supabase_url": os.getenv("SUPABASE_URL"),
        "supabase_key": os.getenv("SUPABASE_KEY"),
        "whatsapp_token": os.getenv("WHATSAPP_TOKEN"),
        "whatsapp_phone_number_id": os.getenv("WHATSAPP_PHONE_NUMBER_ID"),
        "whatsapp_api_version": os.getenv("WHATSAPP_API_VERSION", "v21.0"),
        "whatsapp_template_name": os.getenv(
            "WHATSAPP_TEMPLATE_NAME",
            "link_cotacao_diaria"
        ),
        "whatsapp_template_language": os.getenv(
            "WHATSAPP_TEMPLATE_LANGUAGE",
            "pt_BR"
        ),
    }

    faltando_supabase = variaveis_faltando(
        config,
        VARIAVEIS_SUPABASE_OBRIGATORIAS
    )

    if faltando_supabase:
        raise ValueError(
            mensagem_env_incompleto(
                faltando_supabase,
                "Configuração local incompleta."
            )
        )

    if not dry_run:
        faltando_whatsapp = variaveis_faltando(
            config,
            VARIAVEIS_WHATSAPP_ENVIO_REAL
        )

        if faltando_whatsapp:
            raise ValueError(
                mensagem_env_incompleto(
                    faltando_whatsapp,
                    "Envio real bloqueado."
                )
            )

    return config


def criar_cliente_supabase(config_ambiente):
    return create_client(
        config_ambiente["supabase_url"],
        config_ambiente["supabase_key"]
    )


def carregar_config_whatsapp(supabase):
    resp = (
        supabase
        .table("config_permissionarios")
        .select("*")
        .eq("id", 1)
        .limit(1)
        .execute()
    )

    if not resp.data:
        return None

    return resp.data[0]


def buscar_permissionarios_ativos(supabase):
    resp = (
        supabase
        .table("permissionarios")
        .select("id, nome, whatsapp, ativo")
        .eq("ativo", True)
        .execute()
    )

    return resp.data or []


def montar_validade_link(config, data_referencia=None):
    data_base = data_referencia or data_hoje_brasil()

    if isinstance(data_base, datetime):
        data_base = data_base.date()

    hora_limite_txt = normalizar_hora(
        config.get("hora_limite"),
        padrao="09:00"
    )
    hora_limite = datetime.strptime(hora_limite_txt, "%H:%M").time()

    return datetime.combine(data_base, hora_limite, tzinfo=TZ)


def montar_link(base_url, token):
    base_url = normalizar_base_url_publica(base_url)
    return f"{base_url}?token={token}"


def gerar_ou_atualizar_link(supabase, permissionario_id, config):
    data_hoje = data_hoje_brasil().isoformat()
    valido_ate = montar_validade_link(config)
    base_url = normalizar_base_url_publica(config.get("base_url"))

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

    return montar_link(base_url, token), valido_ate


def envio_ja_realizado(supabase, permissionario_id, data_cotacao):
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
    supabase,
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


def pode_enviar_agora(config, agora=None, avisar=True):
    agora = agora or agora_brasil()
    hora_atual = agora.strftime("%H:%M")
    hora_envio = normalizar_hora(config.get("hora_envio"), padrao="07:00")
    hora_limite = normalizar_hora(config.get("hora_limite"), padrao="09:00")

    if hora_atual < hora_envio:
        if avisar:
            print(
                f"Ainda não está no horário de envio. "
                f"Atual: {hora_atual} | Envio: {hora_envio}"
            )
        return False

    if hora_atual > hora_limite:
        if avisar:
            print(
                f"Horário limite já passou. "
                f"Atual: {hora_atual} | Limite: {hora_limite}"
            )
        return False

    return True


def montar_payload_whatsapp(
    telefone,
    nome,
    mensagem,
    link,
    valido_ate,
    config_whatsapp,
    config_ambiente
):
    template_nome = str(
        config_whatsapp.get("template_nome")
        or config_ambiente.get("whatsapp_template_name")
        or "link_cotacao_diaria"
    ).strip()

    idioma = str(
        config_whatsapp.get("idioma")
        or config_ambiente.get("whatsapp_template_language")
        or "pt_BR"
    ).strip()

    return {
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
                        {"type": "text", "text": str(nome)},
                        {"type": "text", "text": str(mensagem)},
                        {"type": "text", "text": str(link)},
                        {"type": "text", "text": valido_ate.strftime("%H:%M")}
                    ]
                }
            ]
        }
    }


def enviar_template_whatsapp(
    telefone,
    nome,
    mensagem,
    link,
    valido_ate,
    config_whatsapp,
    config_ambiente
):
    url = (
        f"https://graph.facebook.com/"
        f"{config_ambiente['whatsapp_api_version']}/"
        f"{config_ambiente['whatsapp_phone_number_id']}/messages"
    )

    headers = {
        "Authorization": f"Bearer {config_ambiente['whatsapp_token']}",
        "Content-Type": "application/json"
    }

    payload = montar_payload_whatsapp(
        telefone=telefone,
        nome=nome,
        mensagem=mensagem,
        link=link,
        valido_ate=valido_ate,
        config_whatsapp=config_whatsapp,
        config_ambiente=config_ambiente
    )

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


def automacao_whatsapp(supabase, config_ambiente, dry_run=True):
    agora = agora_brasil()
    data_hoje = agora.date().isoformat()
    hora_atual = agora.strftime("%H:%M")

    print(f"Verificando automação: {data_hoje} {hora_atual}")

    config = carregar_config_whatsapp(supabase)

    if not config:
        print("Configuração dos permissionários não encontrada.")
        print("Cadastre as configurações na tela Permissionários > Links e mensagens.")
        return

    if not config.get("ativo", False):
        print("Automação desativada.")
        return

    if not pode_enviar_agora(config):
        return

    mensagem = str(config.get("mensagem") or "").strip() or MENSAGEM_PADRAO
    permissionarios = buscar_permissionarios_ativos(supabase)

    if not permissionarios:
        print("Nenhum permissionário ativo encontrado.")
        return

    print(f"{len(permissionarios)} permissionário(s) ativo(s) encontrado(s).")

    if dry_run:
        print("Modo simulação ativo: nenhuma mensagem será enviada.")

    for p in permissionarios:
        permissionario_id = p.get("id")
        nome = str(p.get("nome") or "").strip()
        whatsapp = limpar_whatsapp(p.get("whatsapp"))

        if not permissionario_id or not nome or not whatsapp:
            print(f"Permissionário ignorado por dados incompletos: {p}")
            continue

        if envio_ja_realizado(supabase, permissionario_id, data_hoje):
            print(f"Já enviado hoje para {nome}.")
            continue

        if dry_run:
            print(f"Simulação: enviaria para {nome} - {whatsapp}")
            continue

        link = ""

        try:
            link, valido_ate = gerar_ou_atualizar_link(
                supabase=supabase,
                permissionario_id=permissionario_id,
                config=config
            )

            status_code, resposta = enviar_template_whatsapp(
                telefone=whatsapp,
                nome=nome,
                mensagem=mensagem,
                link=link,
                valido_ate=valido_ate,
                config_whatsapp=config,
                config_ambiente=config_ambiente
            )

            if status_code in [200, 201]:
                message_id = None

                try:
                    message_id = resposta.get("messages", [{}])[0].get("id")
                except Exception:
                    pass

                registrar_disparo(
                    supabase=supabase,
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
                    supabase=supabase,
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

        except Exception as erro:
            registrar_disparo(
                supabase=supabase,
                data_cotacao=data_hoje,
                permissionario_id=permissionario_id,
                permissionario_nome=nome,
                whatsapp=whatsapp or "",
                link=link,
                status="erro",
                message_id=None,
                erro=str(erro)
            )

            print(f"Erro geral para {nome}: {erro}")


def verificar_configuracao(supabase, dry_run):
    config = carregar_config_whatsapp(supabase)

    print("Configuração local carregada.")
    print(f"Modo: {'simulação' if dry_run else 'envio real'}")

    if not config:
        print("Configuração de permissionários não encontrada no Supabase.")
        print(
            "Abra a tela Permissionários > Mensagem e link e salve a configuração inicial."
        )
        return

    automacao_ativa = bool(config.get("ativo", False))
    base_url = str(config.get("base_url") or "").strip()

    print("Configuração de permissionários encontrada.")
    print(f"Automação ativa: {automacao_ativa}")
    print(f"URL base configurada: {bool(base_url)}")
    print(f"Hora de envio: {normalizar_hora(config.get('hora_envio'))}")
    print(f"Hora limite: {normalizar_hora(config.get('hora_limite'), '09:00')}")

    if not automacao_ativa:
        print("Aviso: a automação está desativada no Supabase.")

    if not base_url:
        print("Aviso: configure a URL pública do sistema com https://.")
    else:
        try:
            normalizar_base_url_publica(base_url)
        except ValueError as erro:
            print(f"Aviso: {erro}")


def criar_parser():
    parser = argparse.ArgumentParser(
        description="Automação opcional de envio de links pelo WhatsApp."
    )

    modo_envio = parser.add_mutually_exclusive_group()
    modo_envio.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Simula a execução sem enviar mensagens. É o padrão."
    )
    modo_envio.add_argument(
        "--send",
        action="store_false",
        dest="dry_run",
        help="Permite envio real pela API do WhatsApp."
    )
    parser.set_defaults(dry_run=True)

    modo_execucao = parser.add_mutually_exclusive_group()
    modo_execucao.add_argument(
        "--once",
        action="store_false",
        dest="schedule",
        help="Executa uma verificação única. É o padrão."
    )
    modo_execucao.add_argument(
        "--schedule",
        action="store_true",
        dest="schedule",
        help="Mantém a automação rodando e verifica a cada minuto."
    )
    parser.set_defaults(schedule=False)

    parser.add_argument(
        "--check",
        action="store_true",
        help="Valida as configurações sem rodar a automação."
    )

    return parser


def main():
    args = criar_parser().parse_args()
    config_ambiente = carregar_config_ambiente(dry_run=args.dry_run)
    supabase = criar_cliente_supabase(config_ambiente)

    if args.check:
        verificar_configuracao(supabase, dry_run=args.dry_run)
        return

    if args.schedule:
        scheduler = BlockingScheduler(timezone=str(TZ))
        scheduler.add_job(
            lambda: automacao_whatsapp(
                supabase=supabase,
                config_ambiente=config_ambiente,
                dry_run=args.dry_run
            ),
            "interval",
            minutes=1,
            id="envio_whatsapp_cotacao",
            replace_existing=True
        )

        print("Automação do WhatsApp iniciada.")
        print("O sistema verificará o horário de envio a cada 1 minuto.")
        print(f"Modo: {'simulação' if args.dry_run else 'envio real'}")

        scheduler.start()
        return

    automacao_whatsapp(
        supabase=supabase,
        config_ambiente=config_ambiente,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    main()
