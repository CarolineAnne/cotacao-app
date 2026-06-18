# ===================== IMPORTS =====================
import streamlit as st
import pandas as pd
import io

from datetime import datetime

from db import conectar_supabase

from utils import (
    normalizar_lista_precos,
    corrigir_classe
)

from dados_utils import (
    carregar_produtos,
    carregar_todas_cotacoes,
    contar_solicitacoes_pendentes,
    registrar_acao
)

from pdf_utils import (
    gerar_pdf,
    gerar_pdf_sobre_produtos
)

from whatsapp_utils import (
    tela_configuracao_whatsapp,
    tela_teste_links_whatsapp
)

from analise_precos import tela_analise_precos
from observacoes_produtos import tela_observacoes_produtos
from posts_analiticos import tela_posts_analiticos
from tela_produtos_info import tela_produtos_info
from post_produto_unitario import tela_post_produto_unitario
from tela_importacoes_excel import tela_importacoes_excel
from relatorio_diario import tela_relatorio_diario
from relatorio_semanal import tela_relatorio_semanal
from solicitacoes import tela_solicitacoes
from auth_utils import verificar_login_seguro
from usuarios import tela_cadastro_usuarios
from produtos import tela_cadastro_produtos

from permissionarios import (
    tela_permissionarios_admin,
    tela_publica_permissionario,
    carregar_respostas_permissionarios,
    tela_respostas_permissionarios
)
# ====================================================

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
    with st.form("form_login"):
        usuario = st.text_input("Usuário")
        senha = st.text_input("Senha", type="password")

        entrar = st.form_submit_button("Entrar")

        if entrar:

            resultado = verificar_login_seguro(supabase, usuario, senha)

            if resultado:
                st.session_state.logado = True
                st.session_state.nome = resultado["nome"]
                st.session_state.nivel = resultado["nivel"]

                st.rerun()

            else:
                st.error("Usuário ou senha inválidos.")

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
            "Relatório Diário",
            "Relatório Semanal",
            "Post Unitário do Produto",
            "Informações dos Produtos",
            "Observações de Produtos",
            "Acompanhamento",
            "Configuração WhatsApp",
            "Teste Links WhatsApp"
        ]

    elif nivel == "cotacao":
        menu = [
            "Início",
            "Cotação do Dia",
            "Visualizar Dados",
            "Sobre os Produtos",
            "Solicitações",
            "Observações de Produtos",
            "Respostas dos Permissionários"
        ]

    elif nivel == "requisitante":
        menu = [
            "Início",
            "Solicitações",
            "Visualizar Dados",
            "Sobre os Produtos"
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
                position: sticky;
                top: 12px;
                z-index: 999;
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
                        "🧑‍🌾 Respostas dos Permissionários",
                        key="menu_respostas_permissionarios",
                        width="stretch",
                        on_click=abrir_pagina_cotacao,
                        args=("Respostas dos Permissionários",)
                    )

                with col3:
                    st.button(
                        "📋 Visualizar Dados",
                        key="menu_visualizar_dados",
                        width="stretch",
                        on_click=abrir_pagina_cotacao,
                        args=("Visualizar Dados",)
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
                        "📝 Observações de Produtos",
                        key="menu_observacoes_produtos",
                        width="stretch",
                        on_click=abrir_pagina_cotacao,
                        args=("Observações de Produtos",)
                    )

                with col6:
                    st.button(
                        "📨 Solicitações",
                        key="menu_solicitacoes",
                        width="stretch",
                        on_click=abrir_pagina_cotacao,
                        args=("Solicitações",)
                    )

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

    # ===================== RESPOSTAS DOS PERMISSIONÁRIOS
    elif opcao == "Respostas dos Permissionários":

        if nivel not in ["admin", "cotacao"]:
            st.error("Acesso restrito.")
            st.stop()

        tela_respostas_permissionarios(supabase)

    # ===================== COTAÇÃO
    elif opcao == "Cotação do Dia":

        st.title("📊 Cotação do Dia")

        # 🔔 mensagem após salvar
        mensagem_cotacao_atual = st.session_state.get("msg_cotacao")
        
        if mensagem_cotacao_atual:
            tipo, texto = mensagem_cotacao_atual
        
            if tipo == "success":
                st.success(texto)
            else:
                st.error(texto)
        
            st.session_state.msg_cotacao = False
    
        # garante session_state
        if "confirmar_cotacao" not in st.session_state:
            st.session_state.confirmar_cotacao = False
        
        data = st.date_input(
            "Data",
            value=pd.to_datetime("today"),
            key="data_cotacao_dia"
        )

        data_str = data.strftime("%Y-%m-%d")

        respostas_permissionarios = carregar_respostas_permissionarios(supabase, data_str)

        # 🔄 se trocar a data, cancela confirmação anterior
        if st.session_state.data_cotacao_atual != data_str:
            st.session_state.confirmar_cotacao = False
            st.session_state.data_cotacao_atual = data_str

        # 🔎 verifica se já existe cotação nessa data
        try:
            resp_data = supabase.table("cotacoes")\
                .select("id")\
                .eq("data", data_str)\
                .execute()
        
            cotacao_ja_existe = bool(resp_data.data)
        
        except Exception as e:
            st.error(f"Erro ao verificar data da cotação: {e}")
            cotacao_ja_existe = False
        
        if cotacao_ja_existe:
            st.warning(
                f"⚠️ Já existe cotação cadastrada para {data.strftime('%d/%m/%Y')}. "
                "Se você confirmar, a cotação anterior dessa data será substituída."
            )
            
        # ================= PRODUTOS =================
        try:
            produtos = carregar_produtos(supabase)
    
            # 🔹 ordem correta das classes
            ordem_classes = {
                "Hortaliças": 1,
                "Frutas": 2,
                "Especiarias": 3,
                "Cereais": 4,
                "SEM CLASSE": 99
            }
    
            # 🔹 padroniza classe
            produtos["classe"] = produtos["classe"].apply(corrigir_classe)
    
            # 🔹 cria ordem
            produtos["ordem_classe"] = produtos["classe"].map(ordem_classes).fillna(99)
    
            # 🔹 ordena
            produtos = produtos.sort_values(["ordem_classe", "nome"])
    
            # 🔹 remove auxiliar
            produtos = produtos.drop(columns=["ordem_classe"])
    
        except Exception as e:
            st.error(f"Erro ao carregar produtos: {e}")
            st.stop()
    
        # 🔹 validação
        if produtos.empty:
            st.warning("Cadastre produtos primeiro!")
            st.stop()
    
        # ================= COTAÇÕES =================
        try:
            df_ultimas = carregar_todas_cotacoes(supabase)
        
            if not df_ultimas.empty and "data" in df_ultimas.columns:
        
                df_ultimas["data"] = pd.to_datetime(df_ultimas["data"], errors="coerce")
                df_ultimas = df_ultimas.dropna(subset=["data"])
        
                df_ultimas["produto"] = df_ultimas["produto"].astype(str).str.strip().str.upper()
        
                df_ultimas = df_ultimas.sort_values("data", ascending=False)
                df_ultimas = df_ultimas.drop_duplicates(subset="produto", keep="first")
        
            else:
                df_ultimas = pd.DataFrame()
        
        except Exception as e:
            st.error(f"Erro ao carregar cotações: {e}")
            df_ultimas = pd.DataFrame()
    
        # LOOP
        cotacoes = []
    
        for _, row in produtos.iterrows():
            produto = str(row["nome"]).strip().upper()
    
            if not df_ultimas.empty:
                ultima = df_ultimas[df_ultimas["produto"] == produto]
            else:
                ultima = pd.DataFrame()
    
            col1, col2 = st.columns([1, 2])
    
            with col1:
                st.write(produto)
    
            with col2:
    
                key = f"precos_{produto}"
                sug_key = f"sugestoes_{produto}"

                # Carrega os preços antigos apenas como sugestão visual
                if key not in st.session_state or sug_key not in st.session_state:

                    if not ultima.empty:
                        sugestoes = normalizar_lista_precos(
                            ultima.iloc[0].get("precos_digitados", [])
                        )

                        # Se ainda não existir lista completa salva,
                        # usa mínimo e máximo como sugestão
                        if not sugestoes:
                            pmin_antigo = float(ultima.iloc[0]["preco_min"])
                            pmax_antigo = float(ultima.iloc[0]["preco_max"])

                            sugestoes = []

                            if pmin_antigo > 0:
                                sugestoes.append(pmin_antigo)

                            if pmax_antigo > 0 and pmax_antigo != pmin_antigo:
                                sugestoes.append(pmax_antigo)

                        # Os campos aparecem vazios, mas com o valor antigo como placeholder
                        st.session_state[sug_key] = sugestoes
                        st.session_state[key] = [""] * len(sugestoes)

                    else:
                        st.session_state[sug_key] = []
                        st.session_state[key] = []

                precos = st.session_state[key]
                sugestoes = st.session_state.get(sug_key, [])

                b1, b2 = st.columns(2)

                with b1:
                    if st.button("➕ Adicionar", key=f"add_{produto}"):
                        precos.append("")
                        sugestoes.append(None)

                with b2:
                    if precos and st.button("➖ Remover", key=f"rem_{produto}"):
                        precos.pop()

                        if sugestoes:
                            sugestoes.pop()

                cols = st.columns(3)

                for i in range(len(precos)):
                    with cols[i % 3]:

                        placeholder = ""

                        if i < len(sugestoes) and sugestoes[i]:
                            placeholder = f"{float(sugestoes[i]):.2f}".replace(".", ",")

                        valor_digitado = st.text_input(
                            f"P{i+1}",
                            value=precos[i],
                            placeholder=placeholder,
                            key=f"{produto}_{i}_txt"
                        )

                        precos[i] = valor_digitado

                # Transforma os textos digitados em números
                # Se o campo estiver vazio, mantém o preço antigo da sugestão
                precos_validos = []

                for i, p in enumerate(precos):

                    texto = str(p).replace(",", ".").strip()

                    # Se digitou um novo valor, usa o novo valor
                    if texto != "":
                        try:
                            valor = float(texto)

                            if valor > 0:
                                precos_validos.append(valor)

                        except:
                            pass

                    # Se deixou vazio, mantém o valor antigo
                    else:
                        if i < len(sugestoes) and sugestoes[i]:
                            try:
                                valor = float(sugestoes[i])

                                if valor > 0:
                                    precos_validos.append(valor)

                            except:
                                pass
    
               # 🔹 PREÇOS ENVIADOS PELOS PERMISSIONÁRIOS
                precos_permissionarios = []

                if not respostas_permissionarios.empty:
                    resp_produto = respostas_permissionarios[
                        respostas_permissionarios["produto"] == produto
                    ]

                    if not resp_produto.empty:
                        st.markdown("**Preços enviados por permissionários:**")

                        for _, r in resp_produto.iterrows():
                            nome_perm = str(r.get("permissionario_nome", ""))
                            preco_perm = float(r.get("preco", 0))

                            if preco_perm > 0:
                                precos_permissionarios.append(preco_perm)

                                numero_preco = r.get("numero_preco", "")

                                st.caption(
                                    f"🧑‍🌾 {nome_perm} - Preço {numero_preco}: R$ {preco_perm:.2f}".replace(".", ",")
                                )

                # junta preços digitados manualmente + preços dos permissionários
                #precos_validos = precos_validos + precos_permissionarios

                if precos_validos:
                    pmin = min(precos_validos)
                    pmax = max(precos_validos)
                    preco_medio = sum(precos_validos) / len(precos_validos)
                else:
                    pmin = pmax = preco_medio = 0
    
                valor_kg = (preco_medio / row["kg"]) if row["kg"] > 0 else 0
    
                st.caption(
                    f"🔽 Mín: {pmin:.2f} | 🔼 Máx: {pmax:.2f} | 📊 Médio: {preco_medio:.2f} | ⚖️ Kg: {valor_kg:.2f}"
                )
    
                if not ultima.empty:
                    valor_kg_anterior = float(ultima.iloc[0]["valor_kg"])
    
                    if valor_kg_anterior > 0:
                        variacao = ((valor_kg - valor_kg_anterior) / valor_kg_anterior) * 100
    
                        if abs(variacao) > 30:
                            st.warning(f"⚠️ Variação alta: {variacao:.1f}%")
    
            st.divider()
    
            cotacoes.append((
                produto,
                row["classe"],
                row["unidade"],
                row["kg"],
                pmin,
                pmax,
                precos_validos.copy()
            ))

        # SALVAR
        if not st.session_state.confirmar_cotacao:
        
            if st.button("💾 Salvar Cotação", key="btn_salvar_cotacao"):
                st.session_state.confirmar_cotacao = True
                st.rerun()
        
        else:
        
            if cotacao_ja_existe:
                st.warning(
                    f"⚠️ Atenção: ao confirmar, a cotação anterior de "
                    f"{data.strftime('%d/%m/%Y')} será apagada e substituída por esta."
                )
            else:
                st.warning("Deseja confirmar o salvamento desta cotação?")
        
            c1, c2 = st.columns(2)
        
            with c1:
                if st.button("✅ Confirmar", key="btn_confirmar_cotacao"):
        
                    try:
                        dados_insert = []
        
                        for c in cotacoes:

                            produto_c = str(c[0]).strip().upper()
                            classe_c = corrigir_classe(c[1])
                            unidade_c = c[2]
                            kg_c = c[3]
                            lista_precos = c[6]
                        
                            if lista_precos:
                                preco_min = min(lista_precos)
                                preco_max = max(lista_precos)
                                preco_medio = sum(lista_precos) / len(lista_precos)
                            else:
                                preco_min = 0
                                preco_max = 0
                                preco_medio = 0
                        
                            valor_kg = preco_medio / kg_c if kg_c > 0 else 0
                        
                            dados_insert.append({
                                "data": data_str,
                                "classe": classe_c,
                                "produto": produto_c,
                                "unidade": unidade_c,
                                "kg": kg_c,
                                "preco_min": preco_min,
                                "preco_max": preco_max,
                                "preco_medio": preco_medio,
                                "valor_kg": valor_kg,
                                "precos_digitados": lista_precos
                            })
        
                        if not dados_insert:
                            st.session_state.msg_cotacao = (
                                "error",
                                "Nenhum dado encontrado para salvar."
                            )
        
                        else:
                            # 🔥 SE JÁ EXISTIR COTAÇÃO NA DATA, APAGA ANTES
                            if cotacao_ja_existe:
                                supabase.table("cotacoes")\
                                    .delete()\
                                    .eq("data", data_str)\
                                    .execute()
        
                            # 🔥 SALVA A NOVA COTAÇÃO
                            response = supabase.table("cotacoes").insert(dados_insert).execute()
        
                            if response.data:
                                if cotacao_ja_existe:
                                    st.session_state.msg_cotacao = (
                                        "success",
                                        "Cotação substituída com sucesso!"
                                    )
        
                                    registrar_acao(
                                        supabase,
                                        "Cotação substituída",
                                        "Cotação do Dia",
                                        f"Cotação substituída para a data {data.strftime('%d/%m/%Y')}"
                                    )
        
                                else:
                                    st.session_state.msg_cotacao = (
                                        "success",
                                        "Cotação salva com sucesso!"
                                    )
        
                                    registrar_acao(
                                        supabase,
                                        "Cotação salva",
                                        "Cotação do Dia",
                                        f"Cotação cadastrada para a data {data.strftime('%d/%m/%Y')}"
                                    )
        
                                st.cache_data.clear()
        
                            else:
                                st.session_state.msg_cotacao = (
                                    "error",
                                    "Erro ao salvar cotação."
                                )
        
                    except Exception as e:
                        st.session_state.msg_cotacao = (
                            "error",
                            f"Erro ao salvar: {e}"
                        )
        
                    st.session_state.confirmar_cotacao = False
                    st.rerun()
        
            with c2:
                if st.button("❌ Cancelar", key="btn_cancelar_cotacao"):
                    st.session_state.confirmar_cotacao = False
                    st.rerun()

    # ===================== VISUALIZAR DADOS 
    elif opcao == "Visualizar Dados":

        st.title("📋 Cotações")

        # ================= FILTROS PRIMEIRO =================
        col1, col2 = st.columns(2)

        hoje = datetime.now().date()

        with col1:
            data_ref = st.date_input(
                "Data",
                value=hoje,
                key="data_visualizar_dados"
            )

        with col2:
            classe = st.selectbox(
                "Classe",
                ["Todas", "Hortaliças", "Frutas", "Especiarias", "Cereais"],
                key="classe_visualizar_dados"
            )

        data_sql = data_ref.strftime("%Y-%m-%d")

        # ================= BUSCA DIRETO NO SUPABASE PELA DATA =================
        try:
            resp = supabase.table("cotacoes")\
                .select("id, data, classe, produto, unidade, kg, preco_min, preco_max, preco_medio, valor_kg")\
                .eq("data", data_sql)\
                .order("produto")\
                .execute()

            df = pd.DataFrame(resp.data or [])

        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            st.stop()

        if df.empty:
            st.warning(f"Não há cotações cadastradas para {data_ref.strftime('%d/%m/%Y')}.")
            df_tabela = pd.DataFrame()

        else:
            # ================= TRATAMENTO =================
            df["data"] = pd.to_datetime(df["data"], errors="coerce")
            df = df.dropna(subset=["data"])

            df["produto"] = df["produto"].astype(str).str.strip().str.upper()

            df["classe"] = df["classe"].astype(str).str.strip()
            df["classe"] = df["classe"].replace("", "SEM CLASSE")
            df["classe"] = df["classe"].fillna("").apply(corrigir_classe)

            if "kg" in df.columns:
                df["kg"] = pd.to_numeric(df["kg"], errors="coerce").fillna(0).astype(int)

            # ================= FILTRO DE CLASSE =================
            if classe != "Todas":
                df = df[df["classe"] == classe]

            # ================= ORDENAÇÃO =================
            ordem_classes = ["Hortaliças", "Frutas", "Especiarias", "Cereais", "SEM CLASSE"]

            df["classe"] = pd.Categorical(
                df["classe"],
                categories=ordem_classes,
                ordered=True
            )

            df = df.sort_values(["classe", "produto"])

            # ================= TABELA =================
            df_tabela = df.drop(columns=[c for c in ["id", "data"] if c in df.columns]).copy()

            cols_preco = ["preco_min", "preco_max", "preco_medio", "valor_kg"]

            for col in cols_preco:
                if col in df_tabela.columns:
                    df_tabela[col] = df_tabela[col].apply(
                        lambda x: f"{x:.2f}".replace(".", ",") if pd.notnull(x) else ""
                    )

            st.dataframe(df_tabela, use_container_width=True)

        # ================= PDF =================
        gerar_pdf_click = st.button("📄 Gerar PDF")

        if gerar_pdf_click:

            try:
                if df.empty:
                    st.warning("Não há dados para gerar PDF nesta data.")
                else:
                    nome_pdf = f"cotacoes_{data_ref.strftime('%d-%m-%Y')}.pdf"

                    gerar_pdf(df, nome_pdf)

                    with open(nome_pdf, "rb") as f:
                        st.download_button(
                            "📥 Baixar PDF",
                            f,
                            file_name=nome_pdf
                        )

            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")

        # ================= EXCEL ADMIN =================
        if st.session_state.get("nivel") == "admin":

            st.divider()
            st.subheader("📥 Exportações do Administrador")

            try:
                # Excel da data filtrada
                if not df_tabela.empty:
                    buffer = io.BytesIO()
                    df_tabela.to_excel(buffer, index=False, engine="openpyxl")
                    buffer.seek(0)

                    st.download_button(
                        "📥 Baixar Excel da Data Filtrada",
                        buffer,
                        file_name=f"cotacoes_filtradas_{data_ref.strftime('%d-%m-%Y')}.xlsx"
                    )

                # Excel com TODAS as cotações cadastradas
                df_todas_cotacoes = carregar_todas_cotacoes(supabase)

                if df_todas_cotacoes.empty:
                    st.info("Não há cotações para exportar.")
                else:
                    df_exportar_todas = df_todas_cotacoes.copy()

                    df_exportar_todas["data"] = pd.to_datetime(
                        df_exportar_todas["data"],
                        errors="coerce"
                    ).dt.strftime("%d/%m/%Y")

                    df_exportar_todas["produto"] = df_exportar_todas["produto"].astype(str).str.strip().str.upper()
                    df_exportar_todas["classe"] = df_exportar_todas["classe"].apply(corrigir_classe)

                    if "kg" in df_exportar_todas.columns:
                        df_exportar_todas["kg"] = pd.to_numeric(
                            df_exportar_todas["kg"],
                            errors="coerce"
                        ).fillna(0).astype(int)

                    ordem_classes = ["Hortaliças", "Frutas", "Especiarias", "Cereais", "SEM CLASSE"]

                    df_exportar_todas["classe"] = pd.Categorical(
                        df_exportar_todas["classe"],
                        categories=ordem_classes,
                        ordered=True
                    )

                    df_exportar_todas = df_exportar_todas.sort_values(["data", "classe", "produto"])

                    buffer_todas = io.BytesIO()
                    df_exportar_todas.to_excel(buffer_todas, index=False, engine="openpyxl")
                    buffer_todas.seek(0)

                    st.download_button(
                        "📥 Exportar Todas as Cotações",
                        buffer_todas,
                        file_name=f"todas_cotacoes_{datetime.now().strftime('%d-%m-%Y')}.xlsx"
                    )

            except Exception as e:
                st.error(f"Erro ao gerar Excel: {e}")
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

        st.title("📝 Sobre os Produtos")

        # CARREGAR PRODUTOS
        try:
            produtos = carregar_produtos(supabase)

            if produtos.empty:
                st.warning("Nenhum produto cadastrado.")
                st.stop()

            produtos["nome"] = produtos["nome"].astype(str).str.strip().str.upper()
            produtos["classe"] = produtos["classe"].apply(corrigir_classe)

            ordem_classes_map = {
                "Hortaliças": 1,
                "Frutas": 2,
                "Especiarias": 3,
                "Cereais": 4,
                "SEM CLASSE": 99
            }

            produtos["ordem_classe"] = produtos["classe"].map(ordem_classes_map).fillna(99)
            produtos = produtos.sort_values(["ordem_classe", "nome"])
            produtos = produtos.drop(columns=["ordem_classe"])

        except Exception as e:
            st.error(f"Erro ao carregar produtos: {e}")
            st.stop()

        # ADMIN/COTAÇÃO: CADASTRAR OU EDITAR
        if nivel in ["admin", "cotacao"]:

            st.subheader("➕ Cadastrar / Atualizar Informação do Produto")

            produto_sel = st.selectbox(
                "Produto",
                produtos["nome"].tolist(),
                key="sobre_produto_sel"
            )

            dados_produto = produtos[produtos["nome"] == produto_sel].iloc[0]
            classe_produto = dados_produto["classe"]

            try:
                resp_info = supabase.table("informacoes_produtos")\
                    .select("*")\
                    .eq("produto", produto_sel)\
                    .execute()

                info_existente = pd.DataFrame(resp_info.data)

                if not info_existente.empty:
                    texto_atual = str(info_existente.iloc[0].get("informacoes", ""))
                else:
                    texto_atual = ""

            except Exception:
                texto_atual = ""

            informacoes = st.text_area(
                "Informações sobre o produto",
                value=texto_atual,
                height=180,
                key=f"info_{produto_sel}"
            )

            if st.button("💾 Salvar Informações"):

                if informacoes.strip() == "":
                    st.warning("Digite alguma informação antes de salvar.")

                else:
                    try:
                        agora = datetime.now()

                        resp_verifica = supabase.table("informacoes_produtos")\
                            .select("id")\
                            .eq("produto", produto_sel)\
                            .execute()

                        dados_existentes = pd.DataFrame(resp_verifica.data)

                        if dados_existentes.empty:

                            supabase.table("informacoes_produtos").insert({
                                "produto": produto_sel,
                                "classe": classe_produto,
                                "informacoes": informacoes.strip(),
                                "atualizado_por": st.session_state.get("nome", ""),
                                "nivel_usuario": nivel,
                                "data_atualizacao": agora.strftime("%Y-%m-%d"),
                                "hora_atualizacao": agora.strftime("%H:%M:%S")
                            }).execute()

                            registrar_acao(
                                supabase,
                                "Cadastro de informação de produto",
                                "Sobre os Produtos",
                                f"Informação cadastrada para o produto: {produto_sel}"
                            )

                            st.success("Informações cadastradas com sucesso!")

                        else:

                            id_info = int(dados_existentes.iloc[0]["id"])

                            supabase.table("informacoes_produtos").update({
                                "classe": classe_produto,
                                "informacoes": informacoes.strip(),
                                "atualizado_por": st.session_state.get("nome", ""),
                                "nivel_usuario": nivel,
                                "data_atualizacao": agora.strftime("%Y-%m-%d"),
                                "hora_atualizacao": agora.strftime("%H:%M:%S")
                            }).eq("id", id_info).execute()

                            registrar_acao(
                                supabase,
                                "Atualização de informação de produto",
                                "Sobre os Produtos",
                                f"Informação atualizada para o produto: {produto_sel}"
                            )

                            st.success("Informações atualizadas com sucesso!")

                        st.rerun()

                    except Exception as e:
                        st.error(f"Erro ao salvar informações: {e}")

            st.divider()

        # VISUALIZAÇÃO
        st.subheader("📋 Informações Cadastradas")

        try:
            resp_infos = supabase.table("informacoes_produtos")\
                .select("*")\
                .execute()

            df_infos = pd.DataFrame(resp_infos.data)

        except Exception as e:
            st.error(f"Erro ao carregar informações dos produtos: {e}")
            st.stop()

        if df_infos.empty:
            st.info("Nenhuma informação cadastrada até o momento.")
            st.stop()

        df_infos["produto"] = df_infos["produto"].astype(str).str.strip().str.upper()
        df_infos["classe"] = df_infos["classe"].apply(corrigir_classe)

        if "data_atualizacao" in df_infos.columns:
            df_infos["data_atualizacao"] = pd.to_datetime(
                df_infos["data_atualizacao"],
                errors="coerce"
            )

        # FILTROS
        col1, col2 = st.columns(2)

        with col1:
            filtro_classe = st.selectbox(
                "Filtrar por classe",
                ["Todas", "Hortaliças", "Frutas", "Especiarias", "Cereais", "SEM CLASSE"],
                key="filtro_classe_sobre"
            )

        with col2:
            lista_produtos = ["Todos"] + sorted(df_infos["produto"].dropna().unique().tolist())

            filtro_produto = st.selectbox(
                "Filtrar por produto",
                lista_produtos,
                key="filtro_produto_sobre"
            )

        df_filtrado = df_infos.copy()

        if filtro_classe != "Todas":
            df_filtrado = df_filtrado[df_filtrado["classe"] == filtro_classe]

        if filtro_produto != "Todos":
            df_filtrado = df_filtrado[df_filtrado["produto"] == filtro_produto]

        ordem_classes = ["Hortaliças", "Frutas", "Especiarias", "Cereais", "SEM CLASSE"]

        df_filtrado["classe"] = pd.Categorical(
            df_filtrado["classe"],
            categories=ordem_classes,
            ordered=True
        )

        df_filtrado = df_filtrado.sort_values(["classe", "produto"])

        if df_filtrado.empty:
            st.warning("Nenhuma informação encontrada com os filtros selecionados.")
        else:
            for _, row in df_filtrado.iterrows():

                with st.container():
                    st.markdown(f"### 📦 {row['produto']}")
                    st.write(f"**Classe:** {row['classe']}")
                    st.write(f"**Informações:** {row['informacoes']}")

                    data_txt = ""
                    if "data_atualizacao" in row and pd.notnull(row["data_atualizacao"]):
                        data_txt = row["data_atualizacao"].strftime("%d/%m/%Y")

                    st.caption(
                        f"Atualizado por: {row.get('atualizado_por', '')} "
                        f"({row.get('nivel_usuario', '')}) "
                        f"| Data: {data_txt} "
                        f"| Hora: {row.get('hora_atualizacao', '')}"
                    )

                    st.divider()

        # EXPORTAÇÃO EM PDF
        st.subheader("📥 Exportação")

        if st.button("📄 Gerar PDF - Sobre os Produtos"):

            try:
                nome_pdf = f"sobre_produtos_{datetime.now().strftime('%d-%m-%Y')}.pdf"

                gerar_pdf_sobre_produtos(df_filtrado, nome_pdf)

                with open(nome_pdf, "rb") as f:
                    st.download_button(
                        "📥 Baixar PDF - Sobre os Produtos",
                        f,
                        file_name=nome_pdf
                    )

                registrar_acao(
                    supabase,
                    "PDF gerado",
                    "Sobre os Produtos",
                    "PDF das informações dos produtos gerado"
                )

            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")
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

    # ===================== RELATÓRIO DIÁRIO
    elif opcao == "Relatório Diário":
        tela_relatorio_diario(supabase)
    # ==========================================

    # ===================== RELATÓRIO SEMANAL
    elif opcao == "Relatório Semanal":
        tela_relatorio_semanal(supabase)
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

        st.title("📌 Acompanhamento do Sistema")

        try:
            resp = supabase.table("acompanhamento")\
                .select("*")\
                .order("id", desc=True)\
                .execute()

            df_acomp = pd.DataFrame(resp.data)

        except Exception as e:
            st.error(f"Erro ao carregar acompanhamento: {e}")
            st.stop()

        if df_acomp.empty:
            st.info("Nenhuma ação registrada até o momento.")
            st.stop()

        # FILTROS
        st.subheader("🔎 Filtros")

        df_acomp["data"] = pd.to_datetime(df_acomp["data"], errors="coerce")

        col1, col2, col3 = st.columns(3)

        with col1:
            data_filtro = st.date_input("Data", value=datetime.now().date())

        with col2:
            usuarios = ["Todos"] + sorted(df_acomp["usuario"].dropna().unique().tolist())
            usuario_filtro = st.selectbox("Usuário", usuarios)

        with col3:
            telas = ["Todas"] + sorted(df_acomp["tela"].dropna().unique().tolist())
            tela_filtro = st.selectbox("Tela", telas)

        df_filtrado = df_acomp[df_acomp["data"].dt.date == data_filtro]

        if usuario_filtro != "Todos":
            df_filtrado = df_filtrado[df_filtrado["usuario"] == usuario_filtro]

        if tela_filtro != "Todas":
            df_filtrado = df_filtrado[df_filtrado["tela"] == tela_filtro]

        # TABELA
        st.subheader("📋 Registro de Atividades")

        df_tabela = df_filtrado.copy()

        if "data" in df_tabela.columns:
            df_tabela["data"] = df_tabela["data"].dt.strftime("%d/%m/%Y")

        colunas_exibir = [
            "data",
            "hora",
            "usuario",
            "nivel",
            "tela",
            "acao",
            "detalhes",
            "arquivo_url"
        ]

        colunas_existentes = [c for c in colunas_exibir if c in df_tabela.columns]

        st.dataframe(
            df_tabela[colunas_existentes],
            use_container_width=True
        )

        # DFS
        st.divider()
        st.subheader("📎 Arquivos PDF disponíveis")

        df_pdfs = df_filtrado[
            df_filtrado["arquivo_url"].notna() &
            (df_filtrado["arquivo_url"].astype(str).str.strip() != "")
        ]

        if df_pdfs.empty:
            st.info("Nenhum PDF registrado nesse período.")
        else:
            for _, row in df_pdfs.iterrows():
                st.markdown(
                    f"""
                    **{row.get('data').strftime('%d/%m/%Y') if pd.notnull(row.get('data')) else ''}**
                    — {row.get('hora', '')}  
                    **Usuário:** {row.get('usuario', '')}  
                    **Ação:** {row.get('acao', '')}  
                    [📥 Baixar PDF]({row.get('arquivo_url', '')})
                    """
                )

        # EXPORTAR EXCEL
        st.divider()

        try:
            buffer = io.BytesIO()
            df_tabela[colunas_existentes].to_excel(buffer, index=False, engine="openpyxl")
            buffer.seek(0)

            st.download_button(
                "📥 Exportar Acompanhamento em Excel",
                buffer,
                file_name=f"acompanhamento_{datetime.now().strftime('%d-%m-%Y')}.xlsx"
            )

        except Exception as e:
            st.error(f"Erro ao gerar Excel: {e}")
#=======================================================================================================

    # ===================== CONF. WHATSAPP
    elif opcao == "Configuração WhatsApp":
        tela_configuracao_whatsapp(supabase)

    # ===================== TESTE LINKS WHATSAPP
    elif opcao == "Teste Links WhatsApp":
        tela_teste_links_whatsapp(supabase)
