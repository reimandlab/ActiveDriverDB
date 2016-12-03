from flask import jsonify
from flask import redirect
from flask import request
from flask import render_template as template
from flask_classful import FlaskView
from flask_classful import route
from database import db
from database import get_or_create
from models import ShortURL
from urllib.parse import unquote


class ShortAddress(FlaskView):

    route_base = '/'

    @route('/s/<shorthand>/')
    def visit_shorthand(self, shorthand):
        short = ShortURL.query.get_or_404(ShortURL.shorthand_to_id(shorthand))
        return redirect(unquote(short.address))

    @route('/get_shorthand/')
    def get_shorthand_for(self):

        address = request.args.get('address')
        if not address:
            return

        short, created = get_or_create(
            ShortURL,
            address=address
        )

        if created:
            db.session.add(short)
            db.session.commit()

        return jsonify(short.shorthand)
