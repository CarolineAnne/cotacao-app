# Sistema de Cotação

Aplicação interna em Streamlit para registrar cotações, acompanhar produtos, receber respostas de permissionários, gerar relatórios e apoiar análises de preços.

## Principais recursos

- Login com níveis de acesso: `admin`, `cotacao` e `requisitante`.
- Cadastro de usuários e produtos.
- Cotação do dia com preços mínimo, máximo, médio e valor por kg.
- Consulta e exportação de cotações em PDF e Excel.
- Importação de dados por Excel.
- Solicitações internas por tipo e status.
- Gestão de permissionários, envio de links e recebimento de respostas públicas.
- Observações sobre produtos para apoiar relatórios.
- Relatórios diário, semanal e semestral.
- Posts analíticos, destaques do dia e post unitário por produto.
- Acompanhamento de ações do sistema.

## Requisitos

- Python 3.10 ou superior.
- Conta/projeto Supabase configurado.
- Dependências listadas em `requirements.txt`.

## Instalação local

Crie e ative o ambiente virtual:

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
```

Instale as dependências:

```powershell
pip install -r requirements.txt
```

## Configuração

O app lê as credenciais do Supabase pelo arquivo `.streamlit/secrets.toml`.

Crie o arquivo abaixo localmente:

```toml
SUPABASE_URL = "https://seu-projeto.supabase.co"
SUPABASE_KEY = "sua-chave-do-supabase"
```

Importante: não envie `.env`, `.env.*` nem `.streamlit/secrets.toml` para o Git. Esses arquivos já estão no `.gitignore`.

## Como rodar

No Windows, você pode abrir o sistema dando dois cliques em:

```text
abrir_sistema.bat
```

Esse arquivo usa o Python do `venv` do projeto, evitando erro de pacote ausente como `ModuleNotFoundError`.

Se preferir rodar manualmente, execute:

```powershell
venv\Scripts\python.exe -m streamlit run app.py
```

O Streamlit mostrará o endereço local para abrir no navegador.

## Automação opcional de WhatsApp

O envio automático de links para permissionários fica no arquivo `automacao_whatsapp.py`.
Por segurança, ele roda em modo de simulação por padrão e não envia mensagens sem a opção `--send`.

Crie um arquivo `.env` local com as variáveis abaixo, sem enviar esse arquivo para o Git:

```env
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-chave-do-supabase
WHATSAPP_TOKEN=seu-token-da-api
WHATSAPP_PHONE_NUMBER_ID=seu-phone-number-id
WHATSAPP_API_VERSION=v21.0
WHATSAPP_TEMPLATE_NAME=link_cotacao_diaria
WHATSAPP_TEMPLATE_LANGUAGE=pt_BR
```

Comandos úteis:

```powershell
venv\Scripts\python.exe automacao_whatsapp.py --check
venv\Scripts\python.exe automacao_whatsapp.py --once --dry-run
venv\Scripts\python.exe automacao_whatsapp.py --once --send
venv\Scripts\python.exe automacao_whatsapp.py --schedule --send
```

Antes de usar `--send`, confirme que a URL pública do sistema, o template aprovado no WhatsApp e a configuração `ativo` dos permissionários estão corretos.

Para links de permissionários, use somente URL pública com `https://`. O sistema bloqueia `http://` para evitar envio de token por conexão insegura.

## Segurança aplicada

- Senhas salvas com hash protegido e migração automática de senhas antigas.
- Bloqueio temporário após tentativas repetidas de login inválido.
- Permissões centralizadas por tela para os níveis `admin`, `cotacao` e `requisitante`.
- Upload de fotos limitado a JPG, PNG e WEBP, com validação de tamanho e conteúdo.
- Links públicos de permissionários obrigatoriamente com `https://`.
- Dependências principais travadas no `requirements.txt`.
- Arquivos sensíveis locais ignorados pelo Git.

## Testes

Os testes usam `unittest`, que já vem com Python. Para executar:

```powershell
venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Estrutura geral

- `app.py`: entrada principal, login, menus e navegação.
- `db.py`: conexão com Supabase.
- `auth_utils.py`: geração e validação de senha protegida.
- `dados_utils.py`: carregamentos gerais e registro de ações.
- `cotacao_utils.py`: regras de cálculo e preparação da cotação.
- `cotacao_repository.py`: gravação protegida das cotações.
- `relatorio_utils.py`: funções comuns de formatação e ordenação dos relatórios.
- `relatorio_diario.py`, `relatorio_semanal.py`, `relatorio_semestral.py`: geração e telas dos relatórios.
- `permissionarios.py`: cadastro, links públicos, respostas e fotos de permissionários.
- `automacao_whatsapp.py`: automação opcional para envio de links via WhatsApp Cloud API.
- `produtos.py`, `usuarios.py`, `solicitacoes.py`: telas administrativas e operacionais.
- `tela_acompanhamento.py`: consulta e exportação dos registros de atividade do sistema.
- `tela_cotacao_dia.py`: formulário e salvamento da cotação diária.
- `post_produto_unitario.py`: tela Streamlit para gerar posts unitários de produtos.
- `post_produto_posts.py`: geração dos PNGs e ZIP dos posts de produto.
- `tela_sobre_produtos.py`: cadastro, consulta e PDF das informações dos produtos.
- `tela_visualizar_dados.py`: consulta, PDF e exportações de cotações.
- `tela_importacoes_excel.py`: importação de planilhas.
- `pdf_utils.py`: geração de PDFs gerais.
- `legacy/`: arquivos antigos da versão SQLite local, mantidos fora do fluxo principal.
- `tests/`: testes automatizados mínimos dos utilitários e gravação protegida.

## Cuidados operacionais

- Antes de substituir cotações de uma data, confira se a data selecionada está correta.
- Arquivos PDF gerados localmente são ignorados pelo Git.
- Evite versionar bancos locais, chaves, tokens ou arquivos de teste com dados reais.
- Para mudanças em relatórios, valide pelo menos um PDF gerado antes de usar em produção.

## Observações para manutenção

O projeto vem sendo organizado aos poucos para reduzir arquivos grandes e funções repetidas. A preferência é fazer melhorias pequenas, testáveis e sem alterar o comportamento da tela quando não for necessário.
