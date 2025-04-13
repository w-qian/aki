from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, JSON, String

Base = declarative_base()


class State(Base):
    __tablename__ = "State"
    threadId = Column(String, primary_key=True)
    state = Column(JSON, nullable=False)
