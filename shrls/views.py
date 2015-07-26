from flask import redirect, render_template, request

from shrls import app
from shrls.models import DBSession, Url


@app.route('/')
def index():
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

    return shrl.alias
