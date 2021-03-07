import genomic_mappings
from database import db
from database.migrate import basic_auto_migrate_relational_db, mysql_extract_definitions, mysql_columns_to_update
from database_testing import DatabaseTest
from models import Model, ScalarSet


def test_make_snv_key():
    test_data = (
        # chrom, pos, ref, alt
        (('1', '211', 'A', 'C'), ('1', '211', 'A', 'c')),
        (('X', '2012', 'T', 'G'), ('X', '2012', 't', 'g')),
    )
    for attributes, equivalent_attributes in test_data:
        result_1 = genomic_mappings.make_snv_key(*attributes)
        result_2 = genomic_mappings.make_snv_key(*equivalent_attributes)
        assert result_1 == result_2


def test_encode_csv():
    test_data = (
        # strand, ref, alt, cdna_pos, exon, protein_id, is_ptm
        (('+', 'R', 'H', 204, 'exon1', 123, False), '+RH0cc:exon1:7b'),
        (('-', 'R', 'H', 204, 'exon1', 123, True), '-RH1cc:exon1:7b'),
    )
    for attributes, correct_result in test_data:
        result = genomic_mappings.encode_csv(*attributes)
        assert result == correct_result


def test_decode_csv():
    keys = ('strand', 'ref', 'alt', 'pos', 'cdna_pos', 'exon', 'protein_id', 'is_ptm')
    test_data = (
        ('+RH0cc:exon1:7b', ('+', 'R', 'H', 68, 204, 'exon1', 123, False)),
        ('-RH1cc:exon1:7b', ('-', 'R', 'H', 68, 204, 'exon1', 123, True)),
    )
    for encoded_csv, correct_result in test_data:
        result = genomic_mappings.decode_csv(encoded_csv)
        assert result == dict(zip(keys, correct_result))


MYSQL_DISEASE = """\
CREATE TABLE `disease` (
  `name` varchar(255) NOT NULL,
  `medgen_id` varchar(16) DEFAULT NULL,
  `omim_id` varchar(16) DEFAULT NULL,
  `snomed_ct_id` int DEFAULT NULL,
  `orhpanet_id` varchar(16) DEFAULT NULL,
  `hpo_id` varchar(16) DEFAULT NULL,
  `clinvar_type` enum('TraitChoice','DrugResponse','Finding','PhenotypeInstruction','Disease') DEFAULT NULL,
  `id` int(11) NOT NULL AUTO_INCREMENT,
  PRIMARY KEY (`id`),
  UNIQUE KEY `ix_disease_name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=10284 DEFAULT CHARSET=utf8mb4\
"""


def test_mysql_extract_definitions():
    extracted = mysql_extract_definitions(MYSQL_DISEASE)
    assert 'name' in extracted
    assert 'INTEGER' in extracted['snomed_ct_id']


def test_mysql_columns_to_update():
    # enums in different order and letter case should be treated as identical
    to_update = mysql_columns_to_update(
        old_definitions={
            'clinvar_type': "clinvar_type ENUM('TRAITCHOICE','DRUGRESPONSE','FINDING','PHENOTYPEINSTRUCTION','DISEASE')"
        },
        new_definitions={
            'clinvar_type': "clinvar_type ENUM('DrugResponse','TraitChoice','Finding','Disease','PhenotypeInstruction')"
        }
    )
    assert len(to_update) == 0

    # changed length should be picked up
    to_update = mysql_columns_to_update(
        old_definitions={'omim_id': 'omim_id varchar(16)'},
        new_definitions={'omim_id': 'omim_id varchar(32)'}
    )
    assert len(to_update) == 1


class TestTypes(DatabaseTest):

    def test_scalar_set(self):

        class TestModel(Model):
            properties = db.Column(ScalarSet(separator=','), default=set)
            citations = db.Column(ScalarSet(separator=',', element_type=int), default=set)

        db.create_all()

        a = TestModel(properties={'green', 'durable'}, citations={1, 4})

        db.session.add(a)
        db.session.commit()

        a_loaded = TestModel.query.one()
        assert a_loaded.properties == {'green', 'durable'}
        assert a_loaded.citations == {1, 4}

        # test tracking of mutations
        b = TestModel(properties={'red'})

        db.session.add(b)
        db.session.commit()

        b.properties.add('volatile')

        db.session.commit()

        # test filtering
        b_loaded = TestModel.query.filter(TestModel.properties.contains('red')).one()
        assert b_loaded.properties == {'red', 'volatile'}

        # test load of empty set:
        assert b_loaded.citations == set()

    def test_migrate(self):
        for bind in self.SQLALCHEMY_BINDS.keys():
            basic_auto_migrate_relational_db(self.app, bind)
