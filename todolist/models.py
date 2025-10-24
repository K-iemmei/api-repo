from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from connector import Base

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    hashed_password = Column(String)

    # 👇 Thêm dòng này để liên kết ngược với Task
    tasks = relationship("Task", back_populates="owner", cascade="all, delete-orphan")


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String)
    description = Column(String, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"))

    # 👇 Liên kết đến User
    owner = relationship("User", back_populates="tasks")

