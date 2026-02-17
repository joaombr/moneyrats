from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    email = Column(String, unique=True, index=True)
    senha = Column(String)
    salario = Column(Float, default=0.0)
    esforco = Column(Integer, default=0)
    total_poupado = Column(Float, default=0.0)
    
    # Define a qual grupo o usuário pertence
    grupo_id = Column(Integer, ForeignKey("grupos.id"))

class Grupo(Base):
    __tablename__ = "grupos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    codigo_convite = Column(String, unique=True, index=True)
    data_fim = Column(DateTime, default=datetime.now)
    
    # Define quem é o dono do grupo
    criador_id = Column(Integer, ForeignKey("usuarios.id"))
    
    # Relacionamentos explícitos para evitar erros de ambiguidade
    usuarios = relationship("Usuario", foreign_keys=[Usuario.grupo_id])
    criador = relationship("Usuario", foreign_keys=[criador_id])