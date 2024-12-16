
from fastapi import FastAPI
from .routers import router

app = FastAPI()

app.include_router(router)


@app.get('/')
async def raiz():
    return {'mensagem': 'Página raiz'}
