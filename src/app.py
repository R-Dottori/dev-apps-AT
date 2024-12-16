
import streamlit as st
import requests
import google.generativeai as genai
import os
from statsbombpy import sb
import numpy as np
import pandas as pd

st.set_page_config(
    page_title='Análises de Partidas de Futebol',
    page_icon='⚽',
)

st.title('Análises de Partidas de Futebol')

api_key = os.getenv('GEMINI_KEY')
genai.configure(api_key=api_key)
modelo = genai.GenerativeModel('gemini-1.5-flash')


def formatar_competicao(competicoes, id_competicao):
    linha_competicao = competicoes[competicoes['competition_id'] == id_competicao].iloc[0]
    nome_competicao = f'{linha_competicao['competition_name']}'
    return nome_competicao


def formatar_partida(partidas, id_partida):
    linha_partida = partidas[partidas['match_id'] == id_partida].iloc[0]
    nome_partida = f'{linha_partida['match_date']} — {linha_partida['home_team']} x {linha_partida['away_team']}'
    return nome_partida


def formatar_jogador(eventos, nome_jogador):
    linha_jogador = eventos[eventos['player'] == nome_jogador].iloc[0]
    nome_jogador = f'{linha_jogador['team']} — {linha_jogador['player']}'
    return nome_jogador


def exibir_partida(partidas, sel_partida):
    data = partidas[partidas['match_id'] == sel_partida]['match_date'].values[0]
    time_casa = partidas[partidas['match_id'] == sel_partida]['home_team'].values[0]
    gols_casa = partidas[partidas['match_id'] == sel_partida]['home_score'].values[0]
    time_fora = partidas[partidas['match_id'] == sel_partida]['away_team'].values[0]
    gols_fora = partidas[partidas['match_id'] == sel_partida]['away_score'].values[0]
    st.subheader(data)
    col_1, col_2 = st.columns(2)
    with col_1:
        st.subheader('Time da Casa')
        st.subheader(time_casa)
        st.metric('Gols', gols_casa)
    with col_2:
        st.subheader('Time de Fora')
        st.subheader(time_fora)
        st.metric('Gols', gols_fora)
    st.markdown(f':green[(ID da partida = {sel_partida})]')


def estatisticas_jogador(eventos, nome_jogador):
    jogadores = eventos['player'].dropna().unique().tolist()
    
    jogadores_iniciais = [jogador['player']['name'] for jogador in eventos[eventos['type'] == 'Starting XI']['tactics'][0]['lineup']] \
                        + [jogador['player']['name'] for jogador in eventos[eventos['type'] == 'Starting XI']['tactics'][1]['lineup']]
    eventos_jogador = eventos[eventos['player'].str.contains(nome_jogador, na=False)]
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
                                                - eventos[
                                                                (eventos['type'] == 'Substitution')
                                                                & (eventos['substitution_replacement'] == estatisticas['jogador'])
                                                                ]['minute'].iloc[0]
                                                )

    return pd.DataFrame(estatisticas, index=[0])


def resumir_partida(eventos):
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
    return resposta



# ESCOLHENDO E EXIBINDO UMA PARTIDA
st.header('• Escolha uma Partida')

# Competição
competicoes = sb.competitions()
sel_competicao = st.selectbox('Selecione o campeonato:',
                                options=competicoes[['competition_id', 'competition_name']].drop_duplicates(),
                                format_func=(lambda id_competicao: formatar_competicao(competicoes, id_competicao)))

# Temporada
temporadas = list(competicoes[competicoes['competition_id'] == sel_competicao]['season_name'].unique())
sel_temporada = st.selectbox(label='Selecione o ano ou temporada:',
                                options=temporadas)
id_temporada = competicoes[(competicoes['competition_id'] == sel_competicao) & (competicoes['season_name'] == sel_temporada)]['season_id'].values[0]

# Partidas
partidas = sb.matches(competition_id=sel_competicao, season_id=id_temporada)
sel_partida = st.selectbox('Selecione a partida:',
                            options=partidas,
                            format_func=lambda id_partida: formatar_partida(partidas, id_partida))

# Eventos
eventos_bruto = sb.events(sel_partida)

st.header('• Partida Selecionada')
exibir_partida(partidas, sel_partida)



# ESCOLHENDO UM JOGADOR E MOSTRANDO SUAS ESTATÍSTICAS
st.header('• Estatísticas de um Jogador')
sel_jogador = st.selectbox('Selecione um jogador:',
                            options=eventos_bruto.sort_values(by='team')['player'].dropna().unique(),
                            format_func=lambda nome_jogador: formatar_jogador(eventos_bruto, nome_jogador))
df_estatisticas = estatisticas_jogador(eventos_bruto, sel_jogador)
st.dataframe(df_estatisticas)



# EVENTOS E RESUMO POR IA
st.header('• Resumo da Partida')
eventos_bruto = eventos_bruto.sort_values(by='minute').to_dict(orient='records')
partida = []

for evento_bruto in eventos_bruto:
    evento = {}
    for chave, valor in evento_bruto.items():
            if valor is not np.nan:
                evento[chave] = valor
    partida.append(evento)

eventos = []
for evento in partida:
    if evento['type'] == 'Shot' or evento['type'] == 'Pass' or evento['type'] == 'Foul Committed':
        eventos.append(evento)

df_eventos = pd.DataFrame(eventos)

st.subheader('Eventos principais da partida')
st.write(df_eventos)

st.subheader('Gerar resumo por IA')
if st.button('Gerar resumo'):
    with st.spinner('Carregando...'):
        resumo = resumir_partida(eventos)
        st.write(resumo)
    
