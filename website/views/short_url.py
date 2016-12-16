from flask import jsonify
from flask import redirect
from flask import request
from flask_classful import FlaskView
from flask_classful import route
from database import db
from database import get_or_create
from models import ShortURL
from models import BadWord
from urllib.parse import unquote
from Levenshtein import distance


list_of_profanities = [
    bad_word.word
    for bad_word in BadWord.query.all()
]


def is_word_obscene(word):

    similar_characters = (
        ('0', 'O'),
        ('2', 'Z'),
        ('3', 'E'),
        ('6', 'G'),
        ('9', 'q'),
        ('5', 'S')
    )

    for representation, char in similar_characters:
        word = word.replace(representation, char)

    word = word.lower()

    # for short words (these are valuable!) we want only exact matches
    if len(word) < 6 and word not in list_of_profanities:
        return False

    # for long words we need to be more cautious
    if any(distance(word, profanity) < 3 for profanity in list_of_profanities):
        return True
    else:
        return False


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

        found_tolerable_shorthand = False   # not yet ;)

        while not found_tolerable_shorthand:
            entry, created = get_or_create(
                ShortURL,
                address=address
            )

            if created:
                db.session.add(entry)
                db.session.commit()

            shorthand = entry.shorthand

            if is_word_obscene(shorthand):
                # let's mark this entry as inappropriate
                entry.address = '__excluded__'
                db.session.commit()
            else:
                # that's great, most of entries should be appropriate
                found_tolerable_shorthand = True

        return jsonify(shorthand)
