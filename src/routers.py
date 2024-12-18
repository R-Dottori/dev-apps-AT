
from fastapi import APIRouter, HTTPException
from .models import ModeloPartida, ModeloJogador, ModeloResumo, ModeloEstatistica, ModeloNarracao, ModeloAgentePergunta, ModeloAgenteResposta
import pandas as pd
from statsbombpy import sb
import numpy as np
import google.generativeai as genai
import os
import json
from langchain.prompts import PromptTemplate
from langchain.agents import create_react_agent, AgentExecutor
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.agents import Tool

router = APIRouter()    


@router.get('/partidas/{id_partida}')
async def get_partida(id_partida: int):
    try:
        partida = sb.events(id_partida)
    except:
        raise HTTPException(status_code=404, detail='Erro! Partida não encontrada.')
    try:
        partida = partida.to_dict(orient='records')
        for evento in partida:
            for chave, valor in evento.items():
                if valor is np.nan:
                    valor = None
                evento[chave] = valor
        partida = json.dumps(partida)
        return partida
    except:
        raise HTTPException(status_code=500, detail='Erro! Não foi possível exibir a partida.')


@router.post('/match_summary', response_model=ModeloResumo)
async def resumir_partida(body: ModeloPartida):
    try:
        partida_bruto = sb.events(body.id_partida)
    except:
        raise HTTPException(status_code=404, detail='Erro! Partida não encontrada.')

    partida_bruto = partida_bruto.sort_values(by='minute').to_dict(orient='records')
    partida = []
    
    for evento_bruto in partida_bruto:
        evento = {}
        for chave, valor in evento_bruto.items():
                if valor is not np.nan:
                    evento[chave] = valor
        partida.append(evento)

    eventos = []
    for evento in partida:
        if evento['type'] == 'Shot' or evento['type'] == 'Pass' or evento['type'] == 'Foul Committed':
            eventos.append(evento)
    
    api_key = os.getenv('GEMINI_KEY')
    genai.configure(api_key=api_key)
    modelo = genai.GenerativeModel('gemini-1.5-flash')
    
    instrucoes = f"""
    Você é um especialista em futebol.

    Baseado nos principais eventos da partida abaixo, resuma o jogo de maneira curta e clara.

    Indique sempre o número de gols tanto do tempo regulamentar quanto de prorrogações e pênaltis.
    
    Tente destacar quem fez mais gols pelo time vencedor, principalmente se marcou 2 ou mais.

    Por exemplo:
    "O time A venceu do time B por 5x2 nos pênaltis. A partida apresentou 2 cartões vermelhos."
    "Com 2 gols de Carol, o time C vence a partida por 2x0. Assistências de Ana e Bianca."
    "Uma partida muito feia, terminando empatada e com um número altíssimo de faltas."

    {eventos}
    """
    try:
        resposta = modelo.generate_content(instrucoes).text
        return ModeloResumo(id_partida=body.id_partida, resumo=resposta)
    except:
        raise HTTPException(status_code=500, detail='Erro! Não foi possível gerar o resumo.')


@router.post('/player_profile', response_model=ModeloEstatistica)
async def estatisticas_jogador(body: ModeloJogador):
    try:
        partida = sb.events(body.id_partida)
    except:
        raise HTTPException(status_code=404, detail='Erro! Partida não encontrada.')

    jogadores = partida['player'].dropna().unique().tolist()
    
    if sum(body.nome_jogador in jogador for jogador in jogadores) == 0:
        raise HTTPException(status_code=400, detail='Erro! Não encontramos nenhum jogador com esse nome.')
    elif sum(body.nome_jogador in jogador for jogador in jogadores) > 1:
        raise HTTPException(status_code=400, detail='Erro! O nome inserido pode ser interpretado para mais de 1 jogador.')
    else:
        jogadores_iniciais = [jogador['player']['name'] for jogador in partida[partida['type'] == 'Starting XI']['tactics'][0]['lineup']] \
                            + [jogador['player']['name'] for jogador in partida[partida['type'] == 'Starting XI']['tactics'][1]['lineup']]
        eventos_jogador = partida[partida['player'].str.contains(body.nome_jogador, na=False)]
        estatisticas = {}

        estatisticas['jogador'] = [jogador for jogador in jogadores if body.nome_jogador in jogador][0]
        estatisticas['passes'] = eventos_jogador[eventos_jogador['type'] == 'Pass'].shape[0]
        estatisticas['finalizacoes'] = eventos_jogador[eventos_jogador['type'] == 'Shot'].shape[0]
        estatisticas['desarmes'] = eventos_jogador[eventos_jogador['type'] == 'Dispossessed'].shape[0]

        if estatisticas['jogador'] in jogadores_iniciais:
            if eventos_jogador[eventos_jogador['type'] == 'Substitution'].shape[0] > 0:
                estatisticas['minutos_jogados'] = int(eventos_jogador[eventos_jogador['type'] == 'Substitution']['minute'].iloc[0])
            else:
                estatisticas['minutos_jogados'] = int(eventos_jogador['minute'].max())
        else:
            estatisticas['minutos_jogados'] = int(eventos_jogador['minute'].max() \
                                                  - partida[
                                                                    (partida['type'] == 'Substitution')
                                                                    & (partida['substitution_replacement'] == estatisticas['jogador'])
                                                                    ]['minute'].iloc[0]
                                                 )

        return ModeloEstatistica(id_partida=body.id_partida, estatisticas=estatisticas)


@router.post('/commentary', response_model=ModeloResumo)
async def narrar_partida(body:ModeloNarracao):
    estilo = body.tom_narracao.lower().strip()

    if estilo != 'formal' and estilo != 'humorístico' and estilo != 'técnico':
        raise HTTPException(status_code=400, detail='Erro! Escolha entre os estilos "Formal", "Humorístico" ou "Técnico".')
        
    else:
        # Obter a partida do StatsBomb
        try:
            partida_bruto = sb.events(body.id_partida)
        except:
            raise HTTPException(status_code=404, detail='Erro! Partida não encontrada.')
        partida_bruto = partida_bruto.sort_values(by='minute').to_dict(orient='records')
        partida = []
        
        # Limpar as células vazias
        for evento_bruto in partida_bruto:
            evento = {}
            for chave, valor in evento_bruto.items():
                    if valor is not np.nan:
                        evento[chave] = valor
            partida.append(evento)

        # Separar os eventos relevantes (chutes, passes e faltas)
        eventos = []
        for evento in partida:
            if evento['type'] == 'Shot' or evento['type'] == 'Pass' or evento['type'] == 'Foul Committed':
                eventos.append(evento)
        
        # Gerar o modelo com o LLM
        api_key = os.getenv('GEMINI_KEY')
        genai.configure(api_key=api_key)
        modelo = genai.GenerativeModel('gemini-1.5-flash')
        
        instrucoes = f"""
        Você é um especialista em futebol.

        Baseado nas estatísticas da partida abaixo, crie uma narração para a partida inteira.
        Não esqueça de indicar o resultado.

        Narre de acordo com o tom exigido pelo usuário:
        - Formal: Narração técnica e objetiva.
        - Humorístico: Narração descontraída e criativa.
        - Técnico: Narração detalhada dos eventos.

        • Tipo de Narração:
        {estilo}

        • Eventos da Partida:
        {eventos}
        """
        try:
            resposta = modelo.generate_content(instrucoes).text
            return ModeloResumo(id_partida=body.id_partida, resumo=resposta)
        except:
            raise HTTPException(status_code=500, detail='Erro! Não foi possível gerar a narração.')



def tipos_react(action_input):
    id_partida = json.loads(action_input)["id_partida"]
    partida = sb.events(id_partida)
    tipos = partida['type'].unique()
    return tipos


def eventos_react(action_input):
    id_partida = json.loads(action_input)["id_partida"]
    try:
        tipo = json.loads(action_input)["tipo"]
    except:
        tipo = ''
    partida_bruto = sb.events(id_partida)
    partida_bruto = partida_bruto.sort_values(by='minute').to_dict(orient='records')
    partida = []
    for evento_bruto in partida_bruto:
        evento = {}
        for chave, valor in evento_bruto.items():
                if valor is not np.nan:
                    evento[chave] = valor
        partida.append(evento)
    eventos = []
    for evento in partida:
        if tipo:
            if evento['type'] == tipo:
                eventos.append(evento)
        else:
            if evento['type'] == 'Shot' or evento['type'] == 'Pass' or evento['type'] == 'Foul Committed':
                eventos.append(evento)
    return json.dumps(eventos)


def jogador_react(action_input):
    id_partida = json.loads(action_input)["id_partida"]
    nome_jogador = json.loads(action_input)["nome_jogador"]
    partida = sb.events(id_partida)

    jogadores = partida['player'].dropna().unique().tolist()
    
    jogadores_iniciais = [jogador['player']['name'] for jogador in partida[partida['type'] == 'Starting XI']['tactics'][0]['lineup']] \
                            + [jogador['player']['name'] for jogador in partida[partida['type'] == 'Starting XI']['tactics'][1]['lineup']]
    eventos_jogador = partida[partida['player'].str.contains(nome_jogador, na=False)]
    estatisticas = {}

    estatisticas['jogador'] = [jogador for jogador in jogadores if nome_jogador in jogador][0]
    estatisticas['passes'] = eventos_jogador[eventos_jogador['type'] == 'Pass'].shape[0]
    estatisticas['finalizacoes'] = eventos_jogador[eventos_jogador['type'] == 'Shot'].shape[0]
    estatisticas['desarmes'] = eventos_jogador[eventos_jogador['type'] == 'Dispossessed'].shape[0]

    if estatisticas['jogador'] in jogadores_iniciais:
        if eventos_jogador[eventos_jogador['type'] == 'Substitution'].shape[0] > 0:
            estatisticas['minutos_jogados'] = int(eventos_jogador[eventos_jogador['type'] == 'Substitution']['minute'].iloc[0])
        else:
            estatisticas['minutos_jogados'] = int(eventos_jogador['minute'].max())
    else:
        estatisticas['minutos_jogados'] = int(eventos_jogador['minute'].max() \
                                                - partida[
                                                                (partida['type'] == 'Substitution')
                                                                & (partida['substitution_replacement'] == estatisticas['jogador'])
                                                                ]['minute'].iloc[0]
                                                )

    return json.dumps(estatisticas)


def carregar_agente() -> AgentExecutor:
    instrucoes = """
    Você é um especialista em futebol.
    Você coletará informações e criará análises de uma partida específica.
    Você TEM ACESSO as seguintes ferramentas.

    • Nomes das Ferramentas:
    {tool_names}

    • Descrições das Ferramentas:
    {tools}

    • Instruções de Uso:
    1 - Você utilizará a ferramenta "tipos_react" para analisar quais os tipos possíveis de eventos em uma partida de futebol.
    A partida é identificada pelo seu número: {id_partida}.

    Exemplo:
    Thought: Preciso obter quais tipos de evento estão presentes na partida de id 12345.
    Action: Tipos de Evento
    Action Input: {{"id_partida": 12345}}
    Observation: Os tipos de evento da partida, incluindo "Shot", "Pass" e "Foul Committed".

    

    2 - Com os tipos possíveis, você achará qual tipo de evento corresponde a pergunta do usuário.
    Então, utilizará a ferramenta "eventos_react" para filtrar os eventos da partida.
    Caso o tipo solicitado esteja implícito (como gols dentro de "Shot"), tente realizar o processo com o tipo base.
    Caso MESMO ASSIM não se encaixe em nenhum tipo disponível, encerre o processo e informe ao usuário.

    Exemplo 1:
    Thought: Procurarei todos os passes presentes na partida 12345.
    Action: Obter Eventos
    Action Input: {{"id_partida": 12345, "tipo": "Pass"}}
    Observation: Todos os passes de uma partida.

    Exemplo 2:
    Thought: Quero todos os eventos da partida 12345, independente do tipo.
    Action: Obter Eventos
    Action Input: {{"id_partida": 12345}}
    Observation: Todos os eventos da partida.



    3 - Caso o usuário pergunte de jogador específico, você pode obter as estatísticas do mesmo usando
    a ferramenta "jogador_react". Pode ser usada várias vezes para comparar jogadores diferentes.

    Exemplo:
    Thought: Preciso saber quem realizou mais passes entre Ana e Carol na partida 12345.
    Action: Estatísticas de um Jogador
    Action Input: {{"id_partida": 12345, "nome_jogador": "Ana"}}
    Observation: Estatísticas da jogadora Ana.

    

    • Resposta Final:
    Com os dados filtrados obtidos, basta contá-los sem nenhuma ferramenta ou código extra para responder a pergunta original.
    Encerre o processo nessa etapa.

    Exemplo:
    Thought: Tenho todos os dados necessários e contei quantos passes foram feitos por cada jogador.
    Final Answer: O jogador que realizou mais passes foi João, com 12 passes.

    
    
    • Id da partida:
    {id_partida}

    • Pergunta do Usuário:
    {pergunta}

    • Outras informações:
    {agent_scratchpad}
    """

    prompt = PromptTemplate(
       input_variables=['id_partida',
                        'pergunta',
                        'tools',
                        'tool_names',
                        'agent_scratchpad'],
       template=instrucoes
    )

    llm = ChatGoogleGenerativeAI(model='gemini-1.5-flash', temperature=0.2)

    ferramentas_react = [
        Tool(name='Tipos de Evento',
            func=tipos_react,
            description='Verifica quais os tipos de evento possíveis em uma partida de futebol (passes, chutes, faltas, etc.).'
            ),

        Tool(
            name='Obter Eventos',
            func=eventos_react,
            description='Coleta todos os eventos de uma partida usando o ID da partida e o tipo do evento.'
        ),

        Tool(name='Estatísticas de um Jogador',
             func=jogador_react,
             description='Obtém as estatísticas principais de um jogador praquela partida.'
             )
    ]

    agente = create_react_agent(llm=llm,
                                tools=ferramentas_react,
                                prompt=prompt)
    
    return AgentExecutor(
        agent=agente,
        tools=ferramentas_react,
        handle_parsing_errors=True,
        verbose=True,
        max_iterations=10
    )


@router.post('/react_agent', response_model=ModeloAgenteResposta)
async def agente_react(body: ModeloAgentePergunta):
    try:
        os.environ["GOOGLE_API_KEY"] = os.getenv('GEMINI_KEY')

        id_partida = body.id_partida
        pergunta = body.pergunta

        agente = carregar_agente()

        resposta = agente.invoke(input={'id_partida': id_partida,
                                        'pergunta': pergunta,
                                        },
                                handle_parsing_errors=True)

        return ModeloAgenteResposta(id_partida=resposta['id_partida'], pergunta=resposta['pergunta'], resposta=resposta['output'])

    except:
        raise HTTPException(status_code=500, detail='Erro! Não foi possível gerar uma resposta.')
