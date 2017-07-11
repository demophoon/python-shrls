#!/usr/bin/env python
# -*- coding: utf-8 -*-

import string
import random
import datetime

from shrls import app

from sqlalchemy import create_engine
from sqlalchemy import Table, Column, Integer, Text, DateTime, ForeignKey
from sqlalchemy.orm import scoped_session, sessionmaker, relationship
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
        if entries:
            alias = None
    return alias


# Tags to Urls Association Table
tags_to_urls_table = Table(
    'tags_to_urls', Base.metadata,
    Column('tag_id', Integer, ForeignKey('tags.id')),
    Column('url_id', Integer, ForeignKey('urls.id')),
)


class Tag(Base):
    __tablename__ = 'tags'
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime)
    name = Column(Text)
    urls = relationship("Url", secondary=tags_to_urls_table, back_populates="tags")

    def __init__(self, name):
        self.name = name
        self.created_at = datetime.datetime.now()

    def __repr__(self):
        return str(self.name)


class Url(Base):
    __tablename__ = 'urls'
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime)
    alias = Column(Text)
    location = Column(Text)
    views = Column(Integer)
    tags = relationship("Tag", secondary=tags_to_urls_table, back_populates="urls")

    def __init__(self, location, alias=None, views=0):
        if not(alias):
            alias = create_short_url()
        self.alias = alias
        self.location = location
        self.views = views
        self.created_at = datetime.datetime.now()

    def __repr__(self):
        return str(self.alias) + ", " + str(self.location) + ", " + str(self.views)


class Snippet(Base):
    __tablename__ = 'snippets'
    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime)
    alias = Column(Text, index=True, unique=True)
    title = Column(Text)
    content = Column(Text)
    views = Column(Integer)

    def __init__(self, content, title=None, alias=None, views=0):
        if not(alias):
            alias = create_short_url()
        self.alias = alias
        self.content = content
        self.title = title
        self.views = views
        self.created_at = datetime.datetime.now()

    def __repr__(self):
        return str(self.alias)


class View(Base):
    __tablename__ = 'views'
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime)
    urls_id = Column(Integer, ForeignKey('urls.id'))
    ip = Column(Text)
    request = Column(Text)
    headers = relationship("Header", back_populates='view')

    def __init__(self, urls_id, ip, request):
        self.timestamp = datetime.datetime.now()
        self.urls_id = urls_id
        self.ip = ip
        self.request = request


class Header(Base):
    __tablename__ = 'headers'
    id = Column(Integer, primary_key=True)
    views_id = Column(Integer, ForeignKey('views.id'))
    key = Column(Text)
    value = Column(Text)
    view = relationship("View", back_populates='headers')

    def __init__(self, key, value):
        self.key = key
        self.value = value


def initialize_shrls_db():
    Base.metadata.create_all(bind=engine)
