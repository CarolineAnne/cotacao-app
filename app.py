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
# ====================================================

# ================== CONEXÃO =========================
url = "https://yovuvhuubopujagvukki.supabase.co"
key = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlvdnV2aHV1Ym9wdWphZ3Z1a2tpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY4MjA1MTIsImV4cCI6MjA5MjM5NjUxMn0.ywT2j8efoK9hnGcckTVrPBa4P7Qi4WkJxkap5bSjLUM"
supabase = create_client(url,key)
# ====================================================

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
def gerar_pdf(df, nome_arquivo):
    doc = SimpleDocTemplate(
    nome_arquivo,
    pagesize=A4,
    leftMargin=13,
    rightMargin=13,
    topMargin=6,
    bottomMargin=6
    )   
    styles = getSampleStyleSheet()
    elementos = []

    classes = df["classe"].unique()

    for c in classes:
        dados_classe = df[df["classe"] == c]
        
        # 🔹 REMOVE A COLUNA CLASSE DA TABELA
        dados_classe = dados_classe.drop(columns=["classe"])

        tabela_dados = [list(dados_classe.columns)] + dados_classe.values.tolist()

        # -------- CABEÇALHO -------- #
        try:
            from reportlab.platypus import Image
            logo = Image("logo.png", width=70, height=45)
            elementos.append(logo)
        except:
            pass  # se não encontrar o logo, não quebra o sistema

        from reportlab.lib.enums import TA_CENTER

        # Estilos centralizados
        estilo_titulo = styles["Title"].clone('titulo_centro')
        estilo_titulo.alignment = TA_CENTER
        estilo_titulo.leading = 14
        estilo_titulo.spaceAfter = 4
        estilo_titulo.spaceBefore = 6

        estilo_sub = styles["Italic"].clone('sub_centro')
        estilo_sub.alignment = TA_CENTER
        estilo_sub.leading = 12  # padrão é maior → diminui aqui
        estilo_sub.spaceAfter = 2
        estilo_sub.spaceBefore = 0

        # -------- TÍTULOS CENTRALIZADOS -------- #
        elementos.append(Paragraph("AMA - Autarquia Municipal de Abastecimento", estilo_sub))
        elementos.append(Paragraph("Diretor Executivo: Celso Candido Almeida Leal", estilo_sub))
        elementos.append(Paragraph("Relatório de Cotação de Preços", estilo_titulo))
        elementos.append(Spacer(1, 12))

        # -------- CLASSE E DATA LADO A LADO -------- #
        from reportlab.platypus import Table

        info_dados = [[
            f"Classe: {c}",
            f"Data de emissão: {datetime.now().strftime('%d/%m/%Y')}"
        ]]

        info_tabela = Table(info_dados, colWidths=[250, 250])
        info_tabela.setStyle([
            ("ALIGN", (0,0), (-1,-1), "CENTER"),
            ("FONTNAME", (0,0), (-1,-1), "Helvetica-Bold"),
        ])

        elementos.append(info_tabela)
        elementos.append(Spacer(1, 12))

        # -------- TABELA -------- #
        tabela_dados = [list(dados_classe.columns)] + dados_classe.values.tolist()

        num_colunas = len(tabela_dados[0])
        largura_total = 560  # largura útil do A4 considerando margens
        # deixa a coluna do produto maior automaticamente
        
        tabela = Table(tabela_dados, colWidths=[125, 75, 75, 75], rowHeights=15, repeatRows=1)

        tabela.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.darkgreen),
            ('TEXTCOLOR',(0,0),(-1,0),colors.white),
            ('ALIGN',(0,0),(-1,-1),'CENTER'),
            ('FONTNAME', (0,0),(-1,0),'Helvetica-Bold'),
            ('GRID', (0,0), (-1,-1), 0.1, colors.black),
            ('BACKGROUND', (0,1), (-1,-1), colors.whitesmoke),

            # 🔹 MELHORIA DE ESPAÇAMENTO (opcional, mas recomendado)
            ('LEFTPADDING', (0,0), (-1,-1), 5),
            ('RIGHTPADDING', (0,0), (-1,-1), 5),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))

        tabela.hAlign = 'CENTER'

        elementos.append(tabela)
        elementos.append(Spacer(1, 20))

        # -------- RODAPÉ -------- #
        elementos.append(Paragraph("Grace Kelly Rodrigues da Silva Santos", styles["Italic"]))
        elementos.append(Paragraph("Supervisor de Estatística, Pesquisa e Controle de Qualidade", styles["Italic"]))

        # Nova página para próxima classe
        elementos.append(PageBreak())

    doc.build(elementos)
# ====================================================

# ================== CONFIG ==========================
st.set_page_config(page_title="Sistema de Cotação", layout="wide")
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
        st.divider()

        # imagem com verificação mais segura
        img_path = "home.png"

        if os.path.exists(img_path):
            st.image(img_path, use_container_width=True)
        else:
            st.warning("Imagem 'home.png' não encontrada no diretório do projeto.")
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
        kg = st.number_input("Kg", min_value=0.0)
        
        if st.button("Cadastrar Produto"):
        
            try:
                supabase.table("produtos").insert({
                    "nome": nome.strip(),
                    "classe": classe,
                    "unidade": unidade,
                    "kg": kg
                }).execute()
        
                st.session_state.msg = ("success", "Produto cadastrado!")
        
            except Exception:
                st.session_state.msg = ("error", "Produto já existe!")
        
        st.divider()
    
        # LISTAR
        try:
            response = supabase.table("produtos").select("*").execute()
            df = pd.DataFrame(response.data)
        
            st.dataframe(df, use_container_width=True)
        
        except Exception as e:
            st.error(f"Erro ao carregar produtos: {e}")
        
        st.divider()
    
        # EDITAR / EXCLUIR
        if not df.empty:
    
            st.subheader("✏️ Editar / Excluir")
    
            produto_selecionado = st.selectbox("Produto", df["nome"])
            dados = df[df["nome"] == produto_selecionado].iloc[0]
    
            novo_nome = st.text_input("Nome", value=dados["nome"], key="edit_prod_nome")
    
            nova_classe = st.selectbox(
                "Classe",
                ["Hortaliças", "Frutas", "Especiarias", "Cereais"],
                index=["Hortaliças", "Frutas", "Especiarias", "Cereais"].index(dados["classe"]),
                key="edit_classe"
            )
    
            nova_unidade = st.selectbox(
                "Unidade",
                ["Kg", "Cx", "Sc", "Mo-4", "Mo-5", "Lt", "Centro", "Fd"],
                index=["Kg", "Cx", "Sc", "Mo-4", "Mo-5", "Lt", "Centro", "Fd"].index(dados["unidade"]),
                key="edit_unidade"
            )
    
            novo_kg = st.number_input("Kg", value=float(dados["kg"]))
    
            col1, col2 = st.columns(2)
    
            # UPDATE
            with col1:
                if st.button("✏️ Atualizar"):
            
                    try:
                        supabase.table("produtos").update({
                            "nome": novo_nome,
                            "classe": nova_classe,
                            "unidade": nova_unidade,
                            "kg": novo_kg
                        }).eq("id", int(dados["id"])).execute()
            
                        st.session_state.msg = ("success", "Produto atualizado!")
            
                    except Exception as e:
                        st.session_state.msg = ("error", str(e))
            
                    st.rerun()
    
            # DELETE
            with col2:
                if st.button("🗑️ Excluir"):
            
                    try:
                        supabase.table("produtos")\
                            .delete()\
                            .eq("id", int(dados["id"]))\
                            .execute()
            
                        st.session_state.msg = ("success", "Produto excluído!")
            
                    except Exception as e:
                        st.session_state.msg = ("error", str(e))
            
                    st.rerun()
    # =====================

    # ===================== COTAÇÃO
    elif opcao == "Cotação do Dia":

        st.title("📊 Cotação do Dia")

        # garante session_state
        if "confirmar_cotacao" not in st.session_state:
            st.session_state.confirmar_cotacao = False
        
        data = st.date_input("Data", value=pd.to_datetime("today"))
        
        # PRODUTOS
        try:
            resp = supabase.table("produtos").select("*").execute()
            produtos = pd.DataFrame(resp.data)
        except Exception as e:
            st.error(f"Erro ao carregar produtos: {e}")
            st.stop()
        
        if produtos.empty:
            st.warning("Cadastre produtos primeiro!")
            st.stop()
        
        cotacoes = []
        
        for _, row in produtos.iterrows():
            produto = row["nome"]
        
            # ÚLTIMA COTAÇÃO
            try:
                resp = supabase.table("cotacoes")\
                    .select("preco_min, preco_max, valor_kg")\
                    .eq("produto", produto)\
                    .order("data", desc=True)\
                    .limit(1)\
                    .execute()
        
                ultima = pd.DataFrame(resp.data)
        
            except Exception:
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
        # SALVAR
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
                                "data": str(data),
                                "classe": c[1],
                                "produto": c[0],
                                "unidade": c[2],
                                "kg": c[3],
                                "preco_min": c[4],
                                "preco_max": c[5],
                                "preco_medio": preco_medio,
                                "valor_kg": valor_kg
                            })
        
                        # Inserção no Supabase
                        response = supabase.table("cotacoes").insert(dados_insert).execute()
        
                        if response.data:
                            st.success("Cotação salva com sucesso!")
                        else:
                            st.error("Erro ao salvar dados.")
        
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
        
                    st.session_state.confirmar_cotacao = False
                    st.rerun()
        
            with c2:
                if st.button("❌ Cancelar"):
                    st.session_state.confirmar_cotacao = False
    # =====================

    # ===================== VISUALIZAR DADOS 
    elif opcao == "Visualizar Dados":

        st.title("📋 Cotações")
    
        try:
            resp = supabase.table("cotacoes").select("*").execute()
            df = pd.DataFrame(resp.data)
    
        except Exception as e:
            st.error(f"Erro ao carregar dados: {e}")
            st.stop()
    
        if df.empty:
            st.warning("Sem dados")
            st.stop()
    
        # DATA
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df = df.dropna(subset=["data"])
    
        # FILTROS
        col1, col2, col3 = st.columns(3)
    
        with col1:
            data_inicio = st.date_input("Data inicial", df["data"].min())
    
        with col2:
            data_fim = st.date_input("Data final", df["data"].max())
    
        with col3:
            classe = st.selectbox(
                "Classe",
                ["Todas", "Hortaliças", "Frutas", "Especiarias", "Cereais"]
            )
    
        # FILTRO
        df = df[
            (df["data"] >= pd.to_datetime(data_inicio)) &
            (df["data"] <= pd.to_datetime(data_fim))
        ]
    
        if classe != "Todas":
            df = df[df["classe"] == classe]
    
        # 🔥 IGUAL AO ANTIGO (REMOVE DATA)
        df_tabela = df.drop(columns=[c for c in ["id", "data"] if c in df.columns]).round(2)
    
        st.dataframe(df_tabela, use_container_width=True)
    
        # BOTÃO PDF (igual ao antigo)
        gerar_pdf_click = st.button("📄 Gerar PDF")
    
        # EXCEL
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
    
        # PDF
        if gerar_pdf_click:
    
            try:
                nome_pdf = f"cotacoes_{datetime.now().strftime('%d-%m-%Y')}.pdf"
    
                # ⚠️ IMPORTANTE: usar df ORIGINAL (com data e classe)
                gerar_pdf(df, nome_pdf)
    
                with open(nome_pdf, "rb") as f:
                    st.download_button(
                        "📥 Baixar PDF",
                        f,
                        file_name=nome_pdf
                    )
    
            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")
