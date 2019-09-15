#!/usr/bin/env python
from setuptools import setup

setup(
    name = 'shrls',
    version = '0.1.0',
    author = 'Britt Gresham',
    author_email = 'brittcgresham@gmail.com',
    description = ('Short URL Service'),
    license = 'MIT',
    install_requires=[
        'flask',
        'flask-SQLAlchemy',
        'sqlalchemy',
        'oath',
    ],
    entry_points="""\
    [console_scripts]
    initialize_shrls_db = shrls.models:initialize_shrls_db
    """,
)
