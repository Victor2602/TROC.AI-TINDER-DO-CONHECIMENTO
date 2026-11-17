# TROC.AI — Contrato da API REST

Este documento descreve os endpoints atualmente implementados no back-end Flask e os formatos que o front-end deve consumir. Ele reflete o código em `backend/app.py`, `backend/services.py` e as regras de domínio existentes em `Bd - Troc.AI/banco.py`.

## 1. Visão geral

- **Back-end:** Python + Flask.
- **Banco de dados:** SQLite.
- **Formato de troca:** JSON (`Content-Type: application/json` nos `POST`).
- **URL local da API:** `http://127.0.0.1:3001`.
- **URL usada pelo React durante o desenvolvimento:** caminhos relativos começando com `/api`; o Vite encaminha essas chamadas para `http://localhost:3001` por meio do proxy definido em `frontend/vite.config.js`.

A raiz `/` não possui endpoint próprio e responde `404` em JSON. Rotas inexistentes e métodos não permitidos também retornam JSON no mesmo formato de erro. Para verificar o servidor, use `GET /api/health`.

## 2. Conceitos do domínio

O sistema não cadastra uma oferta ou demanda como um registro independente. Cada usuário possui uma lista de habilidades oferecidas e outra de habilidades desejadas:

| Código | Significado | Campo da API |
|---|---|---|
| `OUT` | O usuário sabe ensinar/oferecer | `skills_out` |
| `IN` | O usuário quer aprender | `skills_in` |

As habilidades devem ser escolhidas no catálogo retornado por `GET /api/opcoes`.

**Regra para participar do matching:** um perfil é considerado ativo quando possui pelo menos 3 habilidades `OUT` e 1 habilidade `IN`. O cadastro aceita listas menores, mas perfis que não atingirem esse mínimo não aparecem nas sugestões e não podem participar de interações.

Uma mesma habilidade não pode constar simultaneamente em `skills_out` e `skills_in` para o mesmo usuário.

## 3. Endpoints

### 3.1. Verificar a API

`GET /api/health`

Resposta `200 OK`:

```json
{
  "status": "ok",
  "servico": "trocai-api"
}
```

### 3.2. Consultar opções para formulários

`GET /api/opcoes`

Retorna o catálogo de habilidades e categorias existente no banco, os níveis aceitos e os tipos de habilidade.

Resposta `200 OK` (exemplo resumido):

```json
{
  "categorias": ["Design", "Programação", "Web"],
  "habilidades": [
    { "id": 1, "nome": "Python", "categoria": "Programação" },
    { "id": 4, "nome": "SQL", "categoria": "Programação" }
  ],
  "niveis_tecnologia": ["Básico", "Intermediário", "Avançado"],
  "tipos_habilidade": [
    { "codigo": "OUT", "descricao": "Ofereço / sei ensinar" },
    { "codigo": "IN", "descricao": "Quero aprender" }
  ]
}
```

`habilidades` contém objetos com `id`, `nome` e `categoria`. `categorias` contém nomes de categorias.

### 3.3. Cadastrar usuário

`POST /api/usuarios`

Cabeçalho:

```http
Content-Type: application/json
```

Corpo — campos obrigatórios:

| Campo | Tipo | Regra |
|---|---|---|
| `nome` | string | Não pode ser vazio. |
| `email` | string | Obrigatório e único. |
| `senha` | string | Mínimo de 6 caracteres. |

Campos opcionais:

| Campo | Tipo | Observação |
|---|---|---|
| `curso` | string | Curso/formação do usuário. |
| `instituicao` | string | Instituição de ensino. |
| `bio` | string | Texto de apresentação. |
| `foto_url` | string | URL da foto, se houver. |
| `cidade` | string | Cidade do usuário. |
| `zona` | string | Região/zona da cidade. |
| `nivel_tecnologia` | string | `Básico`, `Intermediário` ou `Avançado`. |
| `skills_out` | array de strings | Nomes das habilidades oferecidas; padrão `[]`. |
| `skills_in` | array de strings | Nomes das habilidades desejadas; padrão `[]`. |

Exemplo de requisição:

```json
{
  "nome": "Ana Souza",
  "email": "ana@example.com",
  "senha": "senha123",
  "curso": "Análise e Desenvolvimento de Sistemas",
  "instituicao": "Senac",
  "bio": "Gosto de programação e tecnologia.",
  "cidade": "São Paulo",
  "zona": "Zona Sul",
  "nivel_tecnologia": "Intermediário",
  "skills_out": ["Python", "SQL", "Git"],
  "skills_in": ["Inglês"]
}
```

Os itens de `skills_out` e `skills_in` são **nomes** do catálogo, não IDs. O front-end deve carregar o catálogo por `GET /api/opcoes` e enviar os nomes selecionados.

Resposta `201 Created`:

```json
{
  "mensagem": "Usuário cadastrado com sucesso.",
  "usuario_id": 1050
}
```

O identificador é gerado pelo banco e o valor acima é apenas ilustrativo. O cadastro não inicia uma sessão automaticamente; depois do cadastro, o cliente deve chamar `POST /api/login` para autenticar o usuário.

Validações e limites de entrada:

- `nome`: texto obrigatório, até 100 caracteres; espaços nas extremidades são removidos.
- `email`: texto obrigatório, até 254 caracteres, com formato básico `nome@dominio.extensao` (sem espaços e com domínio e extensão); é normalizado para minúsculas. E-mails duplicados são rejeitados.
- `senha`: texto obrigatório, entre 6 e 128 caracteres no cadastro. Espaços fazem parte da senha e não são removidos. A senha é armazenada como hash; a API não devolve a senha.
- `curso`: até 120 caracteres; `instituicao`: até 160; `bio`: até 1.000; `foto_url`: até 2.048 e deve ser uma URL absoluta `http` ou `https`; `cidade`: até 120; `zona`: até 120.
- `nivel_tecnologia`: somente `Básico`, `Intermediário` ou `Avançado`.
- `skills_out` e `skills_in`: listas de textos. Cada nome pode ter até 80 caracteres e deve existir no catálogo retornado por `GET /api/opcoes`.
- Habilidades repetidas na mesma lista são removidas sem diferenciar maiúsculas/minúsculas. Uma mesma habilidade não pode estar nas duas listas; essa combinação retorna `400 Bad Request`.
- Campos JSON não documentados são rejeitados com `400 Bad Request`, para detectar erros de nomenclatura no cliente.
- O cadastro não exige que o perfil já esteja ativo; entretanto, para entrar no feed, deve haver pelo menos 3 itens em `skills_out` e 1 em `skills_in`.

### 3.4. Fazer login

`POST /api/login`

Corpo:

```json
{
  "email": "lucas.andrade@troc.ai",
  "senha": "senha123"
}
```

Resposta `200 OK`:

```json
{
  "usuario_id": 1045,
  "mensagem": "Autenticação realizada."
}
```

Além do corpo JSON, a resposta define um cookie de sessão HTTP-only. O navegador o envia automaticamente nas próximas chamadas à API feitas pela mesma origem (no desenvolvimento, o React usa o proxy do Vite). O identificador do usuário passa a ser obtido dessa sessão, não de um `usuario_id` enviado pelo cliente.

O e-mail deve respeitar o formato básico informado na seção de cadastro e a senha deve ser texto com até 128 caracteres. Credenciais sintaticamente válidas, mas não correspondentes a uma conta, retornam `401 Unauthorized`:

```json
{
  "erro": "E-mail ou senha inválidos."
}
```

### 3.5. Consultar a sessão atual

`GET /api/sessao`

Requer login. Retorna a identidade associada ao cookie de sessão:

```json
{
  "autenticado": true,
  "usuario": {
    "id": 1045,
    "nome": "Lucas Andrade"
  }
}
```

Sem uma sessão válida, retorna `401 Unauthorized`.

### 3.6. Encerrar a sessão

`POST /api/logout`

Encerra a sessão do navegador. Não exige corpo JSON e pode ser chamado mesmo quando não há sessão ativa.

Resposta `200 OK`:

```json
{
  "mensagem": "Sessão encerrada."
}
```

### 3.7. Consultar perfil

`GET /api/usuarios/{usuario_id}`

Exemplo:

`GET /api/usuarios/1045`

Resposta `200 OK` (exemplo resumido):

```json
{
  "id": 1045,
  "nome": "Lucas Andrade",
  "curso": "Análise e Desenvolvimento de Sistemas",
  "instituicao": "Senac",
  "bio": "Estagiário de TI...",
  "foto_url": null,
  "cidade": "São Paulo",
  "zona": "Zona Leste",
  "nivel_tecnologia": "Avançado",
  "criado_em": "2026-11-14 16:10:46",
  "skills_out": ["Python", "HTML/Web"],
  "skills_in": ["Figma", "UI Design"],
  "perfil_ativo": true,
  "reputacao": {
    "nota_media": null,
    "total_avaliacoes": 0,
    "trocas_concluidas": 0
  },
  "selos": []
}
```

A resposta pública não inclui e-mail, hash de senha ou coordenadas geográficas. Os arrays de habilidades mostrados são apenas ilustrativos.

Se o usuário não existir, a API retorna `404 Not Found`. Se o identificador no caminho não for um inteiro positivo, retorna `400 Bad Request`.

### 3.8. Buscar sugestões de perfis

`GET /api/sugestoes?limite={quantidade}`

Requer sessão autenticada. O usuário de referência é obtido do cookie de sessão; não envie `usuario_id`.

Parâmetros:

| Parâmetro | Obrigatório | Padrão | Regra |
|---|---|---|---|
| `limite` | Não | `10` | Inteiro entre 1 e 50. |

Exemplo:

`GET /api/sugestoes?limite=10`

Resposta `200 OK`: array de perfis públicos. Cada objeto contém os campos do perfil descritos na seção anterior e o campo adicional `indice_afinidade` (número de 0 a 100).

Exemplo resumido:

```json
[
  {
    "id": 1046,
    "nome": "Marina Costa",
    "curso": "Design Gráfico",
    "cidade": "São Paulo",
    "zona": "Zona Sul",
    "skills_out": ["Design Gráfico", "Figma", "UI Design"],
    "skills_in": ["Python", "HTML/Web"],
    "perfil_ativo": true,
    "reputacao": {
      "nota_media": null,
      "total_avaliacoes": 0,
      "trocas_concluidas": 0
    },
    "selos": [],
    "indice_afinidade": 98.0
  }
]
```

As sugestões são ordenadas da maior para a menor afinidade. O próprio usuário autenticado e perfis com os quais já houve interação são excluídos do feed. Se a sessão não existir ou tiver expirado, a API retorna `401 Unauthorized`. Se o usuário autenticado não tiver perfil ativo, retorna `400 Bad Request` com a mensagem de regra de negócio correspondente.

### 3.9. Registrar interesse ou descarte

`POST /api/interacoes`

Requer sessão autenticada.

Cabeçalho:

```http
Content-Type: application/json
```

Corpo:

| Campo | Tipo | Descrição |
|---|---|---|
| `para_usuario_id` | inteiro positivo | Usuário que recebe a ação; não aceita string, decimal ou booleano. |
| `acao` | string | `CONECTAR` ou `DESCARTAR` (a comparação não diferencia maiúsculas/minúsculas). |

O autor da interação (`de_usuario_id`) é obtido da sessão autenticada e não deve ser enviado pelo cliente. Campos extras, inclusive `de_usuario_id`, são rejeitados.

Exemplo — usuário 1045 autenticado:

```json
{
  "para_usuario_id": 1046,
  "acao": "CONECTAR"
}
```

Quando ainda não há interesse recíproco, a API retorna `200 OK`:

```json
{
  "match": false,
  "match_id": null,
  "indice_afinidade": null
}
```

Quando os dois usuários registram `CONECTAR` um para o outro, é criado o match e a API retorna `201 Created`:

```json
{
  "match": true,
  "match_id": 1,
  "indice_afinidade": 98.0
}
```

Os IDs e a afinidade do exemplo podem variar.

Regras:

- `DESCARTAR` não cria match.
- Um match só é criado quando há `CONECTAR` dos dois lados.
- Os dois usuários precisam existir; caso contrário, retorna `404 Not Found`.
- Os dois perfis precisam estar ativos.
- Um usuário não pode interagir consigo mesmo.
- O banco permite apenas uma interação por par ordenado de usuários; tentar registrar outra interação para o mesmo par retorna conflito `409`.

### 3.10. Listar matches

`GET /api/matches`

Requer sessão autenticada. A API retorna somente os matches do usuário associado ao cookie de sessão; não envie `usuario_id`.

Resposta `200 OK`: array. Cada item contém:

- `match_id`: identificador do match;
- `indice_afinidade`: índice de afinidade registrado quando o match foi criado. O nome é o mesmo utilizado nos endpoints de sugestões e interações;
- `criado_em`: data/hora de criação;
- `outro_usuario`: perfil público do outro participante.

Exemplo resumido:

```json
[
  {
    "match_id": 1,
    "indice_afinidade": 98.0,
    "criado_em": "2026-11-14 16:10:46",
    "outro_usuario": {
      "id": 1046,
      "nome": "Marina Costa",
      "skills_out": ["Design Gráfico", "Figma", "UI Design"],
      "skills_in": ["Python", "HTML/Web"],
      "perfil_ativo": true,
      "reputacao": {
        "nota_media": null,
        "total_avaliacoes": 0,
        "trocas_concluidas": 0
      },
      "selos": []
    }
  }
]
```

Se o usuário autenticado ainda não tiver matches, retorna `200 OK` com `[]`. Se não houver sessão válida, retorna `401 Unauthorized`.

## 4. Códigos HTTP e formato de erro

Todos os erros HTTP gerados pela API, inclusive rotas inexistentes e métodos não permitidos, seguem o mesmo envelope JSON:

```json
{
  "erro": "Descrição do problema."
}
```

| Status | Quando ocorre |
|---|---|
| `200 OK` | Consulta ou operação concluída sem criação de match. |
| `201 Created` | Usuário cadastrado ou match criado. |
| `400 Bad Request` | JSON malformado, objeto JSON com estrutura inválida, campo obrigatório ausente, campo desconhecido, tipo/formato inválido ou regra de negócio violada. |
| `401 Unauthorized` | Credenciais inválidas no login ou ausência/expiração da sessão em endpoint protegido. |
| `404 Not Found` | Usuário/recurso consultado não existe ou a rota não foi encontrada. |
| `405 Method Not Allowed` | O método HTTP não é permitido para a rota. |
| `409 Conflict` | Conflito com dados existentes ou violação de restrição de integridade do banco, como e-mail ou interação duplicada. |
| `413 Payload Too Large` | O corpo da requisição ultrapassa o limite de 64 KiB. |
| `415 Unsupported Media Type` | Um endpoint que recebe JSON foi chamado sem `Content-Type: application/json` (ou tipo `application/*+json`). |
| `500 Internal Server Error` | Falha inesperada no servidor. A resposta não expõe detalhes internos; a causa é registrada no log do Flask. |

### 4.1. Regras gerais de validação HTTP

- Os endpoints `POST` que recebem corpo exigem um objeto JSON, não um array, string ou valor primitivo.
- JSON malformado retorna `400`; tipo de conteúdo não JSON retorna `415`.
- O limite máximo do corpo de uma requisição é 64 KiB; acima disso, a API retorna `413`.
- O identificador de perfil em `/api/usuarios/{usuario_id}` deve conter apenas dígitos e representar inteiro positivo no intervalo do SQLite (`1` a `9.223.372.036.854.775.807`). O identificador do destinatário em `/api/interacoes` deve ser número inteiro JSON, não string, decimal ou booleano. O parâmetro `limite` de sugestões deve ser inteiro entre 1 e 50.
- `GET /api/sugestoes` e `GET /api/matches` exigem sessão autenticada e não aceitam `usuario_id` como parâmetro. `POST /api/interacoes` exige sessão e não aceita `de_usuario_id` no corpo.
- Erros de validação retornam o envelope `{"erro": "..."}`.

## 5. Regras de afinidade

O índice de afinidade combina complementaridade de habilidades e proximidade geográfica:

```text
afinidade = 0,9 × compatibilidade_de_skills + 0,1 × proximidade
```

A compatibilidade de skills é a média da cobertura das demandas dos dois usuários pelas habilidades que o outro oferece. A proximidade vale:

- `100`: mesma cidade e mesma zona;
- `80`: mesma cidade, mas zonas diferentes ou não informadas;
- `50`: cidades diferentes ou cidade não informada.

O índice final é retornado no campo `indice_afinidade` nas sugestões, no resultado de uma interação que cria match e na listagem de matches.

## 6. Dados de demonstração

Em um banco recém-criado, a configuração padrão insere cinco usuários demonstrativos. A senha de todos é `senha123`.

| ID | Nome | E-mail |
|---:|---|---|
| 1045 | Lucas Andrade | `lucas.andrade@troc.ai` |
| 1046 | Marina Costa | `marina.costa@troc.ai` |
| 1047 | Maria Oliveira | `maria.oliveira@troc.ai` |
| 1048 | Beatriz Ferreira | `beatriz.ferreira@troc.ai` |
| 1049 | Pedro Henrique | `pedro.henrique@troc.ai` |

Essas credenciais são exclusivamente para desenvolvimento e demonstração.

## 7. Integração com o front-end React

Durante o desenvolvimento, o React deve chamar caminhos relativos, por exemplo:

```javascript
const response = await fetch("/api/opcoes", {
  credentials: "same-origin"
});
```

O proxy do Vite encaminha `/api` para o Flask. Assim, o código React não precisa fixar `http://127.0.0.1:3001` em cada chamada. O navegador envia automaticamente o cookie de sessão para chamadas da mesma origem; `credentials: "same-origin"` deixa essa intenção explícita.

### Integração atual do front-end

O front-end consome o contrato atual, que associa `OUT` e `IN` diretamente aos usuários:

| Arquivo | Integração |
|---|---|
| `src/api.js` | Usa `/api/opcoes`, `/api/usuarios`, `/api/login`, `/api/sessao`, `/api/sugestoes`, `/api/interacoes`, `/api/logout` e `/api/matches`. A busca por texto e tipo filtra localmente as sugestões retornadas. |
| `pages/Cadastro.jsx` | Cria o usuário com `skills_out[]` e `skills_in[]` e, em seguida, chama `POST /api/login` para iniciar a sessão. |
| `pages/Busca.jsx` | Exibe sugestões para o usuário autenticado; as ações de conectar chamam `POST /api/interacoes`. |
| `pages/Match.jsx` | Exibe `match_id`, `indice_afinidade` e `outro_usuario` de `GET /api/matches`. Todo registro retornado já representa interesse mútuo. |

Após o login, o front-end não deve manter nem enviar `usuario_id` como prova de identidade. O navegador conserva o cookie HTTP-only e o envia nas chamadas protegidas. Para recuperar o usuário após atualizar a página, o React deve consultar `GET /api/sessao`. Ao sair, deve chamar `POST /api/logout`. O cookie é HTTP-only e não deve ser lido diretamente por JavaScript.

## 8. Funcionalidades do banco ainda não expostas pela API

O banco de dados já contém operações para mensagens de chat, definição de trocas, agendamento/conclusão de sessões, avaliações, notificações e reputação. **Essas operações ainda não possuem endpoints HTTP nesta versão da API.** Não devem ser consumidas diretamente pelo React até que seus respectivos endpoints sejam implementados.

## 9. Limites e decisões do protótipo

- A API utiliza sessão Flask assinada em cookie (o conteúdo é assinado, não criptografado), adequada ao protótipo local. A chave padrão serve somente para desenvolvimento; configure `TROCAI_SECRET_KEY` com um valor aleatório forte fora do ambiente local.
- O cookie é HTTP-only, `SameSite=Lax` e tem duração de oito horas. `Secure` permanece desativado por padrão para permitir HTTP em localhost; habilite `TROCAI_COOKIE_SECURE=1` somente quando a aplicação estiver sob HTTPS.
- A sessão identifica o usuário para sugestões, interações e listagem de matches. O perfil individual continua público nesta versão; o endpoint não retorna e-mail, hash de senha ou coordenadas.
- Esse mecanismo não inclui proteção CSRF dedicada, recuperação de senha, controle de papéis ou gestão de sessões no servidor. Portanto, é uma autenticação básica para o protótipo e não deve ser tratada como configuração pronta para produção.
- Não há endpoint de atualização de perfil/habilidades nesta versão; `POST /api/usuarios` cria o perfil.
- Não há endpoint HTTP de busca por texto/categoria; `GET /api/sugestoes` retorna o feed de compatibilidade.
- O cálculo de matching e a persistência são delegados às funções existentes em `banco.py`; o React não deve reproduzir essas regras.