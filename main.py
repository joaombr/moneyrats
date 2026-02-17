from fastapi import FastAPI, Request, Depends, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles # Adicione esta linha
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import models
from database import SessionLocal, engine

# Cria as tabelas no banco de dados
models.Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")
app.mount("/static", StaticFiles(directory="static"), name="static")

# Função para conectar ao banco de dados
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- ROTAS DE NAVEGAÇÃO ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/minha-conta", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    email_logado = request.cookies.get("user_email")
    if not email_logado:
        return RedirectResponse(url="/", status_code=303)
        
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email_logado).first()
    return templates.TemplateResponse("dashboard.html", {"request": request, "usuario": usuario})

# --- ROTAS DE AUTENTICAÇÃO ---

@app.post("/cadastro")
async def cadastrar(
    nome: str = Form(...), 
    email: str = Form(...), 
    senha: str = Form(...), 
    salario: float = Form(...), 
    db: Session = Depends(get_db)
):
    novo_usuario = models.Usuario(
        nome=nome,
        email=email,
        senha=senha, # Corrigido: sem duplicidade
        salario=salario,
        total_poupado=0.0
    )
    db.add(novo_usuario)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/login")
async def login(
    response: Response, 
    email: str = Form(...), 
    senha: str = Form(...), 
    db: Session = Depends(get_db)
):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if usuario and usuario.senha == senha:
        response = RedirectResponse(url="/minha-conta", status_code=303)
        response.set_cookie(key="user_email", value=email) # Cria a sessão
        return response
    return RedirectResponse(url="/?erro=login_invalido", status_code=303)

# --- ROTAS DE GRUPOS E ECONOMIA ---

@app.post("/criar-grupo")
async def criar_grupo(
    request: Request,
    nome_grupo: str = Form(...), 
    meses: int = Form(...), 
    db: Session = Depends(get_db)
):
    email_logado = request.cookies.get("user_email")
    # Calcula data de fim baseada nos meses escolhidos
    data_final = datetime.now() + timedelta(days=meses * 30)
    
    novo_grupo = models.Grupo(nome=nome_grupo, data_fim=data_final)
    db.add(novo_grupo)
    db.commit()
    db.refresh(novo_grupo)
    
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email_logado).first()
    usuario.grupo_id = novo_grupo.id
    db.commit()
    return RedirectResponse(url="/minha-conta", status_code=303)

@app.post("/entrar-grupo")
async def entrar_grupo(request: Request, codigo: str = Form(...), db: Session = Depends(get_db)):
    email_logado = request.cookies.get("user_email")
    
    # O SEGREDO: .strip() remove espaços e .lower() garante que fique minúsculo
    codigo_formatado = codigo.strip().lower()
    
    # Agora a busca vai bater com o que está no banco (ecfb1554)
    grupo = db.query(models.Grupo).filter(models.Grupo.codigo_convite == codigo_formatado).first()
    
    if grupo:
        usuario = db.query(models.Usuario).filter(models.Usuario.email == email_logado).first()
        if usuario:
            usuario.grupo_id = grupo.id
            db.commit()
            return RedirectResponse(url="/minha-conta", status_code=303)
    
    return RedirectResponse(url="/minha-conta?erro=codigo_invalido", status_code=303)

@app.post("/lancar-economia")
async def lancar_economia(email: str = Form(...), valor: float = Form(...), db: Session = Depends(get_db)):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if usuario:
        # Só permite lançar se o desafio não expirou
        if usuario.grupo and datetime.now() > usuario.grupo.data_fim:
            return RedirectResponse(url="/minha-conta?erro=expirado", status_code=303)
            
        usuario.total_poupado += valor
        db.commit()
    return RedirectResponse(url="/minha-conta", status_code=303)

@app.get("/ranking/grupo/{grupo_id}", response_class=HTMLResponse)
async def ver_ranking(grupo_id: int, request: Request, db: Session = Depends(get_db)):
    grupo = db.query(models.Grupo).filter(models.Grupo.id == grupo_id).first()
    usuarios = db.query(models.Usuario).filter(models.Usuario.grupo_id == grupo_id).all()
    
    # Processa o ranking calculando o esforço %
    for u in usuarios:
        u.esforco = round((u.total_poupado / u.salario * 100), 1) if u.salario > 0 else 0
        
    ranking_ordenado = sorted(usuarios, key=lambda x: x.esforco, reverse=True)
    
    return templates.TemplateResponse("ranking.html", {
        "request": request,
        "usuarios": ranking_ordenado,
        "grupo": grupo,
        "agora": datetime.now(),
        "titulo_ranking": grupo.nome,
        "codigo_convite": grupo.codigo_convite
    })