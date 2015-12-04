import os
import random
from functools import wraps

from flask import (
    redirect,
    render_template,
    request,
    Response,
    send_from_directory,
)
from werkzeug import secure_filename

from shrls import app
from shrls.models import (
    DBSession,
    Url,
    Snippet,
    allowed_shortner_chars,
)

from sqlalchemy import (
    or_,
    not_,
)


def check_auth(username, password):
    """This function is called to check if a username /
    password combination is valid.
    """
    return all([username == app.config['shrls_username'],
                password == app.config['shrls_password']])


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
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


def not_found():
    if app.config['shrls_redirect_unknown']:
        return redirect(app.config['shrls_redirect_url'], code=302)
    else:
        return Response("File not found", 404)


@app.route('/')
def index():
    return not_found()


@app.route('/code/<url_id>')
@app.route('/c/<url_id>')
def render_code_snippet(url_id):
    redirect_obj = DBSession.query(Snippet).filter(Snippet.alias == url_id).first()
    if redirect_obj:
        redirect_obj.views += 1
        DBSession.add(redirect_obj)
        DBSession.commit()
        return render_template('snippet.html', code=redirect_obj)
    return not_found()


@app.route('/uploads/<path:filename>')
@app.route('/u/<path:filename>')
def return_uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)


@app.route('/<path:url_id>')
def url_redirect(url_id):
    url_id = url_id.split('.')[0]
    redirect_obj = DBSession.query(Url).filter(Url.alias == url_id).all()
    redirect_obj = random.choice(redirect_obj)
    if redirect_obj:
        location = redirect_obj.location
        redirect_obj.views += 1
        DBSession.add(redirect_obj)
        DBSession.commit()
        return redirect(location, code=302)
    return not_found()


@app.route('/admin/')
@requires_auth
def admin_index():
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

    include = request.args.getlist('include')
    exclude = request.args.getlist('exclude')
    searches = request.args.getlist('search')

    t = {
        '+': include,
        '-': exclude,
    }
    searches = [[word for word in x.split(' ') if word] for x in searches if x]
    for search in searches:
        mode = '+'
        phrase = []
        for word in search:
            if word and word[0] in ['-', '+']:
                if phrase:
                    t[mode].append(' '.join(phrase))
                phrase = []
                mode = word[0]
                word = word[1:]
            if word:
                phrase.append(word)
        t[mode].append(' '.join(phrase))

    for f in include:
        urls = urls.filter(or_(
            Url.alias.ilike("%{}%".format(f)),
            Url.location.ilike("%{}%".format(f)),
        ))

    for f in exclude:
        urls = urls.filter(not_(
            or_(
                Url.alias.ilike("%{}%".format(f)),
                Url.location.ilike("%{}%".format(f)),
            )
        ))

    urls = urls.all()

    urlparams = []
    for k, v in request.args.iteritems():
        if k in ['page', 'order_by', 'sort']:
            continue
        urlparams.append("{}={}".format(k, v))
    params = "?{}".format("&".join(urlparams))
    if urlparams:
        params += "&"
    searches = ' '.join([' '.join(x) for x in searches])
    return render_template('admin.html', urls=urls, page=page, count=count, params=params, search=searches)


def create_url(longurl, shorturl=None, creator=None, overwrite=None):
    shrl = Url(longurl)
    if shorturl:
        if overwrite:
            obj = DBSession.query(Url).filter(Url.alias == shorturl).first()
            if obj:
                DBSession.delete(obj)
                DBSession.commit()
        shrl.alias = shorturl
    if creator:
        shrl.alias = "{}/{}".format(creator, shrl.alias)
    DBSession.add(shrl)
    DBSession.commit()
    return '{}/{}'.format(app.config['shrls_base_url'], shrl.alias)


@app.route('/admin/create', methods=['GET'])
@requires_auth
def render_url():
    creator = request.args.get('c')
    longurl = request.args.get('u')
    shortid = request.args.get('s')
    overwrite = request.args.get('o', True)
    url_only = request.args.get('url_only')
    if not(longurl):
        return "prompt('No url specified.')"
    alias = create_url(longurl, shorturl=shortid, creator=creator, overwrite=overwrite)
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
    alias = create_url(alias)
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
    alias = create_url(alias, shorturl=save_as)
    return alias
