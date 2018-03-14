from tempfile import TemporaryDirectory

from analyses.mimp import (
    gather_negative_sites, sample_random_negative_sequences, NegativeSite,
    calculate_background_frequency,
    train_model,
)
from database import db
from database_testing import DatabaseTest
from models import Protein, Site, Gene, Kinase, SiteType


class MIMPTest(DatabaseTest):

    def test_gather_negative_sites(self):

        p = Protein(refseq='NM_007', sequence='X---------X------------YXY--------')
        g = Gene(isoforms=[p], preferred_isoform=p)

        # one-based
        s = Site(position=11, type={'methylation'}, residue='X', protein=p)

        db.session.add_all([g, p, s])

        negative_sites = gather_negative_sites(residues={'X'}, exclude={s})

        # zero-based
        assert negative_sites == {
            NegativeSite(p, 0),
            NegativeSite(p, 24)
        }

    def test_sample_negatives(self):

        p = Protein(refseq='NM_007', sequence='X---------X------------YXY--------')

        negative_sites = {
            NegativeSite(p, 0),
            NegativeSite(p, 24)
        }

        sequences = sample_random_negative_sequences(negative_sites, n=2)
        assert set(sequences) == {'-------X-------', '------YXY------'}

        sequences = sample_random_negative_sequences(negative_sites, n=1)
        assert sequences == ['------YXY------'] or sequences == ['-------X-------']

    def test_background_frequency(self):

        for i, sequence in enumerate(['ABBBC', 'ADDEE']):
            p = Protein(refseq=f'NM_{i}', sequence=sequence)
            g = Gene(isoforms=[p], preferred_isoform=p)
            db.session.add(g)

        frequency = calculate_background_frequency()
        assert frequency == {
            'A': 1 / 10 + 1 / 10,
            'B': 3 / 10,
            'C': 1 / 10,
            'D': 2 / 10,
            'E': 2 / 10
        }

    def test_train_model(self):

        phosphorylation = SiteType(name='phosphorylation')

        # non-phosphorylated serine residues are needed to generate negative sites
        p = Protein(refseq='NM_007', sequence='--------SLPA-----------SVIT-------')
        g = Gene(isoforms=[p], preferred_isoform=p)
        db.session.add(g)

        # phosphorylated, with sites
        p = Protein(refseq='NM_001', sequence='--------SPAK-----------SPAR-------')
        g = Gene(isoforms=[p], preferred_isoform=p)
        db.session.add(g)

        k = Kinase(name='CDK1', is_involved_in={phosphorylation})

        for pos in [9, 24]:
            s = Site(position=pos, type={phosphorylation}, residue='S', protein=p, kinases={k})
            db.session.add(s)

        db.session.commit()

        with TemporaryDirectory() as temp_dir:
            model = train_model(
                phosphorylation,
                sequences_dir=temp_dir,
                sampling_n=2,
                threshold=2
            )

        # the model should have one set of params - for CDK1 kinase
        assert len(model) == 1

        cdk_params = model.rx2('CDK1')
        pwm = cdk_params.rx2('pwm')

        # and the position-specific weight matrix should be created
        assert pwm

        # the very detailed testing should be performed by rMIMP,
        # but why not test the basics?

        weights_of_central_aa = {
            aa: value
            for aa, value in zip(pwm.rownames, pwm.rx(True, 8))
        }
        assert weights_of_central_aa['S'] == max(weights_of_central_aa.values())
