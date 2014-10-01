import string
import random

from shrls import app

from sqlalchemy import create_engine
from sqlalchemy import Column, Integer, Text, DateTime
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.ext.declarative import declarative_base

allowed_shortner_chars = string.ascii_letters + string.digits

engine = create_engine(
    app.config['SQLALCHEMY_DATABASE_URI'],
    convert_unicode=True
)

DBSession = scoped_session(
    sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine
    )
)

Base = declarative_base()
Base.query = DBSession.query_property()


def create_short_url():
    alias = None
    entries = []
    while not(alias):
        alias = ''.join(
            [random.choice(allowed_shortner_chars) for _ in range(5)]
        )
        entries = DBSession.query(Url).filter(Url.alias == alias).first()
        print entries
        if entries:
            alias = None
    return alias


class Url(Base):
    __tablename__ = 'urls'
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime)
    alias = Column(Text, index=True, unique=True)
    location = Column(Text)
    views = Column(Integer)

    def __init__(self, location, alias=None, views=0):
        if not(alias):
            alias = create_short_url()
        print alias
        self.alias = alias
        self.location = location
        self.views = views


    def __repr__(self):
        return str(self.alias) + ", " + str(self.location) + ", " + str(self.views)


def initialize_shrls_db():
    Base.metadata.create_all(bind=engine)
