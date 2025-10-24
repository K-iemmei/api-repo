from fastapi import FastAPI, Depends, Request, Form, HTTPException 
from fastapo import HTTPResponse, RedirectResponse 
from sqlalchemy.orm import Session





app = FastAPI() 


@app.get("/", response_class = HTTPResponse)
def home_page(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    user = None
    if user_id:
        user = db.get(User).filter(User.id == user_id).first()
    
    return templates.template("index.html", {"request" : request}) 



