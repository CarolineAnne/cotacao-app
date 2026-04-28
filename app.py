# ===================== IMPORTS =====================
import streamlit as st
import pandas as pd
from datetime import datetime
import io
import os
import psycopg2
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from supabase import create_client
import base64
# ====================================================
def get_base64(file_path):
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode()
# ================== CONEXÃO =========================
url = "https://yovuvhuubopujagvukki.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlvdnV2aHV1Ym9wdWphZ3Z1a2tpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY4MjA1MTIsImV4cCI6MjA5MjM5NjUxMn0.ywT2j8efoK9hnGcckTVrPBa4P7Qi4WkJxkap5bSjLUM"
supabase = create_client(url,key)
# ====================================================

@st.cache_data(ttl=60)
def carregar_produtos():

    df = pd.DataFrame()  # garante existência

    try:
        resp = supabase.table("produtos").select("*").execute()

        if resp and resp.data:
            df = pd.DataFrame(resp.data)

            df["nome"] = df["nome"].astype(str).str.strip().str.upper()
            df["classe"] = df["classe"].astype(str).str.strip()

    except Exception as e:
        st.error(f"Erro ao carregar produtos: {e}")

    return df

@st.cache_data(ttl=60)
def carregar_cotacoes():

    df = pd.DataFrame()  # 🔥 garante que sempre existe

    try:
        resp = supabase.table("cotacoes")\
            .select("produto, preco_min, preco_max, valor_kg, data")\
            .execute()

        if resp and resp.data:
            df = pd.DataFrame(resp.data)

            df["produto"] = df["produto"].astype(str).str.strip().str.upper()

    except Exception as e:
        st.error(f"Erro ao carregar cotações: {e}")

    return df

def corrigir_classe(valor):
    valor = str(valor).strip().upper()

    if valor in ["HORTALIÇAS", "HORTALICAS"]:
        return "Hortaliças"
    elif valor == "FRUTAS":
        return "Frutas"
    elif valor == "ESPECIARIAS":
        return "Especiarias"
    elif valor == "CEREAIS":
        return "Cereais"
    else:
        return "SEM CLASSE"

# ================== VERIFICAR LOGIN =========================
def verificar_login(usuario, senha):

    resposta = supabase.table("usuarios") \
        .select("nome, nivel") \
        .eq("usuario", usuario) \
        .eq("senha", senha) \
        .execute()

    if resposta.data:
        return resposta.data[0]  # retorna dict: {'nome': ..., 'nivel': ...}
    return None
# ====================================================

# ================== GERAR PDF =========================
def gerar_pdf(df, nome_pdf):
    doc = SimpleDocTemplate(
        nome_pdf,
        pagesize=A4,
        leftMargin=10,
        rightMargin=10,
        topMargin=5,
        bottomMargin=5
    )

    styles = getSampleStyleSheet()
    elementos = []

    df = df.copy()

    df["produto"] = df["produto"].astype(str).str.strip().str.upper()
    df["classe"] = df["classe"].apply(corrigir_classe)

    ordem_classes = ["Hortaliças", "Frutas", "Especiarias", "Cereais", "SEM CLASSE"]

    df["ordem_classe"] = df["classe"].map({
        "Hortaliças": 1,
        "Frutas": 2,
        "Especiarias": 3,
        "Cereais": 4,
        "SEM CLASSE": 99
    })

    df = df.sort_values(["ordem_classe", "produto"])

    if "data" not in df.columns:
        raise ValueError("Coluna data não existe")

    if "classe" not in df.columns:
        raise ValueError("Coluna classe não existe")

    classes = [c for c in ordem_classes if c in df["classe"].dropna().unique()]

    # 🔥 GARANTIA EXTRA
    if len(classes) == 0:
        raise ValueError("Nenhuma classe encontrada para gerar PDF.")

    for i, c in enumerate(classes):
        dados_classe = df[df["classe"] == c].copy()
        dados_classe = dados_classe.drop(columns=["ordem_classe"], errors="ignore")

        # 🔹 evita erro se não tiver dados
        if dados_classe.empty:
            continue

        # 🔹 PEGA A DATA DA COTAÇÃO (ANTES DE QUALQUER ALTERAÇÃO)
        if "data" not in dados_classe.columns:
            raise ValueError("Coluna 'data' não encontrada para gerar o PDF.")

        data_ref = dados_classe["data"].max()
        data_cotacao = pd.to_datetime(data_ref).strftime('%d/%m/%Y')
        
        # 🔹 REMOVE COLUNAS DESNECESSÁRIAS
        colunas_remover = [col for col in ["classe", "id"] if col in dados_classe.columns]
        dados_classe = dados_classe.drop(columns=colunas_remover)

        # 🔹 DEFINE ORDEM DAS COLUNAS (IMPORTANTE PRA NÃO BAGUNÇAR)
        colunas_ordem = [
            "produto",
            "unidade",
            "kg",
            "preco_min",
            "preco_max",
            "preco_medio",
            "valor_kg"
        ]

        colunas_existentes = [col for col in colunas_ordem if col in dados_classe.columns]
        dados_classe = dados_classe[colunas_existentes]

        # 🔹 RENOMEIA COLUNAS (CABEÇALHO BONITO NO PDF)
        nomes_colunas = {
            "produto": "Produto",
            "unidade": "Unidade",
            "kg": "Kg",
            "preco_min": "Preço Mín",
            "preco_max": "Preço Máx",
            "preco_medio": "Preço Médio",
            "valor_kg": "Valor/Kg"
        }

        dados_classe = dados_classe.rename(columns=nomes_colunas)

        # 🔹 FORMATA NÚMEROS (2 CASAS DECIMAIS + VÍRGULA)
        cols_num = dados_classe.select_dtypes(include="number").columns

        for col in cols_num:
            dados_classe[col] = dados_classe[col].map(
                lambda x: f"{x:.2f}".replace(".", ",") if pd.notnull(x) else ""
            )

        tabela_dados = [list(dados_classe.columns)] + dados_classe.values.tolist()

        # -------- CABEÇALHO -------- #
        try:
            from reportlab.platypus import Image
            logo = Image("logo.png", width=60, height=40)
            elementos.append(logo)
        except:
            pass  # se não encontrar o logo, não quebra o sistema

        from reportlab.lib.enums import TA_CENTER

        # Estilos centralizados
        estilo_titulo = styles["Title"].clone('titulo_centro')
        estilo_titulo.alignment = TA_CENTER
        estilo_titulo.fontSize = 14   # título principal
        estilo_titulo.leading = 12
        estilo_titulo.spaceAfter = 4
        estilo_titulo.spaceBefore = 6

        estilo_sub = styles["Italic"].clone('sub_centro')
        estilo_sub.alignment = TA_CENTER
        estilo_sub.fontSize = 8   # título principal
        estilo_sub.leading = 8  # padrão é maior → diminui aqui
        estilo_sub.spaceAfter = 2
        estilo_sub.spaceBefore = 0

        # -------- TÍTULOS CENTRALIZADOS -------- #
        elementos.append(Paragraph("AMA - Autarquia Municipal de Abastecimento", estilo_sub))
        elementos.append(Paragraph("Diretor Executivo: Celso Candido Almeida Leal", estilo_sub))
        elementos.append(Paragraph("Relatório de Cotação de Preços", estilo_titulo))
        elementos.append(Spacer(1, 6))

        # -------- CLASSE E DATA LADO A LADO -------- #
        from reportlab.platypus import Table

        # 🔹 DATA DE EMISSÃO (momento do PDF)
        data_emissao = datetime.now().strftime('%d/%m/%Y')

        # 🔹 LINHA DE INFORMAÇÕES
        info_dados = [[
            f"Classe: {c}",
            f"Data de Cotação: {data_cotacao}",
            f"Data de emissão: {data_emissao}"
        ]]

        info_tabela = Table(info_dados, colWidths=[145, 145, 145]) # criação da tabela e definição da largura das colunas
        info_tabela.setStyle([
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("VALIGN", (0,0), (-1,-1), "MIDDLE"),

            # 🔹 REMOVE NEGRITO
            ("FONTNAME", (0,0), (-1,-1), "Helvetica"),

            # 🔹 FONTE MENOR
            ("FONTSIZE", (0,0), (-1,-1), 7),

            # 🔹 MENOS ESPAÇO (mais compacto)
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 1),
        ])

        elementos.append(info_tabela)
        elementos.append(Spacer(1, 6))

         # 🔹 REMOVE DATA DA TABELA (para não aparecer na tabela)
        if "data" in dados_classe.columns:
            dados_classe = dados_classe.drop(columns=["data"])

        # -------- TABELA -------- #
        tabela_dados = [list(dados_classe.columns)] + dados_classe.values.tolist()

        tabela = Table(
            tabela_dados,
            colWidths=[120, 40, 30, 50, 50, 60, 50], # largura da tabela
            rowHeights=11, # altura da tabela
            repeatRows=1
        )

        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),

            # 🔹 ALINHAMENTO HORIZONTAL
            ('ALIGN', (0,0), (-1,0), 'CENTER'),     # cabeçalho
            ('ALIGN', (0,1), (1,-1), 'LEFT'),       # produto
            ('ALIGN', (2,1), (-1,-1), 'RIGHT'),     # números

            # 🔹 ALINHAMENTO VERTICAL (UMA ÚNICA REGRA)
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),

            ('FONTNAME', (0,0),(-1,0),'Helvetica-Bold'),

            # LLINHAS FINAS
            ('GRID', (0,0), (-1,-1), 0.1, colors.grey),
            
            ('BACKGROUND', (0,1), (-1,-1), colors.whitesmoke),

            # 🔹 MELHORIA DE ESPAÇAMENTO (opcional, mas recomendado)
            ('LEFTPADDING', (0,0), (-1,-1), 2),
            ('RIGHTPADDING', (0,0), (-1,-1), 2),
            ('TOPPADDING', (0,0), (-1,-1), 2),
            ('BOTTOMPADDING', (0,0), (-1,-1), 2),
            
            # tamanho da fonte
            ('FONTSIZE', (0,0), (-1,0), 8),
            ('FONTSIZE', (0,1), (-1,-1), 7), 
        ]))

        tabela.hAlign = 'CENTER'

        elementos.append(tabela)
        elementos.append(Spacer(1, 8))

        # -------- RODAPÉ -------- #
        elementos.append(Paragraph("Grace Kelly Rodrigues da Silva Santos", estilo_sub))
        elementos.append(Paragraph("Supervisor de Estatística, Pesquisa e Controle de Qualidade", estilo_sub))

        # Nova página para próxima classe
        if i < len(classes) - 1:
            elementos.append(PageBreak())

    # 🔥 PROTEÇÃO: evita PDF vazio
    if not elementos:
        elementos.append(Paragraph(
            "Nenhum dado disponível para gerar o relatório.",
            styles["Normal"]
        ))
    
    doc.build(elementos)
# ====================================================

# ================== CONFIG ==========================
st.set_page_config(page_title="Sistema de Cotação", layout="wide")

# 🔥 FUNDO GIF
gif_base64 = get_base64("capa.gif")

st.markdown(
    """
    <style>
    .stApp {
        background: url("https://media2.giphy.com/media/v1.Y2lkPTc5MGI3NjExeGZhcHBta2hsdTh2bmY0Y3h3dWUwMW40eXNiMGozOW1rYjRmNGtvZiZlcD12MV9pbnRlcm5hbF9naWZfYnlfaWQmY3Q9Zw/3bsn2kadghWrYMXneO/giphy.gif") no-repeat center center fixed;
        background-size: cover;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 🔥 SIDEBAR TRANSPARENTE
st.markdown(
    """
    <style>
    [data-testid="stSidebar"] {
        background-color: rgba(0, 0, 0, 0.6);
    }
    </style>
    """,
    unsafe_allow_html=True
)

# 🔥 FUNDO DO CONTEÚDO
st.markdown(
    """
    <style>
    .block-container {
        background-color: rgba(0, 0, 0, 0.3);
        padding: 20px;
        border-radius: 10px;
    }
    </style>
    """,
    unsafe_allow_html=True
)
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
# ====================================================

# ================== LOGIN ==========================
if not st.session_state.logado:

    st.title("🔐 Login")

    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):

        resultado = verificar_login(usuario, senha)

        if resultado:
            st.session_state.logado = True
            st.session_state.nome = resultado["nome"]
            st.session_state.nivel = resultado["nivel"]

            st.rerun()

        else:
            st.error("Usuário ou senha inválidos")

    st.stop()  # 🔴 ESSENCIAL: impede o resto do app rodar
# ====================================================

# ================== SISTEMA ==========================
if st.session_state.logado:

    st.sidebar.title("📌 Menu")

    nivel = st.session_state.get("nivel", "")

    if nivel == "admin":
        menu = ["Início", "Cadastro de Usuários", "Cadastro de Produtos", "Cotação do Dia", "Visualizar Dados"]

    elif nivel == "cotacao":
        menu = ["Início", "Cotação do Dia", "Visualizar Dados"]

    else:
        menu = ["Início", "Visualizar Dados"]

    opcao = st.sidebar.selectbox("Opções", menu)

    st.sidebar.write(f"👤 {st.session_state.get('nome', '')}")
    st.sidebar.write(f"🔑 {nivel}")

    if st.sidebar.button("🚪 Sair"):
        st.session_state.clear()
        st.rerun()
# ====================================================

# ================== TELAS ==========================   

    # ================== INÍCIO
    if opcao == "Início":

        st.title("📊 Sistema de Cotação")
        st.caption("Utilize o menu lateral para navegar pelas funcionalidades.")

        # espaço visual
        #st.divider()

        # imagem com verificação mais segura
        #img_path = "home.png"

        #if os.path.exists(img_path):
        #    st.image(img_path, use_container_width=True)
        #else:
        #    st.warning("Imagem 'home.png' não encontrada no diretório do projeto.")
    # =====================

    # ================== CADASTRO DE USUÁRIOS
    elif opcao == "Cadastro de Usuários":
        st.title("👤 Cadastro de Usuários")

        # garante states
        for k in ["confirmar_usuario", "confirmar_edicao_usuario", "confirmar_exclusao_usuario"]:
            if k not in st.session_state:
                st.session_state[k] = False
    
        st.subheader("➕ Novo Usuário")
    
        nome = st.text_input("Nome", key="user_nome")
        usuario = st.text_input("Usuário", key="user_usuario")
        senha = st.text_input("Senha", type="password", key="user_senha")
        nivel = st.selectbox("Nível", ["admin", "cotacao", "visitante"], key="user_nivel")

        # CADASTRO
        if st.button("Cadastrar Usuário"):

            try:
                supabase.table("usuarios").insert({
                    "nome": nome,
                    "usuario": usuario,
                    "senha": senha,
                    "nivel": nivel
                }).execute()
        
                st.success("Usuário cadastrado com sucesso!")
                st.cache_data.clear()
        
            except Exception as e:
                st.error(f"Erro ao cadastrar: {e}")

        # LISTAR
        try:
            response = supabase.table("usuarios").select("*").execute()
            df = pd.DataFrame(response.data)
        
            st.dataframe(df, use_container_width=True)
        
        except Exception as e:
            st.error(f"Erro ao carregar usuários: {e}")
        
        st.divider()
    
        # EDITAR / EXCLUIR
        if not df.empty:
    
            st.subheader("✏️ Editar / Excluir Usuário")
    
            usuario_sel = st.selectbox("Selecione o usuário", df["usuario"], key="select_user")
            dados = df[df["usuario"] == usuario_sel].iloc[0]
    
            if "usuario_anterior" not in st.session_state:
                st.session_state.usuario_anterior = None
    
            if st.session_state.usuario_anterior != usuario_sel:
                st.session_state.edit_user_nome = dados["nome"]
                st.session_state.edit_user_usuario = dados["usuario"]
                st.session_state.edit_user_senha = dados["senha"]
                st.session_state.edit_user_nivel = dados["nivel"]
                st.session_state.usuario_anterior = usuario_sel
    
            novo_nome = st.text_input("Nome", key="edit_user_nome")
            novo_usuario = st.text_input("Usuário", key="edit_user_usuario")
            nova_senha = st.text_input("Senha", key="edit_user_senha")
    
            novo_nivel = st.selectbox(
                "Nível",
                ["admin", "cotacao", "visitante"],
                index=["admin", "cotacao", "visitante"].index(st.session_state.edit_user_nivel),
                key="edit_user_nivel"
            )
    
            col1, col2 = st.columns(2)

            # ATUALIZAR
            with col1:
                if st.button("✏️ Atualizar Usuário"):
            
                    try:
                        supabase.table("usuarios").update({
                            "nome": novo_nome,
                            "usuario": novo_usuario,
                            "senha": nova_senha,
                            "nivel": novo_nivel
                        }).eq("id", int(dados["id"])).execute()
            
                        st.success("Usuário atualizado!")
                        st.cache_data.clear()
            
                    except Exception as e:
                        st.error(f"Erro ao atualizar: {e}")
            
                    st.rerun()
    
            # EXCLUIR 
            with col2:
                if st.button("🗑️ Excluir Usuário"):
            
                    try:
                        supabase.table("usuarios")\
                            .delete()\
                            .eq("id", int(dados["id"]))\
                            .execute()
            
                        st.success("Usuário excluído!")
                        st.cache_data.clear()
            
                    except Exception as e:
                        st.error(f"Erro ao excluir: {e}")
            
                    st.rerun()
    # =====================
        
    # ===================== CADASTRO DE PRODUTOS
    elif opcao == "Cadastro de Produtos":
    
        st.title("📦 Cadastro de Produtos")
    
        # garante session_state
        for k in ["confirmar_cadastro_produto", "confirmar_edicao", "confirmar_exclusao"]:
            if k not in st.session_state:
                st.session_state[k] = False

        # MENSAGEM
        if "msg" in st.session_state and st.session_state.msg:
            tipo, texto = st.session_state.msg
            if tipo == "success":
                st.success(texto)
            else:
                st.error(texto)
            st.session_state.msg = None
    
        # NOVO PRODUTO
        st.subheader("➕ Novo Produto")

        nome = st.text_input("Nome")
        classe = st.selectbox("Classe", ["Hortaliças", "Frutas", "Especiarias", "Cereais"])
        unidade = st.selectbox("Unidade", ["Kg", "Cx", "Sc", "Mo-4", "Mo-5", "Lt", "Centro", "Fd"])
        kg = st.number_input("Kg", min_value=0, step=1, format="%d")
        
        if st.button("Cadastrar Produto"):
        
            try:
                supabase.table("produtos").insert({
                    "nome": nome.strip().upper(),
                    "classe": corrigir_classe(c[1]),
                    "unidade": unidade,
                    "kg": kg
                }).execute()
        
                st.session_state.msg = ("success", "Produto cadastrado!")
                st.cache_data.clear()
        
            except Exception:
                st.session_state.msg = ("error", "Produto já existe!")
        
        st.divider()
    
        # LISTAR
        try:
            response = supabase.table("produtos").select("*").execute()
            df = pd.DataFrame(response.data)
            
            if not df.empty:
        
                # 🔹 limpa possíveis espaços
                df["classe"] = df["classe"].astype(str).str.strip()
                df["nome"] = df["nome"].astype(str).str.strip().str.upper()
        
                # 🔹 ordem personalizada das classes
                ordem_classes = ["Hortaliças", "Frutas", "Especiarias", "Cereais"]
        
                df["classe"] = pd.Categorical(
                    df["classe"],
                    categories=ordem_classes,
                    ordered=True
                )
        
                # 🔹 ordena
                df = df.sort_values(["classe", "nome"], na_position="last")
        
            # 🔹 FORA do if, mas ainda dentro do try
            st.dataframe(df, use_container_width=True)
        
        except Exception as e:
            st.error(f"Erro ao carregar produtos: {e}")
        
        st.divider()
    
        # EDITAR / EXCLUIR
        if not df.empty:
    
            st.subheader("✏️ Editar / Excluir")
    
            produto_selecionado = st.selectbox("Produto", df["nome"], key="select_prod")

            dados = df[df["nome"] == produto_selecionado].iloc[0]
            
            # 🔹 controle de mudança de produto
            if "produto_anterior" not in st.session_state:
                st.session_state.produto_anterior = None
            
            if st.session_state.produto_anterior != produto_selecionado:
                st.session_state.edit_prod_nome = dados["nome"]
                st.session_state.edit_classe = str(dados["classe"])
                st.session_state.edit_unidade = dados["unidade"]
                st.session_state.edit_kg = float(dados["kg"])
                st.session_state.produto_anterior = produto_selecionado
            
            # 🔹 campos editáveis sincronizados
            novo_nome = st.text_input("Nome", key="edit_prod_nome")
            
            opcoes_classe = ["Hortaliças", "Frutas", "Especiarias", "Cereais"]

            nova_classe = st.selectbox(
                "Classe",
                opcoes_classe,
                index=opcoes_classe.index(st.session_state.edit_classe),
                key="edit_classe"
            )
            
            opcoes_unidade = ["Kg", "Cx", "Sc", "Mo-4", "Mo-5", "Lt", "Centro", "Fd"]

            nova_unidade = st.selectbox(
                "Unidade",
                opcoes_unidade,
                index=opcoes_unidade.index(st.session_state.edit_unidade),
                key="edit_unidade"
            )
            
            novo_kg = st.number_input("Kg", step=1, format="%d", key="edit_kg")
    
            col1, col2 = st.columns(2)
    
            # UPDATE
            with col1:
                if st.button("✏️ Atualizar"):
            
                    try:
                        # 🔥 guarda nome antigo
                        nome_antigo = dados["nome"]
            
                        # 🔥 atualiza produto
                        supabase.table("produtos").update({
                            "nome": novo_nome.strip().upper(),
                            "classe": nova_classe,
                            "unidade": nova_unidade,
                            "kg": novo_kg
                        }).eq("id", int(dados["id"])).execute()
            
                        # 🔥 atualiza cotações
                        supabase.table("cotacoes")\
                            .update({"produto": novo_nome.strip().upper()})\
                            .eq("produto", nome_antigo)\
                            .execute()
            
                        # 🔥 mensagem
                        st.session_state.msg = ("success", "Produto atualizado!")
            
                        # 🔥 limpa cache
                        st.cache_data.clear()
            
                    except Exception as e:
                        st.session_state.msg = ("error", str(e))
            
                    # 🔥 recarrega tela
                    st.rerun()
    
            # DELETE
            with col2:
                if st.button("🗑️ Excluir"):
            
                    try:
                        nome_antigo = dados["nome"]
            
                        # 🔥 remove cotações desse produto
                        supabase.table("cotacoes")\
                            .delete()\
                            .eq("produto", nome_antigo)\
                            .execute()
            
                        # 🔥 remove produto
                        supabase.table("produtos")\
                            .delete()\
                            .eq("id", int(dados["id"]))\
                            .execute()
            
                        st.session_state.msg = ("success", "Produto excluído!")
            
                        # 🔥 limpa cache
                        st.cache_data.clear()
            
                    except Exception as e:
                        st.session_state.msg = ("error", str(e))
            
                    # 🔥 recarrega tela (UMA VEZ SÓ)
                    st.rerun()
    # =====================

    # ===================== COTAÇÃO
    elif opcao == "Cotação do Dia":

        st.title("📊 Cotação do Dia")
    
        # garante session_state
        if "confirmar_cotacao" not in st.session_state:
            st.session_state.confirmar_cotacao = False
        
        data = st.date_input("Data", value=pd.to_datetime("today"))
        
        # ================= PRODUTOS =================
        try:
            produtos = carregar_produtos()
    
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
            resp = supabase.table("cotacoes")\
                .select("produto, preco_min, preco_max, valor_kg, data")\
                .order("data", desc=True)\
                .execute()
    
            df_ultimas = pd.DataFrame(resp.data)
    
            if not df_ultimas.empty and "data" in df_ultimas.columns:
                df_ultimas["data"] = pd.to_datetime(df_ultimas["data"], errors="coerce")
                df_ultimas = df_ultimas.dropna(subset=["data"])
                df_ultimas = df_ultimas.sort_values("data", ascending=False)
                df_ultimas = df_ultimas.drop_duplicates(subset="produto", keep="first")
            else:
                df_ultimas = pd.DataFrame()
    
        except Exception as e:
            st.error(f"Erro ao carregar cotações: {e}")
            df_ultimas = pd.DataFrame()
    
        # ================= LOOP =================
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
    
                if key not in st.session_state:
                    if not ultima.empty:
                        st.session_state[key] = [
                            float(ultima.iloc[0]["preco_min"]),
                            float(ultima.iloc[0]["preco_max"])
                        ]
                    else:
                        st.session_state[key] = []
    
                precos = st.session_state[key]
    
                b1, b2 = st.columns(2)
    
                with b1:
                    if st.button("➕ Adicionar", key=f"add_{produto}"):
                        precos.append(0.0)
    
                with b2:
                    if precos and st.button("➖ Remover", key=f"rem_{produto}"):
                        precos.pop()
    
                cols = st.columns(3)
    
                for i in range(len(precos)):
                    with cols[i % 3]:
                        precos[i] = st.number_input(
                            f"P{i+1}",
                            value=precos[i],
                            key=f"{produto}_{i}"
                        )
    
                precos_validos = [p for p in precos if p > 0]
    
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
    
            cotacoes.append((produto, row["classe"], row["unidade"], row["kg"], pmin, pmax))
    
        # ================= SALVAR =================
        if not st.session_state.confirmar_cotacao:
    
            if st.button("💾 Salvar Cotação"):
                st.session_state.confirmar_cotacao = True
    
        else:
            st.warning("Confirmar salvamento?")
            c1, c2 = st.columns(2)
    
            with c1:
                if st.button("✅ Confirmar"):
    
                    try:
                        dados_insert = []
    
                        for c in cotacoes:
                            preco_medio = (c[4] + c[5]) / 2
                            valor_kg = preco_medio / c[3] if c[3] > 0 else 0
    
                            dados_insert.append({
                                "data": data.strftime("%Y-%m-%d"),
                                "classe": corrigir_classe(classe),
                                "produto": str(c[0]).strip().upper(),
                                "unidade": c[2],
                                "kg": c[3],
                                "preco_min": c[4],
                                "preco_max": c[5],
                                "preco_medio": preco_medio,
                                "valor_kg": valor_kg
                            })
    
                        response = supabase.table("cotacoes").insert(dados_insert).execute()
    
                        if response.data:
                            st.success("Cotação salva com sucesso!")
                            st.cache_data.clear()
                        else:
                            st.error("Erro ao salvar dados.")
    
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
    
                    st.session_state.confirmar_cotacao = False
                    st.rerun()
    
            with c2:
                if st.button("❌ Cancelar"):
                    st.session_state.confirmar_cotacao = False

    # ===================== VISUALIZAR DADOS 
    elif opcao == "Visualizar Dados":

        st.title("📋 Cotações")

        try:
            resp = supabase.table("cotacoes")\
                .select("data, classe, produto, unidade, kg, preco_min, preco_max, preco_medio, valor_kg")\
                .execute()

            df = pd.DataFrame(resp.data)

        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            st.stop()

        # 🔴 PROTEÇÃO (evita tela preta)
        if df is None or df.empty:
            st.warning("Sem dados disponíveis.")
            st.stop()

        # ================= TRATAMENTO =================
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df = df.dropna(subset=["data"])

        df["produto"] = df["produto"].astype(str).str.strip().str.upper()
        
        df["classe"] = df["classe"].astype(str).str.strip()
        df["classe"] = df["classe"].replace("", "SEM CLASSE")
        df["classe"] = df["classe"].fillna("").apply(corrigir_classe)
        # 🔹 kg inteiro
        if "kg" in df.columns:
            df["kg"] = pd.to_numeric(df["kg"], errors="coerce").fillna(0).astype(int)

        # ================= FILTROS =================
        col1, col2, col3 = st.columns(3)

        hoje = datetime.now().date()

        with col1:
            data_inicio = st.date_input("Data inicial", value=hoje)

        with col2:
            data_fim = st.date_input("Data final", value=hoje)

        with col3:
            classe = st.selectbox(
                "Classe",
                ["Todas", "Hortaliças", "Frutas", "Especiarias", "Cereais"]
            )

        # ================= FILTRO =================
        data_inicio = pd.to_datetime(data_inicio)
        data_fim = pd.to_datetime(data_fim)

        df = df[(df["data"] >= data_inicio) & (df["data"] <= data_fim)]

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

        # 🔹 preços com vírgula
        cols_preco = ["preco_min", "preco_max", "preco_medio", "valor_kg"]

        for col in cols_preco:
            if col in df_tabela.columns:
                df_tabela[col] = df_tabela[col].apply(
                    lambda x: f"{x:.2f}".replace(".", ",") if pd.notnull(x) else ""
                )

        st.dataframe(df_tabela, use_container_width=True)

        # ================= BOTÃO PDF =================
        gerar_pdf_click = st.button("📄 Gerar PDF")

        # ================= EXCEL =================
        if st.session_state.get("nivel") == "admin":

            try:
                buffer = io.BytesIO()
                df_tabela.to_excel(buffer, index=False, engine="openpyxl")
                buffer.seek(0)

                st.download_button(
                    "📥 Baixar Excel",
                    buffer,
                    file_name=f"cotacoes_{datetime.now().strftime('%d-%m-%Y')}.xlsx"
                )

            except Exception as e:
                st.error(f"Erro ao gerar Excel: {e}")

        # ================= PDF =================
        if gerar_pdf_click:

            try:
                if not df.empty:
                    data_ref = df["data"].max()
                    nome_pdf = f"cotacoes_{data_ref.strftime('%d-%m-%Y')}.pdf"
                else:
                    nome_pdf = f"cotacoes_{datetime.now().strftime('%d-%m-%Y')}.pdf"

                gerar_pdf(df, nome_pdf)

                with open(nome_pdf, "rb") as f:
                    st.download_button(
                        "📥 Baixar PDF",
                        f,
                        file_name=nome_pdf
                    )

            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")
