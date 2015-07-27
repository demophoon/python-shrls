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
    if app.config['shrls_redirect_unknown'] == True:
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


@app.route('/<url_id>')
def url_redirect(url_id):
    redirect_obj = DBSession.query(Url).filter(Url.alias == url_id).first()
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
    urls = DBSession.query(Url).order_by(Url.created_at.desc()).all()
    return render_template('admin.html', urls=urls)


@app.route('/admin/create', methods=['GET'])
@requires_auth
def create_url():
    longurl = request.args.get('u')
    shortid = request.args.get('s')
    url_only = request.args.get('url_only')
    if not(longurl):
        return ""
    shrl = Url(longurl)
    if shortid:
        obj = DBSession.query(Url).filter(Url.alias == shortid).first()
        if obj:
            obj.delete()
        shrl.alias = shortid
    DBSession.add(shrl)
    DBSession.commit()
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
            obj.delete()
        shrl.alias = shortid
    DBSession.add(shrl)
    DBSession.commit()
    alias = '{}/c/{}'.format(app.config['shrls_base_url'], shrl.alias)
    return alias


@app.route('/admin/upload', methods=['POST'])
@requires_auth
def upload_file():
    f = request.files['file']
    save_as = request.args.get('s')

    name = secure_filename(f.filename)
    extension = name.split('.')[-1]
    if not save_as:
        save_as = ''.join(
            [random.choice(allowed_shortner_chars) for _ in range(5)]
        )
    filename = "{}.{}".format(save_as, extension)
    f.save(os.path.join(
        app.config['UPLOAD_FOLDER'],
        filename)
    )
    alias = "{}/u/{}".format(app.config['shrls_base_url'], filename)
    return alias
