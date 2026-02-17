from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import models, database
from database import engine, get_db
from datetime import datetime
import uuid

# Inicializa o banco de dados e cria as tabelas (PostgreSQL no Render ou SQLite local)
models.Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# --- FUNÇÃO AUXILIAR PARA IDENTIFICAR O USUÁRIO LOGADO ---
def obter_usuario_logado(request: Request, db: Session):
    email = request.cookies.get("user_email")
    if not email:
        return None
    return db.query(models.Usuario).filter(models.Usuario.email == email).first()

# --- 1. ROTAS DE ACESSO (LOGIN, CADASTRO E LOGOUT) ---

@app.get("/")
async def home(request: Request):
    """Página inicial do site (Login/Cadastro)"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/cadastrar")
async def cadastrar_usuario(
    nome: str = Form(...), 
    email: str = Form(...), 
    senha: str = Form(...), 
    db: Session = Depends(get_db)
):
    usuario_existente = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if usuario_existente:
        return "Este e-mail já está cadastrado!"
    
    novo_usuario = models.Usuario(
        nome=nome, 
        email=email, 
        senha=senha, 
        esforco=0, 
        total_poupado=0.0
    )
    db.add(novo_usuario)
    db.commit()
    
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="user_email", value=email)
    return response

@app.post("/login")
async def login_usuario(
    email: str = Form(...), 
    senha: str = Form(...), 
    db: Session = Depends(get_db)
):
    usuario = db.query(models.Usuario).filter(
        models.Usuario.email == email, 
        models.Usuario.senha == senha
    ).first()
    
    if not usuario:
        return "E-mail ou senha incorretos!"
    
    response = RedirectResponse(url="/dashboard", status_code=303)
    response.set_cookie(key="user_email", value=email)
    return response

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("user_email")
    return response

# --- 2. DASHBOARD E GESTÃO DE GRUPOS ---

@app.get("/dashboard")
async def dashboard(request: Request, db: Session = Depends(get_db)):
    usuario = obter_usuario_logado(request, db)
    if not usuario:
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse("dashboard.html", {"request": request, "usuario": usuario})

@app.post("/criar-grupo")
async def criar_grupo(request: Request, nome: str = Form(...), db: Session = Depends(get_db)):
    usuario = obter_usuario_logado(request, db)
    if not usuario:
        return RedirectResponse(url="/", status_code=303)
    
    codigo_novo = str(uuid.uuid4())[:8].upper()

    novo_grupo = models.Grupo(
        nome=nome,
        codigo=codigo_novo,
        criador_id=usuario.id, # Define o usuário atual como o dono do grupo
        data_fim=datetime(2026, 12, 31) # Exemplo de validade
    )
    
    db.add(novo_grupo)
    db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=303)

# --- 3. EDIÇÃO DE GRUPO (SÓ PARA O DONO) ---

@app.get("/editar-grupo/{grupo_id}")
async def pagina_editar_grupo(request: Request, grupo_id: int, db: Session = Depends(get_db)):
    usuario = obter_usuario_logado(request, db)
    if not usuario:
        return RedirectResponse(url="/", status_code=303)
    
    grupo = db.query(models.Grupo).filter(models.Grupo.id == grupo_id).first()

    # Trava de Segurança: impede que outros usuários editem via URL
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
    nome: str = Form(...), 
    db: Session = Depends(get_db)
):
    usuario = obter_usuario_logado(request, db)
    if not usuario:
        return RedirectResponse(url="/", status_code=303)

    grupo = db.query(models.Grupo).filter(models.Grupo.id == grupo_id).first()
    
    # Validação final de autorização
    if grupo and grupo.criador_id == usuario.id:
        grupo.nome = nome
        db.commit()
    
    return RedirectResponse(url="/ranking", status_code=303)

# --- 4. RANKING ---

@app.get("/ranking")
async def exibir_ranking(request: Request, db: Session = Depends(get_db)):
    usuario_logado = obter_usuario_logado(request, db)
    if not usuario_logado:
        return RedirectResponse(url="/", status_code=303)

    # Busca o grupo principal (ajuste conforme sua lógica de múltiplos grupos)
    grupo = db.query(models.Grupo).first() 
    
    # Ordena os usuários pelo maior esforço
    usuarios_ranking = db.query(models.Usuario).order_by(models.Usuario.esforco.desc()).all()

    return templates.TemplateResponse("ranking.html", {
        "request": request,
        "grupo": grupo,
        "usuarios": usuarios_ranking,
        "usuario_logado": usuario_logado, # Passa o usuário para o HTML mostrar a engrenagem
        "agora": datetime.now()
    })

# --- INICIALIZAÇÃO LOCAL ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)