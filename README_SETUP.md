# Setup do Ambiente - ChatLLM Lab

Este documento descreve como configurar o ambiente de desenvolvimento do ChatLLM Lab.

## Stack Base

1. Backend: FastAPI (Python).
2. Frontend: React com JSX compilado em runtime (Babel no navegador, sem build complexo).
3. Persistencia: SQLite.

## Setup Inicial

1. Clone seu fork e entre no diretorio do projeto.
2. Instale as dependencias, configure o ambiente virtual `.venv` e extraia o `.env`:

Linux/Mac:

```bash
bash ./setup.sh
```

Windows:

```bat
setup.bat
```
ou

``` PowerShell
.\setup.bat
```

3. O arquivo `.env` e extraido pelo script de setup a partir de um arquivo protegido por senha incluido no repositorio. Quando o script pedir, **digite a senha fornecida pelo professor**:
   - Os caracteres nao aparecem enquanto voce digita; isso e normal.
   - Se a senha estiver errada, o setup para com erro. Confirme a senha com o professor e execute o setup novamente.
   - A extracao usa ferramentas do proprio sistema: `unzip` no Linux/Mac (se faltar: `sudo apt install unzip`) e `tar.exe` no Windows 10 (versao 1803+) ou 11.
   - Se o `.env` ja existir na raiz do projeto, a extracao e ignorada.
   - O `.env` extraido contem `OPENROUTER_API_KEY` e `OPENROUTER_MODEL`. Nunca faca commit dele (ja esta no `.gitignore`).

4. Inicie a aplicacao com o script correspondente ao seu sistema:

   Linux/Mac:

   ```bash
   bash ./setup.sh run
   ```

   Windows:

   ```bat
   setup.bat run
   ```
   ou
   ``` PowerShell
   .\setup.bat run   
   ```


   Como alternativa no VS Code, abra **Executar e Depurar**, selecione
   **ChatLLM API (uvicorn)** e pressione `F5`. As duas formas monitoram alteracoes
   no backend e nos arquivos HTML, JavaScript, JSX e CSS do frontend.

6. Abra `http://127.0.0.1:8000` no navegador para usar o chat. Quando um arquivo
   do frontend mudar, o servidor sera reiniciado; atualize a pagina do navegador
   para ver a alteracao.

## Endpoints da API

1. `GET /health` retorna status da API.
2. `POST /api/chat` envia mensagem para o modelo e retorna resposta.
3. `POST /api/chat/stream` envia mensagem e retorna a resposta em streaming (SSE), com renderizacao progressiva no chat.
4. `GET /api/instructions` retorna as instrucoes personalizadas (system prompt) do usuario logado.
5. `PUT /api/instructions` salva as instrucoes do usuario logado (`{"content": "..."}`, ate 4000 caracteres; vazio restaura o padrao).
6. `DELETE /api/instructions` restaura o prompt padrao do usuario logado.

Todos os endpoints `/api/chat*`, `/api/sessions*` e `/api/instructions` exigem o header `Authorization: Bearer <token>`.

## Instrucoes personalizadas

Cada usuario pode editar o system prompt enviado ao modelo pelo botao **Instrucoes** no topo do chat.

1. As instrucoes ficam na tabela `user_instructions` do SQLite, uma linha por usuario.
2. Quem nunca editou (ou restaurou o padrao) nao tem linha na tabela e recebe o prompt padrao (`DEFAULT_SYSTEM_PROMPT` em `backend/services/openrouter.py`).
3. `/api/chat` e `/api/chat/stream` usam as instrucoes do usuario do token. A geracao automatica de titulo continua usando o prompt padrao.
4. Os endpoints nao recebem id de usuario: o usuario vem sempre do token, entao ninguem le ou altera as instrucoes de outra pessoa.

Exemplo de request:

```json
{
  "message": "Explique o que e um LLM em uma frase.",
  "history": [
    { "role": "user", "content": "Oi" },
    { "role": "assistant", "content": "Oi!" }
  ]
}
```
