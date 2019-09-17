FROM python:3.6

ADD ./ /shrls

RUN pip install -r /shrls/requirements.txt

CMD [ "python", "/shrls/app.py" ]
