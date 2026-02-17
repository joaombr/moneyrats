from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Request, Depends, Form, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import models
from database import engine, get_db # Importação corrigida
import uuid

# Cria as tabelas no banco de dados
models.Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Monta arquivos estáticos (CSS/Imagens)
try:
    app.mount("/static", StaticFiles(directory="static"), name="static")
except:
    print("Aviso: Pasta /static não encontrada. Crie-a para usar CSS próprio.")

# --- ROTAS DE NAVEGAÇÃO ---

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request, db: Session = Depends(get_db)):
    email_logado = request.cookies.get("user_email")
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email_logado).first()
    
    grupo_atual = None
    if usuario and usuario.grupo_id:
        # Forçamos a busca do grupo para garantir que a data_fim venha junto
        grupo_atual = db.query(models.Grupo).filter(models.Grupo.id == usuario.grupo_id).first()
        
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "usuario": usuario, 
        "grupo": grupo_atual # Variável que o HTML usa para mostrar a data
    })

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
        senha=senha,
        salario=salario,
        total_poupado=0.0
    )
    db.add(novo_usuario)
    db.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/login")
async def login(
    email: str = Form(...), 
    senha: str = Form(...), 
    db: Session = Depends(get_db)
):
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email).first()
    if usuario and usuario.senha == senha:
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="user_email", value=email)
        return response
    return RedirectResponse(url="/?erro=login_invalido", status_code=303)

# --- ROTAS DE GRUPOS ---

@app.post("/criar-grupo")
async def criar_grupo(
    request: Request,
    nome_grupo: str = Form(...), 
    meses: int = Form(...), 
    db: Session = Depends(get_db)
):
    email_logado = request.cookies.get("user_email")
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email_logado).first()
    
    if not usuario:
        return RedirectResponse(url="/", status_code=303)

    # 1. Calcula data de fim
    data_final = datetime.now() + timedelta(days=meses * 30)
    
    # 2. GERA O CÓDIGO DE CONVITE (O que estava faltando!)
    # Se o seu models.py espera 'codigo_convite', o banco trava sem isso.
    novo_codigo = str(uuid.uuid4())[:8].upper()

    # 3. Cria o grupo com todos os campos necessários
    novo_grupo = models.Grupo(
        nome=nome_grupo, 
        codigo_convite=novo_codigo, # Campo essencial
        data_fim=data_final,
        criador_id=usuario.id 
    )
    
    try:
        db.add(novo_grupo)
        db.commit()
        db.refresh(novo_grupo)
        
        # 4. VINCULA o usuário ao grupo
        usuario.grupo_id = novo_grupo.id
        db.commit()
        
        # 5. Redireciona com sucesso
        return RedirectResponse(url="/dashboard", status_code=303)
    except Exception as e:
        db.rollback()
        print(f"Erro ao criar grupo: {e}")
        return "Erro interno ao salvar no banco de dados."
    
@app.post("/entrar-grupo")
async def entrar_grupo(
    request: Request, 
    codigo: str = Form(...), 
    db: Session = Depends(get_db)
):
    # 1. Recupera o e-mail do usuário logado via cookie
    email_logado = request.cookies.get("user_email")
    if not email_logado:
        return RedirectResponse(url="/", status_code=303)

    # 2. Busca o grupo pelo código (limpando espaços e forçando maiúsculas)
    codigo_limpo = codigo.strip().upper()
    grupo = db.query(models.Grupo).filter(models.Grupo.codigo_convite == codigo_limpo).first()
    
    if not grupo:
        # Se o código não existir, volta com aviso de erro
        return RedirectResponse(url="/dashboard?erro=codigo_invalido", status_code=303)

    # 3. Busca o usuário e vincula ele ao grupo encontrado
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email_logado).first()
    if usuario:
        usuario.grupo_id = grupo.id
        db.commit()
        
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/lancar-economia")
async def lancar_economia(
    request: Request, 
    valor: float = Form(...), 
    db: Session = Depends(get_db)
):
    # 1. Identifica o usuário pelo cookie de e-mail
    email_logado = request.cookies.get("user_email")
    if not email_logado:
        return RedirectResponse(url="/", status_code=303)

    # 2. Busca o usuário no banco
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email_logado).first()
    
    if usuario:
        # Só permite lançar se o grupo não estiver expirado
        if usuario.grupo_id:
            grupo = db.query(models.Grupo).filter(models.Grupo.id == usuario.grupo_id).first()
            if grupo and datetime.now() > grupo.data_fim:
                return RedirectResponse(url="/dashboard?erro=prazo_encerrado", status_code=303)

        # 3. Soma o novo valor ao total já poupado
        usuario.total_poupado += valor
        db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=303)

# Rota para abrir a página de edição
# Rota para carregar a página de edição
@app.get("/editar-grupo/{grupo_id}", response_class=HTMLResponse)
async def carregar_edicao(grupo_id: int, request: Request, db: Session = Depends(get_db)):
    email_logado = request.cookies.get("user_email")
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email_logado).first()
    grupo = db.query(models.Grupo).filter(models.Grupo.id == grupo_id).first()

    # Segurança: Só o criador edita
    if not grupo or not usuario or grupo.criador_id != usuario.id:
        return RedirectResponse(url="/ranking", status_code=303)

    return templates.TemplateResponse("editar_grupo.html", {"request": request, "grupo": grupo})

# Rota para salvar nome e novo prazo
@app.post("/salvar-edicao-grupo/{grupo_id}")
async def salvar_edicao(
    grupo_id: int, 
    nome: str = Form(...), 
    meses: int = Form(...), # O FastAPI vai ler o valor do select aqui
    db: Session = Depends(get_db)
):
    grupo = db.query(models.Grupo).filter(models.Grupo.id == grupo_id).first()
    if grupo:
        grupo.nome = nome
        # Atualiza a data de fim somando os meses a partir de AGORA
        grupo.data_fim = datetime.now() + timedelta(days=meses * 30)
        db.commit()
    return RedirectResponse(url="/ranking", status_code=303)

@app.post("/deletar-grupo/{grupo_id}")
async def deletar_grupo(grupo_id: int, request: Request, db: Session = Depends(get_db)):
    email_logado = request.cookies.get("user_email")
    usuario = db.query(models.Usuario).filter(models.Usuario.email == email_logado).first()
    grupo = db.query(models.Grupo).filter(models.Grupo.id == grupo_id).first()

    # Só o criador pode deletar
    if grupo and usuario and grupo.criador_id == usuario.id:
        # Remove o vínculo de todos os usuários do grupo antes de deletar o grupo
        db.query(models.Usuario).filter(models.Usuario.grupo_id == grupo.id).update({"grupo_id": None})
        db.delete(grupo)
        db.commit()
    
    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/ranking", response_class=HTMLResponse)
async def ver_ranking(request: Request, db: Session = Depends(get_db)):
    email_logado = request.cookies.get("user_email")
    usuario_logado = db.query(models.Usuario).filter(models.Usuario.email == email_logado).first()
    
    # Redireciona se não estiver logado ou não tiver grupo
    if not usuario_logado or not usuario_logado.grupo_id:
        return RedirectResponse(url="/dashboard", status_code=303)

    # Busca o grupo e todos os participantes
    grupo = db.query(models.Grupo).filter(models.Grupo.id == usuario_logado.grupo_id).first()
    usuarios = db.query(models.Usuario).filter(models.Usuario.grupo_id == grupo.id).all()
    
    # 1. Calcula o esforço individual de cada membro para o ranking
    for u in usuarios:
        if u.salario and u.salario > 0:
            u.esforco = round((u.total_poupado / u.salario * 100), 1)
        else:
            u.esforco = 0
        
    # 2. ORDENAÇÃO CORRIGIDA: 
    # Usamos 'x.esforco' (referente a cada item da lista) e não 'u.esforco' (que seria apenas o último do loop)
    ranking_ordenado = sorted(usuarios, key=lambda x: x.esforco, reverse=True)
    
    return templates.TemplateResponse("ranking.html", {
        "request": request,
        "usuarios": ranking_ordenado,
        "grupo": grupo,
        "usuario_logado": usuario_logado,
        "agora": datetime.now()
    })

    # atualização: 20/10/2024 - Correção de bugs, melhorias na experiência do usuário e ajustes visuais. O código agora é mais robusto e fácil de manter!