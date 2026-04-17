import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime
import io
import streamlit as st

def set_background(image_path):
    st.markdown(
        '<style>'
        '.stApp {'
        'background-image: url("' + image_path + '");'
        'background-size: cover;'
        'background-position: center;'
        'background-repeat: no-repeat;'
        '}'
        '</style>',
        unsafe_allow_html=True
    )

set_background("home.png")

# ------------------ CONEXÃO ------------------ #
def conectar():
    return sqlite3.connect("database.db")

# ------------------ LOGIN ------------------ #
def verificar_login(usuario, senha):
    conn = conectar()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT nome, nivel FROM usuarios
        WHERE usuario = ? AND senha = ?
    """, (usuario, senha))

    resultado = cursor.fetchone()
    conn.close()
    return resultado

# ------------------ GERAR PDF ------------------ #
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime

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

    classes = df["classe"].unique()

    for c in classes:
        dados_classe = df[df["classe"] == c]

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
        for col in dados_classe.columns:
            if pd.api.types.is_numeric_dtype(dados_classe[col]):
                dados_classe[col] = dados_classe[col].apply(
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
        elementos.append(PageBreak())

    doc.build(elementos)

# ------------------ CONFIG ------------------ #
st.set_page_config(page_title="Sistema de Cotação", layout="wide")

# ------------------ SESSÃO ------------------ #
if "logado" not in st.session_state:
    st.session_state.logado = False

if "msg" not in st.session_state:
    st.session_state.msg = None

if "confirmar_exclusao" not in st.session_state:
    st.session_state.confirmar_exclusao = False

if "confirmar_edicao" not in st.session_state:
    st.session_state.confirmar_edicao = False

if "confirmar_cotacao" not in st.session_state:
    st.session_state.confirmar_cotacao = False

if "confirmar_usuario" not in st.session_state:
    st.session_state.confirmar_usuario = False

if "confirmar_edicao_usuario" not in st.session_state:
    st.session_state.confirmar_edicao_usuario = False

if "confirmar_exclusao_usuario" not in st.session_state:
    st.session_state.confirmar_exclusao_usuario = False

if "confirmar_cadastro_produto" not in st.session_state:
    st.session_state.confirmar_cadastro_produto = False

# ------------------ LOGIN ------------------ #
if not st.session_state.logado:

    st.title("🔐 Login do Sistema")

    usuario = st.text_input("Usuário")
    senha = st.text_input("Senha", type="password")

    if st.button("Entrar"):
        resultado = verificar_login(usuario, senha)

        if resultado:
            st.session_state.logado = True
            st.session_state.nome = resultado[0]
            st.session_state.nivel = resultado[1]
            st.rerun()
        else:
            st.error("Usuário ou senha inválidos")

# ------------------ SISTEMA ------------------ #
else:
    st.sidebar.title("📌 Menu")

    if st.session_state.nivel == "admin":
        menu = ["Início", "Cadastro de Usuários", "Cadastro de Produtos", "Cotação do Dia", "Visualizar Dados"]
    elif st.session_state.nivel == "cotacao":
        menu = ["Início", "Cotação do Dia", "Visualizar Dados"]
    else:
        menu = ["Início", "Visualizar Dados"]

    opcao = st.sidebar.selectbox("Escolha uma opção:", menu)

    st.sidebar.write(f"👤 {st.session_state.nome}")
    st.sidebar.write(f"🔑 {st.session_state.nivel}")

    if st.sidebar.button("🚪 Sair"):
        st.session_state.clear()
        st.rerun()

    # ------------------ INÍCIO ------------------ #
    if opcao == "Início":

        st.title("📊 Sistema de Cotação")
        st.markdown("### Bem-vindo ao sistema")
        st.markdown(
            "<small><i>Utilize o menu lateral para navegar pelas funcionalidades.</i></small>",
            unsafe_allow_html=True
        )

    # ------------------ CADASTRO DE USUÁRIOS ------------------ #
    elif opcao == "Cadastro de Usuários":
        st.title("👤 Cadastro de Usuários")

        conn = conectar()

        st.subheader("➕ Novo Usuário")

        nome = st.text_input("Nome", key="user_nome")
        usuario = st.text_input("Usuário", key="user_usuario")
        senha = st.text_input("Senha", type="password", key="user_senha")
        nivel = st.selectbox("Nível", ["admin", "cotacao", "visitante"], key="user_nivel")

        if not st.session_state.confirmar_usuario:
            if st.button("Cadastrar Usuário"):
                st.session_state.confirmar_usuario = True
        else:
            st.warning("Confirmar cadastro do usuário?")
            c1, c2 = st.columns(2)

            with c1:
                if st.button("✅ Confirmar Cadastro"):
                    try:
                        conn.execute("""
                            INSERT INTO usuarios (nome, usuario, senha, nivel)
                            VALUES (?, ?, ?, ?)
                        """, (nome.strip(), usuario.strip(), senha, nivel))
                        conn.commit()

                        st.success("Usuário cadastrado com sucesso!")
                        st.session_state.confirmar_usuario = False
                        st.rerun()

                    except sqlite3.IntegrityError:
                        st.error("Usuário já existe!")
                        st.session_state.confirmar_usuario = False

            with c2:
                if st.button("❌ Cancelar Cadastro"):
                    st.session_state.confirmar_usuario = False

        st.divider()

        df = pd.read_sql_query("SELECT * FROM usuarios", conn)
        st.dataframe(df, use_container_width=True)

        st.divider()

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

            with col1:
                if not st.session_state.confirmar_edicao_usuario:
                    if st.button("✏️ Atualizar Usuário"):
                        st.session_state.confirmar_edicao_usuario = True
                else:
                    st.warning("Confirmar atualização?")
                    c1, c2 = st.columns(2)

                    with c1:
                        if st.button("✅ Confirmar Atualização"):
                            conn.execute("""
                                UPDATE usuarios
                                SET nome=?, usuario=?, senha=?, nivel=?
                                WHERE id=?
                            """, (
                                novo_nome,
                                novo_usuario,
                                nova_senha,
                                novo_nivel,
                                int(dados["id"])
                            ))
                            conn.commit()
                            st.success("Usuário atualizado!")
                            st.session_state.confirmar_edicao_usuario = False
                            st.rerun()

                    with c2:
                        if st.button("❌ Cancelar Atualização"):
                            st.session_state.confirmar_edicao_usuario = False

            with col2:
                if not st.session_state.confirmar_exclusao_usuario:
                    if st.button("🗑️ Excluir Usuário"):
                        st.session_state.confirmar_exclusao_usuario = True
                else:
                    st.warning("Confirmar exclusão?")
                    c1, c2 = st.columns(2)

                    with c1:
                        if st.button("✅ Confirmar Exclusão"):
                            conn.execute("DELETE FROM usuarios WHERE id=?", (int(dados["id"]),))
                            conn.commit()
                            st.success("Usuário excluído!")
                            st.session_state.confirmar_exclusao_usuario = False
                            st.rerun()

                    with c2:
                        if st.button("❌ Cancelar Exclusão"):
                            st.session_state.confirmar_exclusao_usuario = False

        conn.close()
    
    # ------------------ CADASTRO DE PRODUTOS ------------------ #
    elif opcao == "Cadastro de Produtos":
        st.title("📦 Cadastro de Produtos")

        conn = conectar()

        if st.session_state.msg:
            tipo, texto = st.session_state.msg
            if tipo == "success":
                st.success(texto)
            else:
                st.error(texto)
            st.session_state.msg = None

        st.subheader("➕ Novo Produto")

        nome = st.text_input("Nome")
        classe = st.selectbox("Classe", ["Hortaliças", "Frutas", "Especiarias", "Cereais"])
        unidade = st.selectbox("Unidade", ["Kg", "Cx", "Sc", "Mo-4", "Mo-5", "Lt", "Centro", "Fd"])
        kg = st.number_input("Kg", min_value=0.0)

        # -------- CONFIRMAR CADASTRO DE PRODUTO -------- #
        if not st.session_state.confirmar_cadastro_produto:
            if st.button("Cadastrar Produto"):
                st.session_state.confirmar_cadastro_produto = True
        else:
            st.warning("Confirmar cadastro do produto?")
            c1, c2 = st.columns(2)

            with c1:
                if st.button("✅ Confirmar Produto"):
                    try:
                        conn.execute("""
                            INSERT INTO produtos (nome, classe, unidade, kg)
                            VALUES (?, ?, ?, ?)
                        """, (nome.strip(), classe, unidade, kg))
                        conn.commit()
                        st.session_state.msg = ("success", "Produto cadastrado!")
                    except:
                        st.session_state.msg = ("error", "Produto já existe!")

                    st.session_state.confirmar_cadastro_produto = False
                    st.rerun()

            with c2:
                if st.button("❌ Cancelar Produto"):
                    st.session_state.confirmar_cadastro_produto = False
        
        st.divider()

        df = pd.read_sql_query("SELECT * FROM produtos", conn)
        st.dataframe(df, use_container_width=True)

        st.divider()

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

            with col1:
                if not st.session_state.confirmar_edicao:
                    if st.button("✏️ Atualizar"):
                        st.session_state.confirmar_edicao = True
                else:
                    st.warning("Confirmar atualização?")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Confirmar"):
                            conn.execute("""
                                UPDATE produtos
                                SET nome=?, classe=?, unidade=?, kg=?
                                WHERE id=?
                            """, (novo_nome, nova_classe, nova_unidade, novo_kg, int(dados["id"])))
                            conn.commit()
                            st.session_state.msg = ("success", "Produto atualizado!")
                            st.session_state.confirmar_edicao = False
                            st.rerun()
                    with c2:
                        if st.button("❌ Cancelar"):
                            st.session_state.confirmar_edicao = False

            with col2:
                if not st.session_state.confirmar_exclusao:
                    if st.button("🗑️ Excluir"):
                        st.session_state.confirmar_exclusao = True
                else:
                    st.warning("Confirmar exclusão?")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Confirmar Exclusão"):
                            conn.execute("DELETE FROM produtos WHERE id=?", (int(dados["id"]),))
                            conn.commit()
                            st.session_state.msg = ("success", "Produto excluído!")
                            st.session_state.confirmar_exclusao = False
                            st.rerun()
                    with c2:
                        if st.button("❌ Cancelar Exclusão"):
                            st.session_state.confirmar_exclusao = False

        conn.close()

    # ------------------ COTAÇÃO ------------------ #
    elif opcao == "Cotação do Dia":
        st.title("📊 Cotação do Dia")

        data = st.date_input("Data", value=pd.to_datetime("today"))
        conn = conectar()

        produtos = pd.read_sql_query("SELECT * FROM produtos", conn)

        if produtos.empty:
            st.warning("Cadastre produtos primeiro!")
        else:
            cotacoes = []

            for _, row in produtos.iterrows():
                produto = row["nome"]

                ultima = pd.read_sql_query("""
                    SELECT preco_min, preco_max, valor_kg
                    FROM cotacoes
                    WHERE produto = ?
                    ORDER BY data DESC
                    LIMIT 1
                """, conn, params=(produto,))

                pmin_padrao = float(ultima.iloc[0]["preco_min"]) if not ultima.empty else 0.0
                pmax_padrao = float(ultima.iloc[0]["preco_max"]) if not ultima.empty else 0.0

                col1, col2 = st.columns([1,2])

                with col1:
                    st.write(produto)

                with col2:
                    st.write("Adicionar preços:")

                    # inicializa lista com última cotação
                    if f"precos_{produto}" not in st.session_state:
                        if not ultima.empty:
                            st.session_state[f"precos_{produto}"] = [
                                float(ultima.iloc[0]["preco_min"]),
                                float(ultima.iloc[0]["preco_max"])
                            ]
                        else:
                            st.session_state[f"precos_{produto}"] = []

                    precos = st.session_state[f"precos_{produto}"]

                    # 🔹 BOTÕES LADO A LADO
                    b1, b2 = st.columns(2)

                    with b1:
                        if st.button(f"➕ Adicionar", key=f"add_{produto}"):
                            precos.append(0.0)

                    with b2:
                        if precos and st.button(f"➖ Remover", key=f"rem_{produto}"):
                            precos.pop()

                    # 🔹 PREÇOS LADO A LADO (3 por linha)
                    cols = st.columns(3)

                    for i in range(len(precos)):
                        col = cols[i % 3]
                        with col:
                            precos[i] = st.number_input(
                                f"P{i+1}",
                                value=precos[i],
                                key=f"{produto}_{i}"
                            )

                    # 🔹 CÁLCULOS
                    precos_validos = [p for p in precos if p > 0]

                    if precos_validos:
                        pmin = min(precos_validos)
                        pmax = max(precos_validos)
                        preco_medio = sum(precos_validos) / len(precos_validos)
                    else:
                        pmin = pmax = preco_medio = 0

                    valor_kg = (preco_medio / row["kg"]) if row["kg"] > 0 else 0

                # 🔹 RESULTADOS (TODOS LADO A LADO)
                def formatar(valor):
                    return f"{valor:.2f}".replace(".", ",")
                st.caption(
                    f"🔽 Mín: {pmin:.2f}   🔼 Máx: {pmax:.2f}   📊 Médio: {preco_medio:.2f}   ⚖️ Valor/Kg: {valor_kg:.2f}"
                )

                #preco_medio = (pmin + pmax) / 2 if (pmin > 0 or pmax > 0) else 0
                #valor_kg = (preco_medio / row["kg"]) if row["kg"] > 0 else 0
                #st.caption(f"Preço médio: {preco_medio:.2f} | Valor/kg: {valor_kg:.2f}")

                    # 🔔 ALERTA DE VARIAÇÃO
                if not ultima.empty:
                    valor_kg_anterior = float(ultima.iloc[0]["valor_kg"])

                    if valor_kg_anterior > 0:
                        variacao = ((valor_kg - valor_kg_anterior) / valor_kg_anterior) * 100

                        if abs(variacao) > 30:
                            st.warning(f"⚠️ Variação alta: {variacao:.1f}% em relação à última cotação")

                st.divider()

                cotacoes.append((produto, row["classe"], row["unidade"], row["kg"], pmin, pmax))

            if not st.session_state.confirmar_cotacao:
                if st.button("💾 Salvar Cotação"):
                    st.session_state.confirmar_cotacao = True
            else:
                st.warning("Confirmar salvamento?")
                c1, c2 = st.columns(2)

                with c1:
                    if st.button("✅ Confirmar"):
                        for c in cotacoes:
                            conn.execute("""
                                INSERT INTO cotacoes (
                                    data, classe, produto, unidade, kg,
                                    preco_min, preco_max, preco_medio, valor_kg
                                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                str(data), c[1], c[0], c[2], c[3],
                                c[4], c[5],
                                (c[4]+c[5])/2,
                                ((c[4]+c[5])/2)/c[3] if c[3] > 0 else 0
                            ))

                        conn.commit()
                        st.success("Cotação salva com sucesso!")
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

        if not df.empty:
            df["data"] = pd.to_datetime(df["data"])

            col1, col2, col3 = st.columns(3)

            with col1:
                data_inicio = st.date_input("Data inicial", df["data"].min())

            with col2:
                data_fim = st.date_input("Data final", df["data"].max())

            with col3:
                classe = st.selectbox("Classe", ["Todas","Hortaliças","Frutas","Especiarias","Cereais"])

            df = df[(df["data"] >= pd.to_datetime(data_inicio)) & (df["data"] <= pd.to_datetime(data_fim))]

            if classe != "Todas":
                df = df[df["classe"] == classe]

            # df continua com a coluna data (para o PDF)

            df_tabela = df.drop(columns=["id","data"]).round(2)

            # mostra só a tabela limpa
            st.dataframe(df_tabela, use_container_width=True)

            # usa o df completo no PDF
            # botão
            gerar_pdf_click = st.button("📄 Gerar PDF")

            if gerar_pdf_click:
                nome_pdf = f"cotacoes_{datetime.now().strftime('%d-%m-%Y')}.pdf"
                gerar_pdf(df, nome_pdf)
                st.session_state["pdf_gerado"] = nome_pdf

            # Excel (admin)
            if st.session_state.nivel == "admin":
                buffer = io.BytesIO()
                df.to_excel(buffer, index=False, engine="openpyxl")
                buffer.seek(0)

                st.download_button(
                    "📥 Baixar Excel",
                    buffer,
                    file_name=f"cotacoes_{datetime.now().strftime('%d-%m-%Y')}.xlsx"
                )

            # botão de download separado
            if "pdf_gerado" in st.session_state:
                with open(st.session_state["pdf_gerado"], "rb") as f:
                    st.download_button(
                        "📥 Baixar PDF",
                        f,
                        file_name=st.session_state["pdf_gerado"]
                    )

        else:
            st.warning("Sem dados")
