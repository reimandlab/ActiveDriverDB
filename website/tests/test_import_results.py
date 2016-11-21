""""Tests in this module should be pass after data import and fail before"""
from database import bdb
from database import make_snv_key
from database import decode_csv
from models import Protein


def test_mappings():
    """This is a simple inclusion test for genome -> proteme mutation mappigns.

    Knowing the data, we demand the items from the right side (of test data)
    to be in the results of queries specified on the left side.
    """

    test_data = (
        # (chrom, dna_pos, dna_ref, dna_alt), (name, pos, ref, alt)
        (('chr17', '7572934', 'G', 'A'), ('TP53', 353, 'S', 'L')),
        (('chr17', '19282215', 't', 'a'), ('MAPK7', 1, 'M', 'K')),
        (('chr21', '40547520', 'g', 'a'), ('PSMG1', 283, 'T', 'I')),
        (('chr9', '125616157', 't', 'a'), ('RC3H2', 1064, 'Y' 'F')),
        (('chr11', '120198175', 'g', 'a'), ('TMEM136', 31, 'V', 'M')),
        (('chr10', '81838457', 't', 'a'), ('TMEM254', 1, 'M', 'K')),
        (('chr13', '111267940', 't', 'a'), ('CARKD', 1, 'M', 'K')),
        (('chr6', '30539266', 't', 'a'), ('ABCF1', 1, 'M', 'K')),
        (('chr6', '36765430', 'g', 'a'), ('CPNE5', 140, 'L', 'F')),
        (('chr12', '123464753', 't', 'a'), ('ARL6IP4', 1, 'M', 'K')),
    )

    for genomic_data, protein_data in test_data:

        snv = make_snv_key(*genomic_data)

        items = [
            decode_csv(item)
            for item in bdb[snv]
        ]
        hit = False

        for item in items:
            if (
                Protein.get(item['protein_id']).gene.name == protein_data[0] and
                item['pos'] == protein_data[1] and
                item['ref'] == protein_data[2] and
                item['alt'] == protein_data[3]
            ):
                hit = True

        assert hit
