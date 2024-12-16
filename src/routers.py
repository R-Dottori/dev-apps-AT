
from fastapi import APIRouter, HTTPException
from .models import ModeloPartida, ModeloJogador, ModeloResumo, ModeloEstatistica
import pandas as pd
from statsbombpy import sb
import numpy as np
import google.generativeai as genai
import os

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
    resposta = modelo.generate_content(instrucoes).text
    return ModeloResumo(id_partida=body.id_partida, resumo=resposta)


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
