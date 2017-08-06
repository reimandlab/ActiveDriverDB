""""This tests should be passed after successful data import and fail before"""
from database import bdb
from genomic_mappings import make_snv_key, decode_csv
import app  # this will take some time (stats initialization)
from models import Protein


def test_mappings():
    """This is a simple inclusion test for genome -> proteme mutation mappigns.

    Knowing the data, we demand the items from the right side (of test data)
    to be in the results of queries specified on the left side.
    """

    test_data = (
        # (chrom, dna_pos, dna_ref, dna_alt), (name, pos, ref, alt)
        (('17', '7572934', 'G', 'A'), ('TP53', 353, 'S', 'L')),
        (('17', '19282215', 't', 'a'), ('MAPK7', 1, 'M', 'K')),
        (('21', '40547520', 'g', 'a'), ('PSMG1', 283, 'T', 'I')),
        (('9', '125616157', 't', 'a'), ('RC3H2', 1064, 'Y', 'F')),
        (('11', '120198175', 'g', 'a'), ('TMEM136', 31, 'V', 'M')),
        (('10', '81838457', 't', 'a'), ('TMEM254', 1, 'M', 'K')),
        (('13', '111267940', 't', 'a'), ('CARKD', 1, 'M', 'K')),
        (('6', '30539266', 't', 'a'), ('ABCF1', 1, 'M', 'K')),
        (('6', '36765430', 'g', 'a'), ('CPNE5', 140, 'L', 'F')),
        (('12', '123464753', 't', 'a'), ('ARL6IP4', 1, 'M', 'K')),
    )

    for genomic_data, protein_data in test_data:

        snv = make_snv_key(*genomic_data)

        items = [
            decode_csv(item)
            for item in bdb[snv]
        ]

        for item in items:
            retrieved_data = (
                Protein.query.get(item['protein_id']).gene.name,
                item['pos'],
                item['ref'],
                item['alt']
            )
            if retrieved_data == protein_data:
                break
        else:
            raise Exception(retrieved_data, protein_data)
