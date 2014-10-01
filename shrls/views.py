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
        return redirect(redirect_obj.location, code=302)
    return redirect("http://www.brittg.com/", code=302)


@app.route('/admin/')
def admin_index():
    urls = DBSession.query(Url).all()
    return render_template('admin.html', urls=urls)


@app.route('/admin/create', methods=['GET'])
def create_url():
    longurl = request.args.get('u')
    print longurl
    if not(longurl):
        return ""

    shrl = Url(longurl)

    DBSession.add(shrl)
    DBSession.commit()

    return shrl.alias
