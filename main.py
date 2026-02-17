from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import models, database
from database import engine, get_db
from datetime import datetime

# Cria as tabelas no banco de dados (PostgreSQL no Render ou SQLite local)
models.Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- FUNÇÃO AUXILIAR PARA OBTER USUÁRIO ---
def obter_usuario_logado(request: Request, db: Session):
    email = request.cookies.get("user_email")
    if not email:
        return None
    return db.query(models.Usuario).filter(models.Usuario.email == email).first()

# --- ROTAS DE EDIÇÃO DE GRUPO ---

@app.get("/editar-grupo/{grupo_id}")
async def pagina_editar_grupo(request: Request, grupo_id: int, db: Session = Depends(get_db)):
    usuario = obter_usuario_logado(request, db)
    
    # Verifica se o usuário está logado
    if not usuario:
        return RedirectResponse(url="/", status_code=303)
    
    grupo = db.query(models.Grupo).filter(models.Grupo.id == grupo_id).first()

    # TRAVA DE SEGURANÇA: Só o dono do grupo (criador_id) pode acessar
    if not grupo or grupo.criador_id != usuario.id:
        return RedirectResponse(url="/dashboard", status_code=303)

    return templates.TemplateResponse("editar_grupo.html", {
        "request": request, 
        "grupo": grupo,
        "usuario": usuario
    })

@app.post("/salvar-edicao-grupo/{grupo_id}")
async def salvar_edicao(
    request: Request, 
    grupo_id: int, 
    nome: str = Form(...), # Corrigido: captura o nome diretamente do formulário
    db: Session = Depends(get_db)
):
    usuario = obter_usuario_logado(request, db)
    if not usuario:
        return RedirectResponse(url="/", status_code=303)

    grupo = db.query(models.Grupo).filter(models.Grupo.id == grupo_id).first()
    
    # Verifica novamente se é o dono antes de salvar
    if grupo and grupo.criador_id == usuario.id:
        grupo.nome = nome
        db.commit()
    
    return RedirectResponse(url="/ranking", status_code=303)

# --- ROTA DE RANKING ATUALIZADA ---

@app.get("/ranking")
async def exibir_ranking(request: Request, db: Session = Depends(get_db)):
    usuario_logado = obter_usuario_logado(request, db)
    if not usuario_logado:
        return RedirectResponse(url="/", status_code=303)

    # Busca o grupo (ajuste a lógica conforme como você associa usuário ao grupo)
    grupo = db.query(models.Grupo).first() 
    usuarios_ranking = db.query(models.Usuario).all() # Exemplo simples de listagem

    return templates.TemplateResponse("ranking.html", {
        "request": request,
        "grupo": grupo,
        "usuarios": usuarios_ranking,
        "usuario_logado": usuario_logado, # Necessário para o botão de engrenagem aparecer
        "agora": datetime.now()
    })

# --- ROTA DE CRIAR GRUPO (AJUSTADA) ---

@app.post("/criar-grupo")
async def criar_grupo(request: Request, nome: str = Form(...), db: Session = Depends(get_db)):
    usuario = obter_usuario_logado(request, db)
    if not usuario:
        return RedirectResponse(url="/", status_code=303)
    
    # Lógica para gerar código único (exemplo)
    import uuid
    codigo_novo = str(uuid.uuid4())[:8].upper()

    novo_grupo = models.Grupo(
        nome=nome,
        codigo=codigo_novo,
        criador_id=usuario.id, # IMPORTANTE: define o dono do grupo para a edição funcionar
        data_fim=datetime(2026, 12, 31) # Exemplo de data
    )
    
    db.add(novo_grupo)
    db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=303)