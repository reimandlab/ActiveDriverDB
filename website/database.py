from flask_sqlalchemy import SQLAlchemy
import bsddb3 as bsddb


db = SQLAlchemy()


class BerkleyHashSet:

    def __init__(self, name):
        # open hash database in read-write mode (create it if does not exists)
        self.db = bsddb.hashopen(name, 'c')

    def __getitem__(self, key):
        key = bytes(key, 'utf-8')
        try:
            # remove zeroth element (empty string). TODO: improve the code
            return list(filter(bool, self.db.get(key).split(b'|')))
        except (KeyError, AttributeError):
            return []

    def __setitem__(self, key, items):
        assert '|' not in items
        key = bytes(key, 'utf-8')
        self.db[key] = b'|'.join(items)


def make_snv_key(chrom, pos, ref, alt):
    return ':'.join((chrom, '%x' % int(pos.lstrip()))) + ref + alt


def decode_csv(value):
    value = value.decode('utf-8')
    strand, ref, alt = value[:3]
    pos, exon, protein_id = value[3:].split(':')
    return dict(zip(
        ('strand', 'ref', 'alt', 'pos', 'exon', 'protein_id'),
        (strand, ref, alt, int(pos, base=16), exon, int(protein_id, base=16))
    ))


def encode_csv(strand, ref, alt, pos, exon, protein_id):
    item = strand + ref + alt + ':'.join((
        '%x' % int(pos), exon, '%x' % protein_id))
    return item


bdb = BerkleyHashSet('databases/berkley_hash.db')
