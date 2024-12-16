
from pydantic import BaseModel


class ModeloPartida(BaseModel):
    id_partida: int


class ModeloJogador(BaseModel):
    id_partida: int
    nome_jogador: str


class ModeloResumo(BaseModel):
    id_partida: int
    resumo: str


class ModeloEstatistica(BaseModel):
    id_partida: int
    estatisticas: dict
