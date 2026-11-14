# Back-end do Troc.ai

API REST em Flask integrada ao SQLite já existente em `Bd - Troc.AI`.

## 1. Preparar o ambiente

Na pasta raiz do repositório:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
source .venv/bin/activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

## 2. Executar a API

Na pasta raiz do repositório:

```bash
python -m backend.app
```

A API ficará disponível em `http://127.0.0.1:3001`.
Na primeira execução, o banco é criado automaticamente e recebe os cinco perfis de demonstração.

Para não inserir os perfis demonstrativos em um banco novo, defina `TROCAI_SEED_DEMO=0` antes de iniciar o servidor.
Para usar outro arquivo SQLite, defina `TROCAI_DATABASE` com o caminho desejado.

A especificação completa dos contratos HTTP, exemplos de requisição/resposta, códigos de erro e orientações para o front-end está em [`../docs/API.md`](../docs/API.md).

Para executar os testes do banco, dos serviços e do contrato HTTP (com as dependências instaladas):

```bash
python "Bd - Troc.AI/testes.py"
python -m unittest backend.test_services -v
python -m unittest backend.test_service_input_validation -v
python -m unittest backend.test_api_contract -v
python -m unittest backend.test_input_validation -v
python -m unittest backend.test_auth -v
```

## 3. Validação das entradas

A API valida os tipos, formatos e limites dos campos antes de chamar a camada de persistência. O contrato rejeita propriedades JSON desconhecidas, habilidades fora do catálogo, habilidades repetidas entre `skills_out` e `skills_in`, identificadores que não sejam inteiros positivos e conteúdo que não esteja em JSON. O corpo máximo é de 64 KiB. Os limites por campo estão detalhados em `../docs/API.md`.

## 4. Endpoints iniciais

| Método | Endpoint | Descrição |
|---|---|---|
| GET | `/api/health` | Verifica se a API está ativa. |
| GET | `/api/opcoes` | Lista categorias, habilidades e níveis. |
| POST | `/api/usuarios` | Cadastra usuário e habilidades OUT/IN. |
| POST | `/api/login` | Valida e-mail e senha. |
| GET | `/api/usuarios/{id}` | Consulta um perfil. |
| GET | `/api/sessao` | Identifica o usuário autenticado. |
| POST | `/api/logout` | Encerra a sessão atual. |
| GET | `/api/sugestoes?limite=10` | Lista sugestões do usuário autenticado. |
| POST | `/api/interacoes` | Registra `CONECTAR` ou `DESCARTAR` em nome do usuário autenticado. |
| GET | `/api/matches` | Lista os matches do usuário autenticado. |

### Exemplo: cadastrar usuário

```json
{
  "nome": "Ana Souza",
  "email": "ana@example.com",
  "senha": "senha123",
  "cidade": "São Paulo",
  "zona": "Zona Sul",
  "skills_out": ["Python", "SQL", "Git"],
  "skills_in": ["Inglês"]
}
```

Os nomes das habilidades precisam existir no catálogo retornado por `/api/opcoes`.

### Exemplo: registrar interesse

Após autenticar com `POST /api/login`, o navegador mantém o cookie de sessão. O corpo não informa quem está realizando a ação:

```json
{
  "para_usuario_id": 1046,
  "acao": "CONECTAR"
}
```

O autor é obtido da sessão, não de um identificador enviado pelo front-end. Para consultar a identidade atual, use `GET /api/sessao`; para sair, use `POST /api/logout`.

Um registro em `matches` só é criado quando os dois usuários registram `CONECTAR` um para o outro.

## 5. Decisão de integração

O banco existente é a fonte de verdade do domínio: `usuarios`, `habilidades` e `usuario_habilidades` representam pessoas e os conhecimentos que oferecem (`OUT`) ou desejam aprender (`IN`). A API não cria uma tabela paralela `conhecimentos` porque isso duplicaria o catálogo e não representa o matching entre usuários implementado no banco.

O front-end atual ainda usa o contrato antigo de `conhecimentos` (oferta/demanda com descrição, nível e disponibilidade). Ele precisará ser adaptado aos endpoints e ao modelo acima. Essa adaptação é a próxima etapa da integração.

## 6. Sessão de usuário no protótipo

A API usa um cookie de sessão Flask assinado (o conteúdo é assinado, não criptografado). Para desenvolvimento local, a aplicação possui uma chave padrão que gera um aviso no log. Para definir uma chave específica no PowerShell antes de iniciar a API:

```powershell
$bytes = New-Object byte[] 32
$rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
$rng.GetBytes($bytes)
$rng.Dispose()
$env:TROCAI_SECRET_KEY = [Convert]::ToBase64String($bytes)
python -m backend.app
```

O cookie é HTTP-only e `SameSite=Lax`, com duração de oito horas. Para uso local via HTTP, `TROCAI_COOKIE_SECURE` deve permanecer desativada. Essa sessão atende ao protótipo e não substitui uma solução de autenticação revisada para produção.