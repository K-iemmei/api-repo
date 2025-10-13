from pydantic import BaseModel, Field 

class User(BaseModel):
    username : str = Field(..., example="john_doe")
    password : str = Field(..., example="strongpassword123") 

class TaskCreate(BaseModel):
    title : str = Field(..., example="Buy groceries") 

class TaskUpdate(BaseModel):
    id: int 
    title: str 
    completed: bool 
    owner_id: int 

    class Config:
        orm_mode = True

        