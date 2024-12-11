
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from statsbombpy import sb
import numpy as np
import json

app = FastAPI()


@app.get('/')
async def raiz():
    return {'mensagem': 'Página raiz'}


@app.get('/partidas/{id_partida}')
async def get_partida(id_partida: int):
    try:
        partida = sb.events(id_partida)
        partida = partida.to_dict(orient='records')
        for evento in partida:
            for chave, valor in evento.items():
                if valor is np.nan:
                    valor = None
                evento[chave] = valor
        partida = json.dumps(partida)
        return partida
    except ValueError:
        raise HTTPException(status_code=422, detail='Insira um valor numérico para a partida.')
    except Exception:
        raise HTTPException(status_code=500, detail='Erro ao processar a partida.')
