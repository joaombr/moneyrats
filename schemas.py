from pydantic import BaseModel

class UsuarioCreate(BaseModel):
    nome: str
    email: str
    meta_mensal: float
    senha: str