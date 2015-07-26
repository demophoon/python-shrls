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
from shrls.models import DBSession, Url


@app.route('/')
def index():
    return redirect("http://www.brittg.com/", code=302)


@app.route('/uploads/<path:filename>')
@app.route('/u/<path:filename>')
def return_uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
    redirect_obj = DBSession.query(Url).filter(Url.alias == url_id).first()
    if redirect_obj:
        location = redirect_obj.location
        redirect_obj.views += 1
        DBSession.add(redirect_obj)
        DBSession.commit()
        return redirect(location, code=302)
    return redirect("http://www.brittg.com/", code=302)


@app.route('/<url_id>')
def url_redirect(url_id):
    redirect_obj = DBSession.query(Url).filter(Url.alias == url_id).first()
    if redirect_obj:
        location = redirect_obj.location
        redirect_obj.views += 1
        DBSession.add(redirect_obj)
        DBSession.commit()
        return redirect(location, code=302)
    return redirect("http://www.brittg.com/", code=302)


@app.route('/admin/')
def admin_index():
    urls = DBSession.query(Url).all()
    return render_template('admin.html', urls=urls)


@app.route('/admin/create', methods=['GET'])
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
    alias = 'http://brittg.com/{}'.format(shrl.alias)
    if url_only:
        return alias
    else:
        return "prompt('The url has been shortened', '{}');".format(alias)


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
    alias = "http://brittg.com/u/{}".format(filename)
    return alias
