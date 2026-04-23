import streamlit as st
import pandas as pd
from datetime import datetime
import io
import psycopg2
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from supabase import creat_client

# ------------------------------------------ #
def verificar_login(usuario, senha):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT nome, nivel
        FROM usuarios
        WHERE usuario = %s AND senha = %s
    """, (usuario, senha))

    resultado = cursor.fetchone()
    conn.close()
    return resultado

# ------------------ CONEXÃO ------------------ #
#def conectar():
 #   return psycopg2.connect(
  #      host="db.yovuvhuubopujagvukki.supabase.co",
   #      database="postgres",
    #     user="postgres",
     #   password="sb_publishable_xdViPgvmVxBvpjpNblJg6Q_sMX_QHje",
      #  port="5432"
    #)

url = "https://yovuvhuubopujagvukki.supabase.co/rest/v1/"
key = "sb_publishable_xdViPgvmVxBvpjpNblJg6Q_sMX_QHje"
supabase = create_client(url,key)


# ------------------ CONFIG ------------------ #
st.set_page_config(page_title="Sistema de Cotação", layout="wide")


# ------------------ ESTADO INICIAL ------------------ #
if "logado" not in st.session_state:
    st.session_state.logado = False
    st.session_state.nome = None
    st.session_state.nivel = None


# ------------------ LOGIN ------------------ #
if not st.session_state.logado:

    st.title("🔐 Login")

    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):

        resultado = verificar_login(usuario, senha) # verificar aqui

        if resultado:
            st.session_state.logado = True
            st.session_state.nome = resultado[0]
            st.session_state.nivel = resultado[1]

            st.rerun()

        else:
            st.error("Usuário ou senha inválidos")

    st.stop()  # 🔴 ESSENCIAL: impede o resto do app rodar


# ------------------ GERAR PDF ------------------ #
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

    # garante que existe coluna classe
    if "classe" not in df.columns:
        raise ValueError("Coluna 'classe' não encontrada")

    classes = df["classe"].unique()

    for c in classes:

        dados = df[df["classe"] == c].copy()

        if dados.empty:
            continue

        # ---------------- DATA ---------------- #
        if "data" not in dados.columns:
            raise ValueError("Coluna 'data' não encontrada")

        data_cotacao = pd.to_datetime(dados["data"].max()).strftime('%d/%m/%Y')
        data_emissao = datetime.now().strftime('%d/%m/%Y')

        # ---------------- LIMPEZA ---------------- #
        dados.drop(columns=[col for col in ["id", "classe"] if col in dados.columns], inplace=True)

        colunas_ordenadas = [
            "produto", "unidade", "kg",
            "preco_min", "preco_max",
            "preco_medio", "valor_kg"
        ]

        dados = dados[[c for c in colunas_ordenadas if c in dados.columns]]

        # ---------------- NOME COLUNAS ---------------- #
        dados.rename(columns={
            "produto": "Produto",
            "unidade": "Unidade",
            "kg": "Kg",
            "preco_min": "Preço Mín",
            "preco_max": "Preço Máx",
            "preco_medio": "Preço Médio",
            "valor_kg": "Valor/Kg"
        }, inplace=True)

        # ---------------- FORMATAÇÃO ---------------- #
        for col in dados.columns:
            if pd.api.types.is_numeric_dtype(dados[col]):
                dados[col] = dados[col].apply(
                    lambda x: f"{x:.2f}".replace(".", ",") if pd.notnull(x) else ""
                )

        # ---------------- CABEÇALHO ---------------- #
        estilo_titulo = styles["Title"]
        estilo_sub = styles["Italic"]

        elementos.append(Paragraph("AMA - Autarquia Municipal de Abastecimento", estilo_sub))
        elementos.append(Paragraph("Relatório de Cotação de Preços", estilo_titulo))
        elementos.append(Spacer(1, 8))

        # ---------------- INFO ---------------- #
        info = Table([[
            f"Classe: {c}",
            f"Cotação: {data_cotacao}",
            f"Emissão: {data_emissao}"
        ]], colWidths=[150, 150, 150])

        elementos.append(info)
        elementos.append(Spacer(1, 10))

        # ---------------- TABELA ---------------- #
        tabela = Table(
            [list(dados.columns)] + dados.values.tolist(),
            repeatRows=1
        )

        tabela.setStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.darkgreen),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ])

        elementos.append(tabela)
        elementos.append(PageBreak())

    doc.build(elementos)

# ------------------ SESSÃO ------------------ #
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


# ------------------ SISTEMA ------------------ #
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

    # ------------------ INÍCIO ------------------ #
    if opcao == "Início":

        st.title("📊 Sistema de Cotação")
        st.caption("Utilize o menu lateral para navegar pelas funcionalidades.")

        # espaço visual
        st.divider()

        # imagem com verificação mais segura
        import os
        img_path = "home.png"

        if os.path.exists(img_path):
            st.image(img_path, use_container_width=True)
        else:
            st.warning("Imagem 'home.png' não encontrada no diretório do projeto.")

    # ------------------ CADASTRO DE USUÁRIOS ------------------ #
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

        # ===================== CADASTRO =====================
        if st.button("Cadastrar Usuário"):
            conn = conectar()
            cursor = conn.cursor()
    
            try:
                cursor.execute("""
                    INSERT INTO usuarios (nome, usuario, senha, nivel)
                    VALUES (%s, %s, %s, %s)
                """, (nome, usuario, senha, nivel))
    
                conn.commit()
                st.success("Usuário cadastrado com sucesso!")
    
            except Exception as e:
                st.error(f"Erro ao cadastrar: {e}")
    
            finally:
                conn.close()
    
        st.divider()

        # ===================== LISTAR =====================
        conn = conectar()
        df = pd.read_sql_query("SELECT * FROM usuarios", conn)
        conn.close()

        st.dataframe(df, use_container_width=True)
        st.divider()
    
        # ===================== EDITAR / EXCLUIR =====================
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

            # ===================== ATUALIZAR =====================
            with col1:
                if st.button("✏️ Atualizar Usuário"):
    
                    conn = conectar()
                    cursor = conn.cursor()
    
                    try:
                        cursor.execute("""
                            UPDATE usuarios
                            SET nome=%s, usuario=%s, senha=%s, nivel=%s
                            WHERE id=%s
                        """, (
                            novo_nome,
                            novo_usuario,
                            nova_senha,
                            novo_nivel,
                            int(dados["id"])
                        ))
    
                        conn.commit()
                        st.success("Usuário atualizado!")
    
                    except Exception as e:
                        st.error(f"Erro ao atualizar: {e}")
    
                    finally:
                        conn.close()
    
                    st.rerun()
    
            # ===================== EXCLUIR =====================
            with col2:
                if st.button("🗑️ Excluir Usuário"):
    
                    conn = conectar()
                    cursor = conn.cursor()
    
                    try:
                        cursor.execute("DELETE FROM usuarios WHERE id=%s", (int(dados["id"]),))
                        conn.commit()
                        st.success("Usuário excluído!")
    
                    except Exception as e:
                        st.error(f"Erro ao excluir: {e}")
    
                    finally:
                        conn.close()
    
                    st.rerun()
        
    # ------------------ CADASTRO DE PRODUTOS ------------------ #
    elif opcao == "Cadastro de Produtos":
    
        st.title("📦 Cadastro de Produtos")
    
        # garante session_state
        for k in ["confirmar_cadastro_produto", "confirmar_edicao", "confirmar_exclusao"]:
            if k not in st.session_state:
                st.session_state[k] = False

        # ===================== MENSAGEM =====================
        if "msg" in st.session_state and st.session_state.msg:
            tipo, texto = st.session_state.msg
            if tipo == "success":
                st.success(texto)
            else:
                st.error(texto)
            st.session_state.msg = None
    
        # ===================== NOVO PRODUTO =====================
        st.subheader("➕ Novo Produto")
    
        nome = st.text_input("Nome")
        classe = st.selectbox("Classe", ["Hortaliças", "Frutas", "Especiarias", "Cereais"])
        unidade = st.selectbox("Unidade", ["Kg", "Cx", "Sc", "Mo-4", "Mo-5", "Lt", "Centro", "Fd"])
        kg = st.number_input("Kg", min_value=0.0)
    
        if st.button("Cadastrar Produto"):
    
            conn = conectar()
            cursor = conn.cursor()
    
            try:
                cursor.execute("""
                    INSERT INTO produtos (nome, classe, unidade, kg)
                    VALUES (%s, %s, %s, %s)
                """, (nome.strip(), classe, unidade, kg))
    
                conn.commit()
                st.session_state.msg = ("success", "Produto cadastrado!")
    
            except Exception:
                st.session_state.msg = ("error", "Produto já existe!")
    
            finally:
                conn.close()
    
        st.divider()
    
        # ===================== LISTAR =====================
        conn = conectar()
        df = pd.read_sql_query("SELECT * FROM produtos", conn)
        conn.close()
    
        st.dataframe(df, use_container_width=True)
    
        st.divider()
    
        # ===================== EDITAR / EXCLUIR =====================
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
    
            # ===================== UPDATE =====================
            with col1:
                if st.button("✏️ Atualizar"):
    
                    conn = conectar()
                    cursor = conn.cursor()
    
                    try:
                        cursor.execute("""
                            UPDATE produtos
                            SET nome=%s, classe=%s, unidade=%s, kg=%s
                            WHERE id=%s
                        """, (
                            novo_nome,
                            nova_classe,
                            nova_unidade,
                            novo_kg,
                            int(dados["id"])
                        ))
    
                        conn.commit()
                        st.session_state.msg = ("success", "Produto atualizado!")
    
                    except Exception as e:
                        st.session_state.msg = ("error", str(e))
    
                    finally:
                        conn.close()
    
                    st.rerun()
    
            # ===================== DELETE =====================
            with col2:
                if st.button("🗑️ Excluir"):
    
                    conn = conectar()
                    cursor = conn.cursor()
    
                    try:
                        cursor.execute("DELETE FROM produtos WHERE id=%s", (int(dados["id"]),))
                        conn.commit()
                        st.session_state.msg = ("success", "Produto excluído!")
    
                    except Exception as e:
                        st.session_state.msg = ("error", str(e))
    
                    finally:
                        conn.close()
    
                    st.rerun()

    # ------------------ COTAÇÃO ------------------ #
    elif opcao == "Cotação do Dia":

        st.title("📊 Cotação do Dia")

        # garante session_state
        if "confirmar_cotacao" not in st.session_state:
            st.session_state.confirmar_cotacao = False

        data = st.date_input("Data", value=pd.to_datetime("today"))

        conn = conectar()
        produtos = pd.read_sql_query("SELECT * FROM produtos", conn)

        if produtos.empty:
            st.warning("Cadastre produtos primeiro!")
            conn.close()
            st.stop()

        cotacoes = []

        for _, row in produtos.iterrows():
            produto = row["nome"]

            ultima = pd.read_sql_query("""
                SELECT preco_min, preco_max, valor_kg
                FROM cotacoes
                WHERE produto = %s
                ORDER BY data DESC
                LIMIT 1
            """, conn, params=(produto,))

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

        # ===================== SALVAR =====================
        if not st.session_state.confirmar_cotacao:
    
            if st.button("💾 Salvar Cotação"):
                st.session_state.confirmar_cotacao = True
    
        else:
            st.warning("Confirmar salvamento?")
            c1, c2 = st.columns(2)
    
            with c1:
                if st.button("✅ Confirmar"):
    
                    cursor = conn.cursor()
    
                    try:
                        for c in cotacoes:
                            cursor.execute("""
                                INSERT INTO cotacoes (
                                    data, classe, produto, unidade, kg,
                                    preco_min, preco_max, preco_medio, valor_kg
                                )
                                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                            """, (
                                str(data), c[1], c[0], c[2], c[3],
                                c[4], c[5],
                                (c[4] + c[5]) / 2,
                                ((c[4] + c[5]) / 2) / c[3] if c[3] > 0 else 0
                            ))
    
                        conn.commit()
                        st.success("Cotação salva com sucesso!")
    
                    except Exception as e:
                        st.error(f"Erro ao salvar: {e}")
    
                    finally:
                        conn.close()
    
                    st.session_state.confirmar_cotacao = False
                    st.rerun()
    
            with c2:
                if st.button("❌ Cancelar"):
                    st.session_state.confirmar_cotacao = False
    
        conn.close()

   # ------------------ VISUALIZAR DADOS ------------------ #
    elif opcao == "Visualizar Dados":
    
        st.title("📋 Cotações")
    
        conn = conectar()
        df = pd.read_sql_query("SELECT * FROM cotacoes", conn)
        conn.close()
    
        if df.empty:
            st.warning("Sem dados")
            st.stop()
    
        # ===================== TRATAMENTO DE DATA =====================
        df["data"] = pd.to_datetime(df["data"], errors="coerce")
        df = df.dropna(subset=["data"])
    
        # ===================== FILTROS =====================
        col1, col2, col3 = st.columns(3)
    
        with col1:
            data_inicio = pd.to_datetime(
                st.date_input("Data inicial", df["data"].min().date())
            )
    
        with col2:
            data_fim = pd.to_datetime(
                st.date_input("Data final", df["data"].max().date())
            )
    
        with col3:
            classe = st.selectbox(
                "Classe",
                ["Todas", "Hortaliças", "Frutas", "Especiarias", "Cereais"]
            )
    
        # ===================== FILTRO =====================
        df_filtrado = df[
            (df["data"] >= data_inicio) &
            (df["data"] <= data_fim)
        ]
    
        if classe != "Todas":
            df_filtrado = df_filtrado[df_filtrado["classe"] == classe]
    
        # ===================== TABELA =====================
        cols_drop = [c for c in ["id"] if c in df_filtrado.columns]
        df_tabela = df_filtrado.drop(columns=cols_drop).round(2)
    
        st.dataframe(df_tabela, use_container_width=True)
    
        # ===================== PDF =====================
        if st.button("📄 Gerar PDF"):
    
            try:
                nome_pdf = f"cotacoes_{datetime.now().strftime('%d-%m-%Y')}.pdf"
                gerar_pdf(df_filtrado, nome_pdf)
                st.session_state["pdf_gerado"] = nome_pdf
                st.success("PDF gerado com sucesso!")
    
            except Exception as e:
                st.error(f"Erro ao gerar PDF: {e}")
    
        # ===================== EXCEL =====================
        if st.session_state.get("nivel") == "admin":
    
            try:
                buffer = io.BytesIO()
                df_filtrado.to_excel(buffer, index=False, engine="openpyxl")
                buffer.seek(0)
    
                st.download_button(
                    "📥 Baixar Excel",
                    buffer,
                    file_name=f"cotacoes_{datetime.now().strftime('%d-%m-%Y')}.xlsx"
                )
    
            except Exception as e:
                st.error(f"Erro ao gerar Excel: {e}")
    
        # ===================== DOWNLOAD PDF =====================
        if st.session_state.get("pdf_gerado"):
    
            try:
                with open(st.session_state["pdf_gerado"], "rb") as f:
                    st.download_button(
                        "📥 Baixar PDF",
                        f,
                        file_name=st.session_state["pdf_gerado"]
                    )
    
            except FileNotFoundError:
                st.warning("PDF não encontrado. Gere novamente.")
