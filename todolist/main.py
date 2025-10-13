from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from models import User, Task 
from connector import SessionLocal, engine, Base 
from passlib.context import CryptContext

Base.metadata.create_all(bind = engine) 

app = FastAPI()
templates = Jinja2Templates(directory = "templates")
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/", response_class = HTMLResponse)
def home_page(request : Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    user = None
    tasks = [] 
    if user_id:
        user = db.query(User).filter(User.id == int(user_id)).first() 
        if user:
            tasks = db.query(Task).filter(Task.owner_id == int(user_id)).all() 
    return templates.TemplateResponse("index.html", {"request" : request, "tasks" : tasks, "user" : user})

@app.get("/register", response_class = HTMLResponse)
def register_page(request : Request): 
    return templates.TemplateResponse("register.html", {"request" : request})
@app.post("/register", response_class = HTMLResponse) 
def register(request : Request,
             username: str = Form(...),
             password: str = Form(...),
             db: Session = Depends(get_db)):
    if db.query(User).filter(User.name==username).first():
        return templates.TemplateResponse("register.html", {"request" : request, "error": "User already exist !"}) 
    else:
        hashed_password = pwd_context.hash(password)
        user = User(name  = username, hashed_password = hashed_password)
        db.add(user)
        db.commit()
        return RedirectResponse(url="/login", status_code = 303)

@app.post("/login")
def login(request : Request,
             username: str = Form(...),
             password: str = Form(...),
             db: Session = Depends(get_db)):
    user = db.query(User).filter(User.name == username).first()
    if not user:
        return templates.TemplateResponse("login.html", {"request" : request, "error": "User not found"})
    if not pwd_context.verify(password, user.hashed_password):
        return templates.TemplateResponse("login.html", {"request" : request, "error" : "Incorrect password"})
    
    response = RedirectResponse(url="/", status_code = 303)
    response.set_cookie(
        key="user_id",
        value=str(user.id),
        httponly=True,  # bảo mật cookie, JS không đọc được
        max_age=3600,   # 1h (tuỳ chọn)
        samesite="lax"
    )
    return response


@app.get("/login", response_class = HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request" : request}) 

@app.get("/add_task", response_class = HTMLResponse)
def add_task(request : Request):
    return templates.TemplateResponse("add_task.html", {"request" : request})
@app.get("/logout", response_class = HTMLResponse)
def logout():
    response = RedirectResponse(url = "/login", status_code = 303)
    response.delete_cookie("user_id")
    return response


@app.post("/tasks", response_class = HTMLResponse)
def add_task(request : Request,
             title: str = Form(...),
             db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code = 303)
    task = Task(title = title, owner_id = int(user_id))
    db.add(task)
    db.commit()
    return RedirectResponse(url="/", status_code = 303)

@app.get("/add_task", response_class = HTMLResponse)
def add_task_page(request : Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url = "/login", status_code = 303)
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        return RedirectResponse(url="/login", status_code = 303)
    return templates.TemplateResponse("add_task.html", {"request" : request , "user" : user})

@app.post("/tasks/{task_id}/delete", response_class = HTMLResponse)
def delete_task(task_id: int, request : Request , db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code = 303)
    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == int(user_id)).first()
    if not task:
        raise HTTPException(status_code = 404, detail ="Task not found")
    db.delete(task)
    db.commit()
    return RedirectResponse(url = "/", status_code = 303)

