from contextlib import asynccontextmanager
from datetime import timedelta
from random import choices
from typing import List
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, WebSocket
from sqlalchemy import create_engine, Column, Integer, Boolean, String, DateTime, ForeignKey
from sqlalchemy.orm import sessionmaker, DeclarativeBase, relationship, Mapped, mapped_column
import psycopg2
import datetime



DATABASE_URL = "postgresql://user:pass@localhost/voting"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

class Base(DeclarativeBase):
    pass

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield

app = FastAPI(lifespan=lifespan)

class VoteTopic(Base):
    __tablename__ = "vote_topics"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement="auto")
    active = Column(Boolean, default=True)
    content = Column(String, nullable=False)
    choices: Mapped[List["VoteChoice"]] = relationship(back_populates="topic", cascade="all, delete-orphan")
    #votes = uservotes
    created = Column(DateTime, default=datetime.datetime.now())
    ends = Column(DateTime, default=datetime.datetime.now() + timedelta(days=2))

class VoteChoice(Base):
    __tablename__ = "vote_choices"
    id: Mapped[int] = mapped_column(primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("vote_topics.id"))
    content = Column(String)
    votes = Column(Integer, default = 0)
    topic: Mapped["VoteTopic"] = relationship(back_populates="choices")


class Vote(BaseModel):
    topic_id: int
    choice: str

class NewVote(BaseModel):
    content: str
    choices: List[str]


"""
con = psycopg2.connect(
    dbname="voting",
    user="user",
    password="pass",
    host="localhost",
    port="5432"
)
cursor = con.cursor()

cursor.execute("CREATE TABLE test (id serial PRIMARY KEY, num integer, data varchar);")
"""

@app.get("/getvote")
async def get_vote(topic_id: int):
    db = SessionLocal()
    topic = db.query(VoteTopic).filter_by(id=topic_id).first()
    if not topic:
        raise HTTPException(status_code=404)
    return {"question": topic.content, "options": topic.choices, "active": topic.active}

@app.post("/addvote")
async def add_vote(new_vote: NewVote):
    db = SessionLocal()
    topic = db.query(VoteTopic).filter_by(content=new_vote.content).first()
    if topic:
        raise HTTPException(status_code=400, detail="Vote already exists")
    topic = VoteTopic(content=new_vote.content)
    for c in new_vote.choices:
        topic.choices.append(VoteChoice(content=c))
    db.add(topic)
    db.commit()
    db.close()
    return {"message": "Vote created"}

@app.post("/vote")
async def vote(vote: Vote):
    db = SessionLocal()
    topic = db.query(VoteTopic).filter_by(id=vote.topic_id).first()
    if not topic:
        raise HTTPException(status_code=404)
    if not topic.active:
        raise HTTPException(status_code=400, detail="Voting closed")
    choice = next((c for c in topic.choices if c.content == vote.choice), None)
    if not choice:
        raise HTTPException(status_code=400, detail="Invalid choice")

    choice.votes += 1
    db.commit()
    db.close()
    return {"message": "Vote added"}

@app.get("/status")
async def status(topic_id: int):
    db = SessionLocal()
    topic = db.query(VoteTopic).filter_by(id=topic_id).first()
    if not topic:
        raise HTTPException(status_code=404)
    return {"question": topic.content, "status": topic.active, "choices": [{"id": c.id, "content": c.content, "votes": c.votes} for c in topic.choices], "created_at": topic.created, "end_at": topic.ends}