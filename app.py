# ===================== IMPORTS =====================
import streamlit as st

from db import conectar_supabase

from utils import corrigir_classe

from dados_utils import (
    carregar_produtos,
    contar_solicitacoes_pendentes,
    registrar_acao
)

from analise_precos import tela_analise_precos
from observacoes_produtos import tela_observacoes_produtos
from posts_analiticos import tela_posts_analiticos
from tela_produtos_info import tela_produtos_info
from post_produto_unitario import tela_post_produto_unitario
from tela_acompanhamento import tela_acompanhamento
from tela_cotacao_dia import tela_cotacao_dia
from tela_importacoes_excel import tela_importacoes_excel
from tela_sobre_produtos import tela_sobre_produtos
from tela_visualizar_dados import tela_visualizar_dados
from relatorio_diario import tela_relatorio_diario
from relatorio_semanal import tela_relatorio_semanal
from relatorio_semestral import tela_relatorio_semestral
from post_destaques_dia import tela_post_destaques_dia
from solicitacoes import tela_solicitacoes
from auth_utils import (
    MAX_TENTATIVAS_LOGIN,
    limpar_tentativas_login,
    registrar_falha_login,
    segundos_bloqueio_login,
    verificar_login_seguro
)
from usuarios import tela_cadastro_usuarios
from produtos import tela_cadastro_produtos

#from relatorio_mensal import tela_relatorio_mensal

from permissionarios import (
    tela_permissionarios_admin,
    tela_envio_links_permissionarios,
    tela_publica_permissionario,
    tela_respostas_permissionarios
)
# ====================================================

PERMISSOES_POR_TELA = {
    "Cadastro de Usuários": {"admin"},
    "Cadastro de Produtos": {"admin"},
    "Permissionários": {"admin"},
    "Importações por Excel": {"admin"},
    "Relatório Diário": {"admin", "convidado"},
    "Relatório Semanal": {"admin", "convidado"},
    "Relatório Mensal": {"admin", "convidado"},
    "Acompanhamento": {"admin"},
    "Cotação do Dia": {"admin", "cotacao"},
    "Envio de Links": {"admin", "cotacao"},
    "Respostas dos Permissionários": {"admin", "cotacao"},
    "Análise de Preços": {"admin", "cotacao"},
    "Post Destaques do Dia": {"admin", "cotacao", "convidado"},
    "Relatório Semestral": {"admin", "cotacao", "convidado"},
    "Posts Analíticos": {"admin", "cotacao"},
    "Post Unitário do Produto": {"admin", "cotacao"},
    "Informações dos Produtos": {"admin", "cotacao"},
    "Observações de Produtos": {"admin", "cotacao"},
    "Solicitações": {"admin", "cotacao", "requisitante"},
    "Visualizar Dados": {"admin", "cotacao", "requisitante", "convidado"},
    "Sobre os Produtos": {"admin", "cotacao", "requisitante"},
}


def usuario_pode_acessar_tela(nivel, tela):
    niveis_permitidos = PERMISSOES_POR_TELA.get(tela)

    if not niveis_permitidos:
        return True

    return nivel in niveis_permitidos

# ================== CONFIG ==========================
st.set_page_config(
    page_title="Sistema de Cotação",
    layout="wide"
)
# ====================================================

# ================== CONEXÃO =========================
supabase = conectar_supabase()
# ====================================================

# ================== TELA PÚBLICA POR TOKEN =========================
token_publico = st.query_params.get("token", None)

if token_publico:
    tela_publica_permissionario(supabase, token_publico)
    st.stop()
# ====================================================

# ================== ESTADO INICIAL ==========================
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.nome = None
    st.session_state.nivel = None
# ====================================================

# ================== SESSÃO ==========================
for k in [
    "msg",
    "msg_cotacao",
    "confirmar_exclusao",
    "confirmar_edicao",
    "confirmar_cotacao",
    "confirmar_usuario",
    "confirmar_edicao_usuario",
    "confirmar_exclusao_usuario",
    "confirmar_cadastro_produto"
]:
    if k not in st.session_state:
        st.session_state[k] = False

if "data_cotacao_atual" not in st.session_state:
    st.session_state.data_cotacao_atual = ""
# ====================================================

# ================== LOGIN ==========================
if not st.session_state.logado:

    # ---------- ESTILO DA TELA DE LOGIN ----------
    st.markdown(
        """
        <style>
        .login-container {
            max-width: 900px;
            margin: 20px auto 10px auto;
            padding: 10px 0 5px 0;
            text-align: center;
            background: transparent;
            box-shadow: none;
            border-radius: 0;
        }
    
        .login-title {
            font-size: 42px;
            font-weight: 700;
            margin-bottom: 6px;
        }
    
        .login-subtitle {
            font-size: 18px;
            margin-bottom: 10px;
            white-space: nowrap;
        }
    
        .login-footer {
            text-align: center;
            font-size: 11px;
            opacity: 0.8;
            margin-top: 28px;
        }
    
        div.stButton > button {
            border-radius: 10px;
            height: 42px;
            font-weight: 600;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    # ---------- CABEÇALHO ----------
    st.markdown(
        """
        <div class="login-container">
            <div class="login-title">📊 Sistema de Cotação</div>
            <div class="login-subtitle">
                Acesso restrito para registro, acompanhamento e consulta de cotações.
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    # ---------- FORMULÁRIO ----------
    segundos_bloqueio = segundos_bloqueio_login(st.session_state)
    login_bloqueado = segundos_bloqueio > 0

    if login_bloqueado:
        minutos_bloqueio = max(1, (segundos_bloqueio + 59) // 60)
        st.warning(
            "Muitas tentativas inválidas. "
            f"Tente novamente em {minutos_bloqueio} minuto(s)."
        )

    with st.form("form_login"):
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")

        entrar = st.form_submit_button(
            "Entrar",
            disabled=login_bloqueado
        )

        if entrar and not login_bloqueado:

            resultado = verificar_login_seguro(supabase, usuario, senha)

            if resultado:
                limpar_tentativas_login(st.session_state)
                st.session_state.logado = True
                st.session_state.nome = resultado["nome"]
                st.session_state.nivel = resultado["nivel"]

                st.rerun()

            else:
                bloqueio_restante = registrar_falha_login(st.session_state)
                st.error("Usuário ou senha inválidos.")

                if bloqueio_restante > 0:
                    st.warning(
                        "Limite de tentativas atingido. "
                        "Aguarde 5 minutos para tentar novamente."
                    )
                else:
                    tentativas = int(
                        st.session_state.get(
                            "login_tentativas_falhas",
                            0
                        ) or 0
                    )
                    restantes = max(0, MAX_TENTATIVAS_LOGIN - tentativas)

                    if restantes <= 2:
                        st.warning(
                            f"Tentativas restantes: {restantes}."
                        )

    # ---------- INFORMAÇÃO EXTRA ----------
    st.markdown(
        """
        <div class="login-footer">
            Sistema interno de apoio ao acompanhamento de preços e relatórios<br>
            Versão 1.0<br>
            © 2026 - Todos os direitos reservados.
        </div>
        """,
        unsafe_allow_html=True
    )

    st.stop()
# ====================================================

# ================== SISTEMA ==========================
if st.session_state.logado:

    nivel = st.session_state.get("nivel", "")

    qtd_solicitacoes_pendentes = 0

    if nivel == "admin":
        qtd_solicitacoes_pendentes = contar_solicitacoes_pendentes(supabase)

    # ================= MENUS POR NÍVEL =================
    if nivel == "admin":
        menu = [
            "Início",
            "Cadastro de Usuários",
            "Cadastro de Produtos",
            "Solicitações",
            "Importações por Excel",
            "Sobre os Produtos",
            "Permissionários",
            "Respostas dos Permissionários",
            "Cotação do Dia",
            "Visualizar Dados",
            "Análise de Preços",
            "Posts Analíticos",
            "Post Destaques do Dia",
            "Relatório Diário",
            "Relatório Semanal",
            #"Relatório Mensal",
            "Relatório Semestral",
            "Post Unitário do Produto",
            "Informações dos Produtos",
            "Observações de Produtos",
            "Acompanhamento"
        ]

    elif nivel == "cotacao":
        menu = [
            "Início",
            "Cotação do Dia",
            "Visualizar Dados",
            "Envio de Links",
            "Sobre os Produtos",
            "Solicitações",
            "Respostas dos Permissionários"
        ]

    elif nivel == "requisitante":
        menu = [
            "Início",
            "Solicitações",
            "Visualizar Dados",
            "Sobre os Produtos"
        ]

    elif nivel == "convidado":
        menu = [
            "Início",
            "Visualizar Dados",
            #"Relatório Diário",
            "Relatório Semanal",
            "Relatório Mensal",
            "Relatório Semestral",
            "Post Destaques do Dia"
        ]

    else:
        menu = ["Início"]

    # ================= ESTADO DA NAVEGAÇÃO =================
    if "opcao_menu" not in st.session_state:
        st.session_state.opcao_menu = "Início"

    if st.session_state.opcao_menu not in menu:
        st.session_state.opcao_menu = "Início"

    # ================= FUNÇÕES DE NAVEGAÇÃO =================
    def abrir_pagina_cotacao(pagina):
        st.session_state.opcao_menu = pagina

    def voltar_menu_cotacao():
        st.session_state.opcao_menu = "Início"

    def sair_sistema():
        st.session_state.clear()

    # ========================================================
    # NÍVEL COTAÇÃO: SEM MENU LATERAL
    # ========================================================
    if nivel == "cotacao":

        st.markdown(
            """
            <style>
            /* Botão de voltar das páginas */
            .st-key-btn_voltar_menu_cotacao {
                position: fixed;
                top: 80px;
                left: 18px;
                z-index: 999999;
                width: fit-content;
            }

            .st-key-btn_voltar_menu_cotacao button {
                width: 52px !important;
                height: 52px !important;
                min-height: 52px !important;
                border-radius: 50% !important;
                border: 2px solid #4f98b3 !important;
                background: rgba(235, 248, 252, 0.95) !important;
                color: #245d72 !important;
                font-size: 27px !important;
                font-weight: bold !important;
                padding: 0 !important;
                box-shadow: 0 5px 14px rgba(38, 92, 112, 0.25) !important;
                transition: all 0.18s ease !important;
            }

            .st-key-btn_voltar_menu_cotacao button:hover {
                background: #d4edf5 !important;
                color: #123f50 !important;
                border-color: #2d7894 !important;
                transform: translateX(-3px) scale(1.05) !important;
                box-shadow: 0 7px 18px rgba(38, 92, 112, 0.32) !important;
            }
            </style>
            """,
            unsafe_allow_html=True
        )

        opcao = st.session_state.opcao_menu

        # Dentro de uma página, mostra somente a seta de retorno
        if opcao != "Início":
            st.button(
                "←",
                key="btn_voltar_menu_cotacao",
                help="Voltar ao menu principal",
                on_click=voltar_menu_cotacao
            )

    # ========================================================
    # OUTROS NÍVEIS: CONTINUAM COM MENU LATERAL
    # ========================================================
    else:

        st.sidebar.title("📌 Menu")

        def formatar_menu(item):
            if (
                item == "Solicitações"
                and nivel == "admin"
                and qtd_solicitacoes_pendentes > 0
            ):
                return f"Solicitações 🔴 ({qtd_solicitacoes_pendentes})"

            return item

        opcao = st.sidebar.selectbox(
            "Opções",
            menu,
            key="opcao_menu",
            format_func=formatar_menu
        )

        st.sidebar.write(f"👤 {st.session_state.get('nome', '')}")
        st.sidebar.write(f"🔑 {nivel}")

        st.sidebar.button(
            "🚪 Sair",
            key="btn_sair_sidebar",
            on_click=sair_sistema
        )

    if not usuario_pode_acessar_tela(nivel, opcao):
        st.error("Acesso restrito.")
        st.stop()

    # ================= FUNDO DA TELA INICIAL =================
    if opcao == "Início":
        st.markdown(
            """
            <style>
            .stApp {
                background-image: url(
                    "https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExeGZhcHBta2hsdTh2bmY0Y3h3dWUwMW40eXNiMGozOW1rYjRmNGtvZiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3bsn2kadghWrYMXneO/giphy.gif"
                );
                background-repeat: no-repeat;
                background-position: center;
                background-size: cover;
                background-attachment: fixed;
            }

            .stApp::before {
                content: "";
                position: fixed;
                inset: 0;
                background: rgba(255, 255, 255, 0.45);
                pointer-events: none;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
# ====================================================

# ================== TELAS ==========================   

    # ================== INÍCIO
    if opcao == "Início":

        # ==================================================
        # MENU PRINCIPAL DO NÍVEL COTAÇÃO
        # ==================================================
        if nivel == "cotacao":

            nome_usuario = st.session_state.get("nome", "Usuário")

            st.markdown(
                """
                <style>
                /* Largura geral da página */
                .block-container {
                    max-width: 1180px;
                    padding-top: 2.5rem;
                    padding-bottom: 3rem;
                }

                /* Caixa principal do menu */
                .st-key-menu_cotacao_box {
                    background: rgba(255, 255, 255, 0.42);
                    border: 1px solid rgba(190, 215, 225, 0.65);
                    border-radius: 24px;
                    padding: 28px 32px 24px 32px;
                    box-shadow: 0 12px 35px rgba(41, 79, 92, 0.14);
                    backdrop-filter: blur(7px);
                }

                /* Título do menu */
                .titulo-menu-cotacao {
                    text-align: center;
                    color: #244854;
                    font-size: 32px;
                    font-weight: 750;
                    margin-bottom: 4px;
                }

                /* Saudação */
                .saudacao-menu-cotacao {
                    text-align: center;
                    color: #3f6570;
                    font-size: 18px;
                    font-weight: 600;
                    margin-bottom: 5px;
                }

                /* Instrução */
                .instrucao-menu-cotacao {
                    text-align: center;
                    color: #718a91;
                    font-size: 14px;
                    margin-bottom: 20px;
                }

                /* Botões do menu */
                .st-key-menu_cotacao_box div[data-testid="stButton"] > button {
                    width: 100%;
                    min-height: 68px;
                    border-radius: 14px;
                    border: 1px solid #c8dfe6;
                    background: linear-gradient(
                        135deg,
                        #edf7fa 0%,
                        #dceef3 100%
                    );
                    color: #285461;
                    font-size: 15px;
                    font-weight: 650;
                    padding: 10px 12px;
                    white-space: normal;
                    box-shadow: 0 4px 10px rgba(50, 91, 105, 0.10);
                    transition: all 0.18s ease;
                }

                /* Efeito ao passar o mouse */
                .st-key-menu_cotacao_box div[data-testid="stButton"] > button:hover {
                    background: linear-gradient(
                        135deg,
                        #dceff4 0%,
                        #cce5ec 100%
                    );
                    color: #173f4b;
                    border-color: #9fc8d3;
                    transform: translateY(-2px);
                    box-shadow: 0 7px 15px rgba(50, 91, 105, 0.16);
                }

                /* Cor ao clicar */
                .st-key-menu_cotacao_box div[data-testid="stButton"] > button:active {
                    transform: translateY(0);
                }

                /* Espaçamento entre os botões */
                .st-key-menu_cotacao_box div[data-testid="stButton"] {
                    margin-bottom: 4px;
                }

                /* Botão de sair */
                .st-key-menu_sair_cotacao button {
                    background: rgba(255, 255, 255, 0.35) !important;
                    color: #2f6f86 !important;
                    border: 2px solid #5a9db5 !important;
                    border-radius: 12px !important;
                    min-height: 42px !important;
                    font-size: 14px !important;
                    font-weight: 650 !important;
                    box-shadow: none !important;
                }

                .st-key-menu_sair_cotacao button:hover {
                    background: rgba(221, 241, 247, 0.75) !important;
                    color: #174d61 !important;
                    border: 2px solid #397f99 !important;
                    transform: none !important;
                    box-shadow: 0 4px 10px rgba(50, 91, 105, 0.12) !important;
                }

                /* Ajustes para telas menores */
                @media (max-width: 768px) {
                    .block-container {
                        padding-left: 12px;
                        padding-right: 12px;
                        padding-top: 1rem;
                    }

                    .st-key-menu_cotacao_box {
                        padding: 20px 16px;
                        border-radius: 18px;
                    }

                    .titulo-menu-cotacao {
                        font-size: 25px;
                    }

                    .saudacao-menu-cotacao {
                        font-size: 16px;
                    }

                    .st-key-menu_cotacao_box div[data-testid="stButton"] > button {
                        min-height: 60px;
                        font-size: 14px;
                    }
                }
                </style>
                """,
                unsafe_allow_html=True
            )

            with st.container(
                border=True,
                key="menu_cotacao_box"
            ):

                st.markdown(
                    """
                    <div class="titulo-menu-cotacao">
                        Sistema de Cotação
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                st.markdown(
                    f"""
                    <div class="saudacao-menu-cotacao">
                        Olá, {nome_usuario}
                    </div>

                    <div class="instrucao-menu-cotacao">
                        Selecione uma das opções abaixo para continuar.
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                # Primeira linha
                col1, col2, col3 = st.columns(3, gap="medium")

                with col1:
                    st.button(
                        "📊 Cotação do Dia",
                        key="menu_cotacao_dia",
                        width="stretch",
                        on_click=abrir_pagina_cotacao,
                        args=("Cotação do Dia",)
                    )

                with col2:
                    st.button(
                        "📋 Visualizar Dados",
                        key="menu_visualizar_dados",
                        width="stretch",
                        on_click=abrir_pagina_cotacao,
                        args=("Visualizar Dados",)
                    )

                with col3:
                    st.button(
                        "📨 Envio de Links",
                        key="menu_envio_links",
                        width="stretch",
                        on_click=abrir_pagina_cotacao,
                        args=("Envio de Links",)
                    )

                # Segunda linha
                col4, col5, col6 = st.columns(3, gap="medium")

                with col4:
                    st.button(
                        "📦 Sobre os Produtos",
                        key="menu_sobre_produtos",
                        width="stretch",
                        on_click=abrir_pagina_cotacao,
                        args=("Sobre os Produtos",)
                    )

                with col5:
                    st.button(
                        "📨 Solicitações",
                        key="menu_solicitacoes",
                        width="stretch",
                        on_click=abrir_pagina_cotacao,
                        args=("Solicitações",)
                    )

                with col6:
                    st.button(
                        "🧑‍🌾 Respostas dos Permissionários",
                        key="menu_respostas_permissionarios",
                        width="stretch",
                        on_click=abrir_pagina_cotacao,
                        args=("Respostas dos Permissionários",)
                    )

                # Terceira linha: envio de links
                #link1, link2, link3 = st.columns([1, 1, 1], gap="medium")

                
                st.write("")

                sair1, sair2, sair3 = st.columns([1.4, 1, 1.4])

                with sair2:
                    st.button(
                        "Sair do sistema",
                        key="menu_sair_cotacao",
                        width="stretch",
                        on_click=sair_sistema
                    )

        # ==================================================
        # INÍCIO DOS OUTROS NÍVEIS
        # ==================================================
        else:
            st.title("📊 Sistema de Cotação")
            st.markdown(
                "Utilize o menu lateral para navegar pelas funcionalidades."
            )

    # =====================

    # ================== CADASTRO DE USUÁRIOS
    elif opcao == "Cadastro de Usuários":

        if nivel != "admin":
            st.error("Acesso restrito ao administrador.")
            st.stop()

        tela_cadastro_usuarios(
            supabase,
            lambda acao, tela="Cadastro de Usuários", detalhes="", arquivo_url="": registrar_acao(
                supabase,
                acao,
                tela,
                detalhes,
                arquivo_url
            )
        )

    elif opcao == "Cadastro de Produtos":

        if nivel != "admin":
            st.error("Acesso restrito ao administrador.")
            st.stop()

        tela_cadastro_produtos(
            supabase,
            lambda acao, tela="Cadastro de Produtos", detalhes="", arquivo_url="": registrar_acao(
                supabase,
                acao,
                tela,
                detalhes,
                arquivo_url
            )
        )

    elif opcao == "Permissionários":

        if nivel != "admin":
            st.error("Acesso restrito ao administrador.")
            st.stop()

        tela_permissionarios_admin(
            supabase,
            lambda: carregar_produtos(supabase),
            corrigir_classe,
            lambda acao, tela="", detalhes="", arquivo_url="": registrar_acao(
                supabase,
                acao,
                tela,
                detalhes,
                arquivo_url
            )
        )

    # ===================== ENVIO DE LINKS
    elif opcao == "Envio de Links":

        if nivel not in ["admin", "cotacao"]:
            st.error("Acesso restrito.")
            st.stop()

        tela_envio_links_permissionarios(supabase)

    # ===================== RESPOSTAS DOS PERMISSIONÁRIOS
    elif opcao == "Respostas dos Permissionários":

        if nivel not in ["admin", "cotacao"]:
            st.error("Acesso restrito.")
            st.stop()

        tela_respostas_permissionarios(supabase)

    # ===================== COTAÇÃO
    elif opcao == "Cotação do Dia":

        tela_cotacao_dia(supabase)

    # ===================== VISUALIZAR DADOS 
    elif opcao == "Visualizar Dados":

        tela_visualizar_dados(supabase)
    # ===============================================================

    # ===================== SOLICITAÇÕES
    elif opcao == "Solicitações":

        tela_solicitacoes(
            supabase,
            nivel,
            lambda acao, tela="Solicitações", detalhes="", arquivo_url="": registrar_acao(
                supabase,
                acao,
                tela,
                detalhes,
                arquivo_url
            )
        )

    # ===================== SOBRE OS PRODUTOS
    elif opcao == "Sobre os Produtos":

        tela_sobre_produtos(supabase, nivel)
    # ==========================================

    # ===================== IMPORTAÇÃO DE EXCEL
    elif opcao == "Importações por Excel":

        if nivel not in ["admin"]:
            st.error("Acesso restrito.")
            st.stop()

        tela_importacoes_excel(supabase)
    # ==========================================

    # ===================== ANÁLISE DE PREÇOS
    elif opcao == "Análise de Preços":

        if nivel not in ["admin", "cotacao"]:
            st.error("Acesso restrito.")
            st.stop()

        tela_analise_precos(supabase)
    # ==========================================

    # ===================== POST DESTAQUES DO DIA
    elif opcao == "Post Destaques do Dia":

        if nivel not in ["admin", "cotacao", "convidado"]:
            st.error("Acesso restrito.")
            st.stop()

        tela_post_destaques_dia(supabase)
    # ==========================================

    # ===================== RELATÓRIO DIÁRIO
    elif opcao == "Relatório Diário":
        tela_relatorio_diario(supabase)
    # ==========================================

    # ===================== RELATÓRIO SEMANAL
    elif opcao == "Relatório Semanal":
        tela_relatorio_semanal(supabase)
    # ==========================================

    # ===================== RELATÓRIO MENSAL
    elif opcao == "Relatório Mensal":

        if nivel not in ["admin", "convidado"]:
            st.error("Acesso restrito.")
            st.stop()

        tela_relatorio_mensal(supabase)
    # ==========================================

    # ===================== RELATÓRIO SEMESTRAL
    elif opcao == "Relatório Semestral":

        if nivel not in ["admin", "cotacao", "convidado"]:
            st.error("Acesso restrito.")
            st.stop()

        tela_relatorio_semestral(supabase)
    # ==========================================

    # ===================== POSTS ANALÍTICOS
    elif opcao == "Posts Analíticos":

        if nivel not in ["admin", "cotacao"]:
            st.error("Acesso restrito.")
            st.stop()

        tela_posts_analiticos(supabase)
    # ==========================================

    # ===================== POSTS ANALÍTICOS INDIV
    elif opcao == "Post Unitário do Produto":

        if nivel not in ["admin", "cotacao"]:
            st.error("Acesso restrito.")
            st.stop()

        tela_post_produto_unitario(supabase)
    # ==========================================

    # ===================== INF DOS PRODUTOS
    elif opcao == "Informações dos Produtos":

        if nivel not in ["admin", "cotacao"]:
            st.error("Acesso restrito.")
            st.stop()

        tela_produtos_info(supabase)
    # ==========================================

    # ===================== OBSERVAÇÕES DE PRODUTOS
    elif opcao == "Observações de Produtos":

        if nivel not in ["admin", "cotacao"]:
            st.error("Acesso restrito.")
            st.stop()

        tela_observacoes_produtos(supabase)
    # ==========================================

    # ===================== ACOMPANHAMENTO
    elif opcao == "Acompanhamento":

        if nivel != "admin":
            st.error("Acesso restrito ao administrador.")
            st.stop()

        tela_acompanhamento(supabase)
#=======================================================================================================
