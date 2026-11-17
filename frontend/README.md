TROC.AI - Tinder do Conhecimento
Aplicação web para buscar perfis, compartilhar habilidades e criar conexões com interesse mútuo. O front-end React/Vite se comunica com uma API HTTP em Python, que utiliza o banco SQLite em `Bd_Troc.AI`.

## Executar localmente

Requisitos: Python 3.8+ e Node.js. Prepare e ative o ambiente Python conforme [`backend/README.md`](../backend/README.md).

Em um terminal, na raiz do repositório e com o ambiente Python ativo, inicie o backend:

```bash
python -m backend.app
```

Na primeira execução, o banco trocai.db e os perfis de demonstração são criados automaticamente. O servidor fica em http://127.0.0.1:3001.

Em outro terminal, inicie o front-end:

```bash
cd frontend
npm install
npm run dev
```

Abra o endereço exibido pelo Vite (por padrão http://localhost:5173). O Vite encaminha as chamadas /api ao backend.

Faça login para ver as sugestões e matches. Para testar, use um perfil de demonstração:

- E-mail: `lucas.andrade@troc.ai`
- Senha: `senha123`

Os demais perfis de demonstração também usam a senha senha123. Para testar um match, entre em duas sessões/perfis distintos e ambos devem se conectar.

## Validar

O build do front-end pode ser validado com:

```bash
cd frontend
npm run build
```

Para executar os testes do backend no PowerShell, na raiz do repositório:

```powershell
$env:PYTHONPATH = "Bd_Troc.AI"
.\.venv\Scripts\python.exe -m unittest discover -s backend/tests -v
```
