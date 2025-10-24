from fastapi import FastAPI, Depends, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from models import User, Task 
from connector import SessionLocal, engine, Base 
from passlib.context import CryptContext
from langchain_google_genai import ChatGoogleGenerativeAI 
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.memory import MemorySaver 
from langgraph.graph import StateGraph, START, END 
from langgraph.graph.message import add_messages 
from typing import Annotated, TypedDict
from langchain_core.runnables import RunnableConfig 
from langgraph.prebuilt import ToolNode, tools_condition 
import random
from dotenv import load_dotenv
import os

load_dotenv()

class State(TypedDict):
    messages: Annotated[list, add_messages]

class Message(BaseModel):
    message: str

Base.metadata.create_all(bind = engine) 

app = FastAPI() 
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    print("Cookies:", request.cookies)
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
        httponly=True,  
        max_age=3600, 
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
             description:str = Form(...),
             db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code = 303)
    task = Task(title = title, description = description, owner_id = int(user_id))
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

graph_builder = StateGraph(State) 
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)

memory = MemorySaver()
   
def chat_bot(state: State):
    return {"messages": llm.invoke(state["messages"])} 

graph_builder.add_node("chatbot", chat_bot)
graph_builder.add_edge(START, "chatbot")   
graph_builder.add_edge("chatbot", END) 
graph = graph_builder.compile(checkpointer=memory) 

class Message(BaseModel):
    message: str

@app.post("/chat")
async def receive_message(msg: Message):
    user_message = msg.message
    config = RunnableConfig(recursion_limit=10, configurable={"thread_id": "1"})
    bot_response = ""
    for event in graph.stream({"messages": [("user", user_message)]}, config=config):
        for value in event.values():
            bot_response = value['messages'].content

    return {"reply": bot_response}
@app.post("/reload_event") 
async def reload_event():
    memory.delete_thread("1")
    return {"status": "events reloaded"} 

@app.post("/chat_with_user")
async def receive_message_from_user(msg: Message,  request : Request , db: Session = Depends(get_db)):
    user_message = msg.message
    user_id = request.cookies.get("user_id")
    user = None
    tasks = []    
    if user_id:
        user = db.query(User).filter(User.id == int(user_id)).first()  
        if user:
            tasks = db.query(Task).filter(Task.owner_id == int(user_id)).all() 
    config = RunnableConfig(recursion_limit=10, configurable={"thread_id": user_id})
    tasks = db.query(Task).filter(Task.owner_id == int(user_id)).all() 
    user = db.query(User).filter(User.id == int(user_id)).first()
    task_list = [f"- {t.title}: {t.description}:deadline " for t in tasks]
    task_text = "\n".join(task_list)
    user_text = f"Tên: {user.name}\nId: {user.id}"
 
    state = { 
        "messages": [
            {"role": "system", "content": "Bạn là trợ lý AI, có quyền truy cập thông tin user và task."},
            {"role": "system", "content": f"Thông tin người dùng:\n{user_text}"},
            {"role": "system", "content": f"Danh sách task:\n{task_text}"},
            {"role": "user", "content": user_message}
        ]
    }

    config = RunnableConfig(
        recursion_limit=10,
        configurable={"thread_id": user_id}
    )

    result = graph.invoke(state, config=config)
    response_message = result["messages"][-1].content
    return {"reply": response_message}