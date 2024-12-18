
# Importações
import streamlit as st
import requests
import google.generativeai as genai
import os
from statsbombpy import sb
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt



# Configurações
st.set_page_config(
    page_title='Análises de Partidas de Futebol',
    page_icon='⚽',
)

st.title('Análises de Partidas de Futebol')

pag_1_title = 'Selecionar a Partida'
pag_2_title = 'Eventos da Partida'
pag_3_title = 'Estatísticas dos Jogadores'
pag_4_title = 'Assistentes Virtuais'

api_key = os.getenv('GEMINI_KEY')
genai.configure(api_key=api_key)
modelo = genai.GenerativeModel('gemini-1.5-flash')

if all(key not in st.session_state for key in ['camp_selecionado', 'temp_selecionada', 'partida_selecionada',
    'id_partida', 'partidas', 'eventos', 'pos_campo', 'taticas']):
        st.session_state['camp_selecionado'] = 0
        st.session_state['temp_selecionada'] = 0
        st.session_state['partida_selecionada'] = 0
        st.session_state['id_partida'] = None
        st.session_state['partidas'] = None
        st.session_state['eventos'] = None



# Funções de Uso Geral
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


def filtrar_eventos(eventos, filtros):
    df_original = eventos.copy()
    df_filtrado = pd.DataFrame([])
    if 'Gols' in filtros:
        df_filtrado = pd.concat([df_filtrado, df_original[df_original['shot_outcome'] == 'Goal']])
    if 'Passes' in filtros:
        df_filtrado = pd.concat([df_filtrado, df_original[df_original['type'] == 'Pass']])
    if 'Finalizações' in filtros:
        df_filtrado = pd.concat([df_filtrado, df_original[df_original['type'] == 'Shot']])
    if 'Faltas' in filtros:
        df_filtrado = pd.concat([df_filtrado, df_original[df_original['type'] == 'Foul Committed']])

    df_filtrado.sort_index(inplace=True)
    df_filtrado = df_filtrado.sort_values(by='minute').to_dict(orient='records')
    partida = []

    for evento_bruto in df_filtrado:
        evento = {}
        for chave, valor in evento_bruto.items():
                if valor is not np.nan:
                    evento[chave] = valor
        partida.append(evento)

    df_final = pd.DataFrame(partida)
    return df_final


# Páginas
def pagina_um():
    # ESCOLHENDO E EXIBINDO UMA PARTIDA
    st.header('• Selecionar a Partida')

    # Competição
    competicoes = sb.competitions()
    nomes_competicoes = list(competicoes['competition_name'].unique())
    try:
        filtro_campeonato = st.selectbox(label='Selecione o campeonato:', options=nomes_competicoes, index=st.session_state['camp_selecionado'])
    except:
        filtro_campeonato = st.selectbox(label='Selecione o campeonato:', options=nomes_competicoes)
    st.session_state['camp_selecionado'] = nomes_competicoes.index(filtro_campeonato)
    id_campeonato = competicoes[competicoes['competition_name'] == filtro_campeonato]['competition_id'].values[0]

    # Temporada
    temporadas = list(competicoes[competicoes['competition_name'] == filtro_campeonato]['season_name'].unique())
    try:
        filtro_temporada = st.selectbox(label='Selecione o ano ou temporada:', options=temporadas, index=st.session_state['temp_selecionada'])
    except:
        filtro_temporada = st.selectbox(label='Selecione o ano ou temporada:', options=temporadas)
    st.session_state['temp_selecionada'] = temporadas.index(filtro_temporada)
    id_temporada = competicoes[competicoes['season_name'] == filtro_temporada]['season_id'].values[0]

    st.session_state['partidas'] = sb.matches(competition_id=id_campeonato, season_id=id_temporada)

    # Partida
    try:
        st.session_state['id_partida'] = st.selectbox(label='Selecione a partida:',
                                            options=st.session_state['partidas']['match_id'],
                                            index=st.session_state['partida_selecionada'],
                                            format_func=lambda id_partida: formatar_partida(st.session_state['partidas'], id_partida)
                                            )
    except:
        st.session_state['id_partida'] = st.selectbox(label='Selecione a partida:',
                                            options=st.session_state['partidas']['match_id'],
                                            format_func=lambda id_partida: formatar_partida(st.session_state['partidas'], id_partida)
                                            )

    st.session_state['partida_selecionada'] = int(st.session_state['partidas'][st.session_state['partidas']['match_id'] == st.session_state['id_partida']].index[0])
    st.session_state['eventos'] = sb.events(st.session_state['id_partida'])

    exibir_partida(st.session_state['partidas'], st.session_state['id_partida'])


def pagina_dois():
    st.header('• Eventos da Partida')
    if st.session_state['eventos'] is not None:
        filtrar_radio = st.radio(label='', options=['Todos', 'Filtrar eventos'])
        if filtrar_radio == 'Filtrar eventos':
            opcoes_eventos = ['Gols', 'Passes', 'Finalizações', 'Faltas']
            filtro_eventos = st.multiselect(label='Selecione um tipo de evento:', options=opcoes_eventos, default=opcoes_eventos)
            eventos_filtrados = filtrar_eventos(st.session_state['eventos'], filtro_eventos)
            st.write(eventos_filtrados)
        else:
            st.write(st.session_state['eventos'])
    else:
        st.error('Selecione uma partida na página inicial.')



def pagina_tres():
    st.header('• Estatísticas dos Jogadores')
    if st.session_state['eventos'] is not None:
        opcoes_jogadores = st.session_state['eventos'].sort_values(by='team')['player'].dropna().unique()
        sel_jogador = st.selectbox('Selecione um jogador:',
                                    options=opcoes_jogadores,
                                    format_func=lambda nome_jogador: formatar_jogador(st.session_state['eventos'], nome_jogador))
        resp_estatisticas = requests.post('http://127.0.0.1:8000/player_profile', json={'id_partida':st.session_state['id_partida'],
                                                                                        'nome_jogador': sel_jogador}
                                                                                        )
        if resp_estatisticas:
            df_estatisticas = pd.DataFrame(resp_estatisticas.json()['estatisticas'], index=[0])
            st.dataframe(df_estatisticas)
            # Visualização
            fig_1, ax_1 = plt.subplots()
            
            ax_1.bar(df_estatisticas.drop('jogador', axis=1).columns.tolist(),
                            df_estatisticas.drop('jogador', axis=1).values.tolist()[0],
                            color=['blue', 'green', 'red', 'purple'])

            plt.title(f'Estatísticas de {df_estatisticas["jogador"][0]}')
            plt.ylabel('Quantidade')
            st.pyplot(fig_1)
            if st.checkbox('Comparar com outro jogador:'):
                opcoes_jogador_2 = list(opcoes_jogadores).copy()
                opcoes_jogador_2.remove(sel_jogador)
                sel_jogador_2 = st.selectbox('Selecione outro jogador:',
                                            options=opcoes_jogador_2,
                                            format_func=lambda nome_jogador: formatar_jogador(st.session_state['eventos'], nome_jogador))
                resp_estatisticas_2 = requests.post('http://127.0.0.1:8000/player_profile', json={'id_partida':st.session_state['id_partida'],
                                                                                'nome_jogador': sel_jogador_2})
                if resp_estatisticas_2:
                    df_estatisticas_2 = pd.DataFrame(resp_estatisticas_2.json()['estatisticas'], index=[0])
                    st.dataframe(df_estatisticas_2)
                    # Visualização
                    fig_2, ax_2= plt.subplots()
                    
                    ax_2.bar(df_estatisticas_2.drop('jogador', axis=1).columns.tolist(),
                                    df_estatisticas_2.drop('jogador', axis=1).values.tolist()[0],
                                    color=['blue', 'green', 'red', 'purple'])

                    plt.title(f'Estatísticas de {df_estatisticas_2["jogador"][0]}')
                    plt.ylabel('Quantidade')
                    st.pyplot(fig_2)
                    # Métricas Comparativas
                    st.subheader('Métricas')
                    col_1, col_2 = st.columns(2)
                    # Jogador 1
                    col_1.metric('Jogador', df_estatisticas['jogador'][0])
                    col_1.metric('Passes', df_estatisticas['passes'][0])
                    col_1.metric('Finalizações', df_estatisticas['finalizacoes'][0])
                    col_1.metric('Desarmes', df_estatisticas['desarmes'][0])
                    col_1.metric('Minutos Jogados', df_estatisticas['minutos_jogados'][0])
                    # Jogador 2
                    col_2.metric('Jogador', df_estatisticas_2['jogador'][0])
                    col_2.metric('Passes', df_estatisticas_2['passes'][0])
                    col_2.metric('Finalizações', df_estatisticas_2['finalizacoes'][0])
                    col_2.metric('Desarmes', df_estatisticas_2['desarmes'][0])
                    col_2.metric('Minutos Jogados', df_estatisticas_2['minutos_jogados'][0])
    else:
        st.error('Selecione uma partida na página inicial.')


def pagina_quatro():
    st.header('• Assistentes Virtuais')

    if st.session_state['id_partida'] is not None:
        # Resumo
        st.subheader('Resumo')
        if st.button('Gerar resumo da partida por IA'):
            with st.spinner('Carregando...'):
                resp_resumo = requests.post('http://127.0.0.1:8000/match_summary', json={'id_partida':st.session_state['id_partida']})
                st.write(resp_resumo.json()['resumo'])
        
        # Narração
        st.subheader('Narração')
        tom_narracao = st.radio(label='', options=['Formal', 'Humorístico', 'Técnico'])
        if st.button('Gerar narração da partida por IA'):
            with st.spinner('Carregando...'):
                resp_narracao = requests.post('http://127.0.0.1:8000/commentary', json={'id_partida':st.session_state['id_partida'],
                                                                                        'tom_narracao': tom_narracao})
                st.write(resp_narracao.json()['resumo'])

        # Agente ReAct
        st.subheader('Pergunte algo ao assistente')
        if prompt := st.chat_input('Digite sua pergunta:'):
            with st.spinner('Carregando...'):
                resp_pergunta = requests.post('http://127.0.0.1:8000/react_agent', json={'id_partida':st.session_state['id_partida'],
                                                                                        'pergunta':prompt})
                st.write(resp_pergunta.json())
        
    else:
        st.error('Selecione uma partida na página inicial.')



# Navegação
st.sidebar.title('Navegação')
pagina = st.sidebar.radio(label='Escolha uma página:', options=(pag_1_title, pag_2_title, pag_3_title, pag_4_title))
if pagina == pag_1_title:
    pagina_um()
elif pagina == pag_2_title:
    pagina_dois()
elif pagina == pag_3_title:
    pagina_tres()
else:
    pagina_quatro()
