from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import Base
import uuid

class Grupo(Base):
    __tablename__ = "grupos"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, unique=True)
    codigo_convite = Column(String, unique=True, default=lambda: str(uuid.uuid4())[:8])
    data_criacao = Column(DateTime, default=datetime.utcnow)
    data_fim = Column(DateTime) # Define o fim do desafio (ex: 6 meses)
    
    usuarios = relationship("Usuario", back_populates="grupo")

class Usuario(Base):
    __tablename__ = "usuarios"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String)
    email = Column(String, unique=True, index=True)
    senha = Column(String)
    salario = Column(Float, default=0.0) # NOVO
    total_poupado = Column(Float, default=0.0)
    
    # Ligação com o Grupo
    grupo_id = Column(Integer, ForeignKey("grupos.id"), nullable=True)
    grupo = relationship("Grupo", back_populates="usuarios")