# Desenvolvimento de Data-Driven Apps com Python
## Assessment (AT)
## Instituto Infnet - Rafael Dottori de Oliveira

## Descrição
Projeto para visualizar e analisar dados sobre futebol obtidos do StatsBomb.
Temos funcionalidades com integração a LLMs que podem ser requisitados via API.
Além disso, todas essas funcionalidades e visualizações estão incluídas em um aplicativo via Streamlit.

## Instalação e Uso
1 - Criar um novo ambiente virtual: "python -m venv .venv_app"

2 - Ativar o ambiente: ".venv_app/Scripts/activate"

3 - Instalar as dependências: "python -m pip install -r requirements.txt"

4 - Rodar a API com: uvicorn src.main:app

5 - Rodar o aplicativo do Streamlit com: streamlit run src/app.py

6 - Para utilizar o LLM Gemini, criar um arquivo ".env" na raiz do projeto contendo a chave da API: "GEMINI_KEY=chave"


## Exemplos de Requisição

Após rodar a API:

http POST localhost:8000/player_profile id_partida=12345 nome_jogador="Fulano"

http POST localhost:8000/commentary id_partida=42 tom_narracao="Formal"