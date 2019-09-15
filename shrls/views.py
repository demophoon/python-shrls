#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import random
import json
import datetime
from functools import wraps

from flask import (
    redirect,
    render_template,
    make_response,
    request,
    Response,
    send_from_directory,
    session,
    jsonify,
)
from werkzeug import secure_filename
from oath import GoogleAuthenticator

from shrls import app
from shrls.models import (
    DBSession,
    Url,
    Tag,
    Snippet,
    View,
    Header,
    allowed_shortner_chars,
)

from sqlalchemy import (
    or_,
    not_,
    desc,
)


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    obj = {'login': False}
    authenticated = session.get('login_key')
    for user in app.config.get('shrls_users'):

        if user.get('shrls_totp'):
            a = GoogleAuthenticator(user['shrls_totp'])
            if all([username == user['shrls_username'],
                    password == a.generate()]) or authenticated == app.config.get('login_key'):
                session['login_key'] = app.config.get('login_key')
                obj['login'] = True
                break
        else:
            if all([username == user['shrls_username'],
                    password == user['shrls_password']]):
                obj['login'] = True
                break
    if obj['login']:
        obj['admin'] = user.get('shrls_admin')
    return obj


def authenticate():
    """Sends a 401 response that enables basic auth"""
    return Response(
        'Could not verify your access level for that URL.\n'
        'You have to login with proper credentials', 401,
        {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or 'logout' in request.args:
            return authenticate()
        is_login = check_auth(auth.username, auth.password)
        if is_login['login']:
            session['admin'] = is_login['admin']
        else:
            return authenticate()
        return f(*args, **kwargs)
    return decorated


def not_found():
    if app.config['shrls_redirect_unknown']:
        return redirect(app.config['shrls_redirect_url'], code=302)
    else:
        return Response("File not found", 404)


@app.route('/.well-known/acme-challenge/<path:challenge>')
def letsencrypt_challenge(challenge):
    challenge_path = '.well-known/acme-challenge/{}'.format(challenge)
    return send_from_directory(app.config['UPLOAD_FOLDER'], challenge_path)


@app.route('/')
def index():
    return not_found()


@app.route('/code/<url_id>')
@app.route('/c/<url_id>')
def render_code_snippet(url_id):
    url_parts = url_id.split('.')
    url_id = url_parts[0]
    file_format = None
    if len(url_parts) > 1:
        file_format = url_parts[-1].lower()
    redirect_obj = DBSession.query(Snippet).filter(Snippet.alias == url_id).first()
    if redirect_obj:
        redirect_obj.views += 1
        DBSession.add(redirect_obj)
        DBSession.commit()
        if file_format:
            if file_format in ['txt']:
                response = make_response(redirect_obj.content)
                response.headers['Content-Type'] = 'text/plain; charset=utf-8'
                return response
            elif file_format in ['asc', 'pgp', 'gpg']:
                return render_template('gpg.html', code=redirect_obj)
        else:
            return render_template('snippet.html', code=redirect_obj)
    return not_found()


@app.route('/uploads/<path:filename>')
@app.route('/u/<path:filename>')
def return_uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


def remove_extra_redirects(original_url):
    if not original_url.startswith(app.config['shrls_base_url']):
        return original_url
    url = original_url[(len(app.config['shrls_base_url']) + 1):]
    urls = DBSession.query(Url).filter(Url.alias == url).all()
    if not urls:
        return original_url
    url = random.choice(urls)
    url.views += 1
    DBSession.add(url)
    DBSession.commit()
    return remove_extra_redirects(url.location)


@app.route('/t/<path:tagname>')
def return_tagged_url(tagname):
    tag = DBSession.query(Tag).filter(Tag.name == tagname).first()
    if not tag:
        return not_found()
    urls = tag.urls
    if not urls:
        return not_found()

    url = random.choice(urls)
    location = '{}/{}'.format(app.config['shrls_base_url'], url.alias)
    location = remove_extra_redirects(location)
    return redirect(location, code=302)


def record_view(url):
    view = View(url.id, request.environ['HTTP_X_REAL_IP'], request.url)
    for k, v in request.headers.items():
        view.headers.append(Header(k, v))
    DBSession.add(view)
    DBSession.commit()


@app.route('/<path:url_id>')
def url_redirect(url_id):
    extras = request.url.split('?')[1:]
    base = url_id.split('/')[0]
    filters = url_id.split('/')[1:]
    print "{}: {}".format(request.environ['PATH_INFO'], request.environ['HTTP_X_FORWARDED_FOR'])
    canned_responses = {
    }
    response = canned_responses.get(request.environ['HTTP_X_FORWARDED_FOR'])
    if response:
        return response
    url_id = url_id.split('.')[0]
    query = DBSession.query(Url).filter(Url.alias == url_id)
    if query.count() == 0:
        query = DBSession.query(Url).filter(Url.alias == base)
    if filters and query.count() > 1:
        for f in filters:
            query = query.filter(Url.location.ilike("%{}%".format(f)))
    redirect_obj = query.all()
    if redirect_obj:
        redirect_obj = random.choice(redirect_obj)
        location = redirect_obj.location
        record_view(redirect_obj)

        if extras:
            if not extras[0].startswith('/'):
                location += '/'
            location += extras[0]
        redirect_obj.views += 1
        DBSession.add(redirect_obj)
        DBSession.commit()
        return redirect(location, code=302)
    return not_found()


@app.route('/admin/info/')
@requires_auth
def all_info():
    requests = DBSession.query(View).order_by(View.timestamp.desc()).limit(25).all()

    info_obj = {}
    info_obj['requests'] = [{
        'id': r.id,
        'timestamp': r.timestamp,
        'ip': r.ip,
        'path': r.request,
        'alias': r.url.alias,
        'headers': {header.key: header.value for header in r.headers},
    } for r in requests]
    return jsonify(info_obj)


@app.route('/admin/info/<path:url_id>')
@requires_auth
def url_info(url_id):
    url_id = url_id.split('.')[0]
    info_obj = {}
    urls = DBSession.query(Url).filter(Url.alias == url_id).all()

    info_obj['urls'] = []
    for url in urls:
        info_obj['urls'].append({
            'id': url.id,
            'created_at': url.created_at,
            'alias': url.alias,
            'location': url.location,
            'views': url.views,
            'tags': [t.name for t in url.tags],
            'requests': {r.id: {
                'timestamp': r.timestamp,
                'ip': r.ip,
                'path': r.request,
                'alias': r.url.alias,
                'headers': {header.key: header.value for header in r.headers},
            } for r in url.requests.order_by(desc(View.timestamp)).limit(25)},
        })
    return jsonify(info_obj)


@app.route('/admin/backup/')
@requires_auth
def backup():
    urls = DBSession.query(Url).all()
    snippets = DBSession.query(Snippet).all()
    backup_obj = {
        'urls': [],
        'snippets': [],
    }
    for url in urls:
        obj = {
            'id': url.id,
            'alias': url.alias,
            'location': url.location,
            'views': url.views,
        }
        if url.created_at:
            obj['created_at'] = (url.created_at - datetime.datetime(1970, 1, 1)).total_seconds()
        else:
            obj['created_at'] = 0
        obj['tags'] = [x.name for x in url.tags]
        backup_obj['urls'].append(obj)
    for snippet in snippets:
        obj = {
            'id': snippet.id,
            'alias': snippet.alias,
            'title': snippet.title,
            'content': snippet.content,
            'views': snippet.views,
        }
        if snippet.created_at:
            obj['created_at'] = (snippet.created_at - datetime.datetime(1970, 1, 1)).total_seconds()
        else:
            obj['created_at'] = 0
        backup_obj['snippets'].append(obj)
    return jsonify(backup_obj)


@app.route('/admin/restore/', methods=['POST'])
@requires_auth
def restore():
    payload = request.files['file']
    payload = json.loads(payload.read())
    db_entities = []
    known_tags = {}
    for url in payload['urls']:
        u = Url(url['location'], url['alias'], url['views'])
        for tag in url['tags']:
            if tag not in known_tags:
                known_tags[tag] = Tag(tag)
        url['tags'] = [known_tags[tag] for tag in url['tags']]
        for k, v in url.items():
            setattr(u, k, v)
        u.created_at = datetime.datetime.fromtimestamp(url['created_at'])
        db_entities.append(u)
    for snip in payload['snippets']:
        s = Snippet(snip['content'], snip['title'], snip['alias'], snip['views'])
        for k, v in snip.items():
            setattr(s, k, v)
        s.created_at = datetime.datetime.fromtimestamp(snip['created_at'])
        db_entities.append(s)
    DBSession.add_all(db_entities)
    DBSession.commit()
    return redirect('/admin/', code=302)



@app.route('/admin/api/snippet')
@requires_auth
def get_snippets():
    final = {
    }
    snippets = [DBSession.query(Snippet).first()]
    final['snippets'] = [{
        'id': x.id,
        'created_at': x.created_at,
        'alias': x.alias,
        'title': x.title,
        'content': x.content,
        'views': x.views,
    } for x in snippets]
    return jsonify(final)


@app.route('/admin/api/shrls')
@requires_auth
def get_shrls_api():
    page = int(request.args.get('page', 0))
    count = int(request.args.get('count', 50))
    urls = DBSession.query(Url)

    order_by = request.args.get('order_by')
    sort_by = request.args.get('sort')
    if not order_by or order_by.lower() not in ['id', 'created_at', 'alias', 'views', 'location']:
        order_by = 'created_at'
    if not sort_by or sort_by.lower() not in ['asc', 'desc']:
        sort_by = 'desc'
    order_by = order_by.lower()
    sort_by = sort_by.lower()

    urls = urls.order_by(getattr(getattr(Url, order_by), sort_by)())

    searches = request.args.getlist('search')

    t = {
        '+': [],
        '-': [],
        '#': [],
        '/': [],
    }

    searches = [[word for word in x.split(' ') if word] for x in searches if x]
    for search in searches:
        mode = '+'
        phrase = []
        for word in search:
            if word and word[0] in t.keys():
                if phrase:
                    t[mode].append(' '.join(phrase))
                phrase = []
                mode = word[0]
                word = word[1:]
            if word:
                phrase.append(word)
        t[mode].append(' '.join(phrase))

    for f in t['/']:
        urls = urls.filter(or_(
            Url.alias.ilike("{}%".format(f)),
            Url.location.ilike("%/{}%".format(f)),
        ))

    for f in t['#']:
        urls = urls.filter(
            Url.tags.any(Tag.name.ilike("%{}%".format(f)))
        )

    for f in t['+']:
        urls = urls.filter(or_(
            Url.alias.ilike("%{}%".format(f)),
            Url.location.ilike("%{}%".format(f)),
            Url.tags.any(Tag.name.ilike("%{}%".format(f))),
        ))

    for f in t['-']:
        urls = urls.filter(not_(or_(
            Url.alias.ilike("%{}%".format(f)),
            Url.location.ilike("%{}%".format(f)),
        )))

    urls = urls.offset(page * count)
    urls = urls.limit(count)

    urls = urls.all()
    final = {'urls': [{
        'id': x.id,
        'alias': x.alias,
        'location': x.location,
        'views': x.views,
        'tags': [t.name for t in x.tags],
    } for x in urls]}

    return jsonify(final)


@app.route('/admin/')
@requires_auth
def admin_index():
    return render_template('admin.html')


def create_url(longurl, shorturl=None, creator=None, shrl_id=None, tags=None):
    ftags = []
    if tags:
        for tag in tags:
            tag_obj = DBSession.query(Tag).filter(Tag.name == tag).first()
            if not tag_obj:
                tag_obj = Tag(tag)
                DBSession.add(tag_obj)
            ftags.append(tag_obj)

    shrl = None
    if shrl_id:
        shrl = DBSession.query(Url).filter(Url.id == shrl_id).first()
    if not shrl:
        shrl = Url(longurl)
    if longurl:
        shrl.location = longurl
    if ftags:
        shrl.tags = ftags
    if shorturl:
        shrl.alias = shorturl
    if creator:
        shrl.alias = "{}/{}".format(creator, shrl.alias)
    DBSession.add(shrl)
    DBSession.commit()
    return shrl
    return '{}/{}'.format(app.config['shrls_base_url'], shrl.alias)


@app.route('/admin/api/tags', methods=['GET'])
@requires_auth
def get_tags():
    tags = DBSession.query(Tag).all()
    return jsonify({
        'tags': [x.name for x in tags],
    })


@app.route('/admin/api/shrls', methods=['DELETE'])
@requires_auth
def delete_shrl():
    shrl_id = request.form.get('id')
    obj = DBSession.query(Url).filter(Url.id == int(shrl_id)).first()
    DBSession.delete(obj)
    DBSession.commit()
    return jsonify({
        'status': 'success',
        'id': shrl_id,
    })


@app.route('/admin/api/shrls', methods=['POST'])
@requires_auth
def post_shrl():
    creator = request.form.get('user')
    longurl = request.form.get('location')
    alias = request.form.get('alias')
    shrl_id = request.form.get('id')
    tags = request.form.getlist('tags[]')

    if shrl_id:
        shrl_id = int(shrl_id)

    shrl = create_url(longurl, shorturl=alias, creator=creator, shrl_id=shrl_id, tags=tags)
    alias = u"{}/{}".format(app.config['shrls_base_url'], shrl.alias)
    return jsonify({
        'status': 'success',
        'url': alias,
        'shrl': {
            'id': shrl.id,
            'alias': shrl.alias,
            'location': shrl.location,
            'views': shrl.views,
            'tags': [t.name for t in shrl.tags],
        },
    })



@app.route('/admin/create', methods=['GET'])
@requires_auth
def render_url():
    creator = request.args.get('c')
    longurl = request.args.get('u')
    shortid = request.args.get('s')
    tags = request.args.getlist('t')
    overwrite = str(request.args.get('o', False)).lower() == 'true'
    url_only = request.args.get('url_only')
    if creator:
        tags.append(creator)

    if overwrite and not session['admin']:
        return "prompt('You do not have permission to overwrite existing urls.')"

    if not(longurl):
        return "prompt('No url specified.')"
    shrl = create_url(longurl, shorturl=shortid, creator=creator, tags=tags)
    alias = '{}/{}'.format(app.config['shrls_base_url'], shrl.alias)

    if url_only:
        return alias
    else:
        return "prompt('The url has been shortened', '{}');".format(alias)


@app.route('/admin/snippet', methods=['POST'])
@requires_auth
def create_snippet():
    print request.args
    content = request.form.get('c')
    title = request.form.get('t')
    shortid = request.form.get('s')
    if not content:
        return "Error"
    shrl = Snippet(content, title=title)
    if shortid:
        obj = DBSession.query(Snippet).filter(Snippet.alias == shortid).first()
        if obj:
            DBSession.delete(obj)
            DBSession.commit()
        shrl.alias = shortid
    DBSession.add(shrl)
    DBSession.commit()
    alias = '{}/c/{}'.format(app.config['shrls_base_url'], shrl.alias)
    shrl = create_url(alias)
    alias = '{}/{}'.format(app.config['shrls_base_url'], shrl.alias)
    return alias


@app.route('/admin/upload', methods=['POST'])
@requires_auth
def upload_file():
    f = request.files['file']
    save_as = request.form.get('s')

    name = secure_filename(f.filename)
    extension = name.split('.')[-1]
    if not save_as:
        save_as = ''.join(
            [random.choice(allowed_shortner_chars) for _ in range(5)]
        )
    filename = "{}.{}".format(
        ''.join([x for x in save_as if x in allowed_shortner_chars]),
        extension
    )
    f.save(os.path.join(
        app.config['UPLOAD_FOLDER'],
        filename)
    )
    alias = "{}/u/{}".format(app.config['shrls_base_url'], filename)
    shrl = create_url(alias, shorturl=save_as)
    alias = '{}/{}'.format(app.config['shrls_base_url'], shrl.alias)
    return alias
