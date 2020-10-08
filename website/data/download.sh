#!/usr/bin/env bash
# Please be advised that files downloaded using this script are subject of different licencing policies
# and use of some files may be forbidden for commercial purposes. Authors of some files ask for citation
# if you use their work; some authors ask not to distribute their work directly for download.
#
# Please be advised that all the download links collected here are >not< meant to be used
# for standalone download and distribution of the data files linked.

# It is your responsibility to check authors citation requirements and data usage restrictions
# if you want to use any of the files outside of their original purpose (i.e. incorporation to ActiveDriverDB)

# In effort to acknowledge all authors of the data used in ActiveDriverDB we prepared acknowledgments section on:
# https://activedriverdb.org/publications/


for required_program in 'wget' 'unzip' 'Rscript' 'tar' 'synapse'
do
  hash $required_program 2>/dev/null || {
    echo >&2 "$required_program is required but it is not installed. Aborting."
    exit 1
  }
done

wget https://gist.githubusercontent.com/krassowski/8c9710fa20ac944ec8d47ac4a0ac5b4a/raw/444fcc584bc10b5e504c05a6063a281cee808c9c/ucsc_download.sh
source ucsc_download.sh
# refseq mRNA summaries
get_whole_genome_table refseq_summary.tsv.gz genes refGene hgFixed.refSeqSummary gzip
# some of protein mappings (RefSeq)
get_whole_genome_table refseq_link.tsv.gz genes refGene hgFixed.refLink gzip
rm ucsc_download.sh

# full gene name
wget ftp://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz

## Interpro domains

# fetch domains from Ensembl biomart

domains_query=$(tr '\n' ' ' <<- EOQ
<?xml version="1.0" encoding="UTF-8"?>
  <!DOCTYPE Query>
  <Query  virtualSchemaName = "default" formatter = "TSV" header = "1" uniqueRows = "1" count = "" datasetConfigVersion = "0.6" >

    <Dataset name = "hsapiens_gene_ensembl" interface = "default" >
      <Filter name = "with_refseq_mrna" excluded = "0"/>
      <Attribute name = "ensembl_gene_id" />
      <Attribute name = "ensembl_transcript_id" />
      <Attribute name = "ensembl_peptide_id" />
      <Attribute name = "chromosome_name" />
      <Attribute name = "start_position" />
      <Attribute name = "end_position" />
      <Attribute name = "refseq_mrna" />
      <Attribute name = "interpro" />
      <Attribute name = "interpro_short_description" />
      <Attribute name = "interpro_description" />
      <Attribute name = "interpro_end" />
      <Attribute name = "interpro_start" />
    </Dataset>
  </Query>
EOQ
)
wget -O domains.tsv "http://grch37.ensembl.org/biomart/martservice?query=$domains_query"

# hierarchy tree
wget ftp://ftp.ebi.ac.uk/pub/databases/interpro/ParentChildTreeFile.txt

# entry list (all data)
wget ftp://ftp.ebi.ac.uk/pub/databases/interpro/interpro.xml.gz

# protein mappings (external references)
wget ftp://ftp.ncbi.nlm.nih.gov/refseq/H_sapiens/RefSeqGene/LRG_RefSeqGene
wget ftp://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/idmapping/by_organism/HUMAN_9606_idmapping.dat.gz

# uniprot sequences
wget ftp://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot.fasta.gz
wget ftp://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/complete/uniprot_sprot_varsplic.fasta.gz

# pathway list
wget https://biit.cs.ut.ee/gprofiler/static/gprofiler_hsapiens.name.zip
unzip gprofiler_hsapiens.name.zip
rm gprofiler_hsapiens.name.zip
cat hsapiens.REAC.name.gmt hsapiens.GO:BP.name.gmt > hsapiens.pathways.NAME.gmt
rm hsapiens.*.name.gmt

# gene sets - GSEA, not needed for the DB itself
mkdir -p gene_sets
cd gene_sets
wget http://download.baderlab.org/EM_Genesets/current_release/Human/symbol/DrugTargets/Human_DrugBank_all_symbol.gmt
echo 'Gene sets from MSigDB need to be downloaded directly from: software.broadinstitute.org/gsea/msigdb/'
cd ..

echo 'Downloading DrugBank:'
read -s -p "Enter DrugBank account e-mail: " drugbank_email
read -s -p "Enter DrugBank account password: " drugbank_password
curl -Lfv -o drugbank_all_full_database.xml.zip -u "$drugbank_email:$drugbank_password" https://go.drugbank.com/releases/5-1-7/downloads/all-full-database
unzip drugbank_all_full_database.xml.zip

#  All below are dropbox-dependent ===
wget https://www.dropbox.com/s/pjf7nheutez3w6r/curated_kinase_IDs.txt

echo 'Downloading mutations:'

mkdir -p mutations
cd mutations

#echo "Please, enter your synapse credentials to download MC3 dataset"
#read -p "Login: " synapse_login
#read -s -p "Password: " synapse_password
#synapse login -u $synapse_login -p $synapse_password
#synapse get syn7824274
#echo "MC3 mutations dataset downloaded"

wget https://www.dropbox.com/s/lhou9rnwl6lwuwj/mc3.v0.2.8.PUBLIC.maf.gz
wget https://www.dropbox.com/s/zodasbvinx339tw/ESP6500_muts_annotated.txt.gz
wget ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/vcf_GRCh37/clinvar_20201003.vcf.gz
wget ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/xml/ClinVarFullRelease_2020-10.xml.gz

wget https://www.dropbox.com/s/pm74k3qwxrqmu2q/all_mimp_annotations_p085.rsav

echo 'Extracting MIMP mutations from .rsav file... (it will take a long time)'

Rscript -e 'load("all_mimp_annotations_p085.rsav");write.table(all_mimp_annotations, file="all_mimp_annotations.tsv", row.names=F, quote=F, sep="\t");'
rm all_mimp_annotations_p085.rsav

mkdir -p G1000
cd G1000
wget https://www.dropbox.com/s/fidorbveacpo0yh/G1000.hg19_multianno_nsSNV.tgz

echo 'unpacking...'
tar -xvzf G1000.hg19_multianno_nsSNV.tgz
rm G1000.hg19_multianno_nsSNV.tgz
cd ..

cd ..

mkdir -p MIMP_logos
cd MIMP_logos
echo 'Downloading MIMP logos:'
wget https://www.dropbox.com/s/3gjkaim1qs8xc2o/MIMP_logos.zip
unzip MIMP_logos.zip
rm MIMP_logos.zip

cd ..

mkdir -p ../static/mimp
mv MIMP_logos/logos_newman ../static/mimp/logos

echo "Getting list of words we don't wont to have as autogenerated shorthands:"
wget https://raw.githubusercontent.com/LDNOOBW/List-of-Dirty-Naughty-Obscene-and-Otherwise-Bad-Words/master/en -O bad-words.txt

echo 'Downloading all possible SNVs:'
wget https://www.dropbox.com/s/qtuqvucb8nzim51/ALL_PROTEIN_ANNOT.tgz

echo 'unpacking...'
tar -xvzf ALL_PROTEIN_ANNOT.tgz
rm ALL_PROTEIN_ANNOT.tgz


# remove temporary dir
rm -r tmp

cd mutations
./annotate_mc3.sh

cd ..

wget http://purl.obolibrary.org/obo/mondo.obo
wget https://raw.githubusercontent.com/DiseaseOntology/HumanDiseaseOntology/master/src/ontology/HumanDO.obo
wget https://raw.githubusercontent.com/obophenotype/human-phenotype-ontology/master/hp.obo


wget ftp://ftp.ncbi.nlm.nih.gov/pub/clinvar/gene_condition_source_id

# Broad Firehose - TCGA open access data
mkdir -p firehose
cd firehose
wget http://gdac.broadinstitute.org/runs/code/firehose_get_latest.zip
unzip firehose_get_latest.zip

# antibodies - gene map
./firehose_get -tasks "RPPA_AnnotateWithGene.Level_3" data latest
cd stddata__2016_07_15
antibodies=''
for d in *; do
    if [ -d ${d} ]; then
        f="$d/20160715/gdac.broadinstitute.org_$d.RPPA_AnnotateWithGene.Level_3.2016071500.0.0.tar.gz"
        if [ -f ${f} ]; then
            antibodies+=$(tar --to-stdout --wildcards -xf $f "gdac.broadinstitute.org_$d.RPPA_AnnotateWithGene.Level_3.2016071500.0.0/$d.antibody_annotation.txt" | tail -n +2)
            tar --ignore-failed-read --ignore-command-error -xzf "$f" "gdac.broadinstitute.org_$d.RPPA_AnnotateWithGene.Level_3.2016071500.0.0/$d.rppa.txt"
        fi
    fi
done
cd ..
echo "$antibodies" | sort | uniq > gene_antibody_map.txt

cd ..

# expression
./firehose_get -tasks Merge_rnaseqv2__illuminahiseq_rnaseqv2__unc_edu__Level_3__RSEM_genes_normalized__data.Level_3 data latest



# Conservation track from UCSC
wget -N http://hgdownload.cse.ucsc.edu/goldenpath/hg19/phyloP100way/hg19.100way.phyloP100way.bw
wget -N http://hgdownload.cse.ucsc.edu/goldenPath/hg19/database/refGene.txt.gz

mkdir -p sites
cd sites
# https://data.mendeley.com/datasets/dpkbh2g9hy/1
mkdir -p COVID
cd COVID
echo "attempting to download zip from https://data.mendeley.com/datasets/dpkbh2g9hy/1"
wget https://md-datasets-cache-zipfiles-prod.s3.eu-west-1.amazonaws.com/dpkbh2g9hy-1.zip
unzip dpkbh2g9hy-1.zip
cd ..

mkdir -p UniProt
cd UniProt
wget -O glycosylation_sites.csv "https://sparql.uniprot.org/sparql?query=PREFIX+up%3a%3chttp%3a%2f%2fpurl.uniprot.org%2fcore%2f%3e%0d%0aPREFIX+taxon%3a%3chttp%3a%2f%2fpurl.uniprot.org%2ftaxonomy%2f%3e%0d%0aPREFIX+rdf%3a%3chttp%3a%2f%2fwww.w3.org%2f1999%2f02%2f22-rdf-syntax-ns%23%3e%0d%0aPREFIX+faldo%3a%3chttp%3a%2f%2fbiohackathon.org%2fresource%2ffaldo%23%3e%0d%0aSELECT%0d%0a+++++++(SUBSTR(STR(%3fprotein)%2c+33)+AS+%3fprimary_accession)%0d%0a+++++++(SUBSTR(STR(%3fsequence)%2c+34)+AS+%3fsequence_accession)%0d%0a+++++++(%3fbegin+AS+%3fposition)%0d%0a+++++++%3fdata%0d%0a+++++++(SUBSTR(STR(%3fevidence)%2c+32)+AS+%3feco)%0d%0a+++++++%3fsource%0d%0aWHERE%0d%0a%7b%0d%0a++%3fprotein+a+up%3aProtein+%3b%0d%0a+++++++++up%3aorganism+taxon%3a9606+%3b%0d%0a+++++++++up%3aannotation+%3fannotation+%3b%0d%0a+++++++++rdfs%3alabel+%3fname+.%0d%0a++VALUES+%3fannotationType+%7b%0d%0a+++++++up%3aGlycosylation_Annotation%0d%0a+++++++%23+up%3aModified_Residue_Annotation%0d%0a++%7d%0d%0a++%3fannotation+a+%3fannotationType%3b%0d%0a++++++++++++rdfs%3acomment+%3fdata+%3b%0d%0a++++++++++++up%3arange%2ffaldo%3abegin%0d%0a++++++++++++%5b+faldo%3aposition+%3fbegin+%3b%0d%0a+++++++++++++++++++++++++++++faldo%3areference+%3fsequence+%5d+.%0d%0aOPTIONAL+%7b%0d%0a++++%5b%5d+rdf%3aobject+%3fannotation+%3b%0d%0a++++++++++++++++++up%3aattribution+%3fattribution+.%0d%0a++++++++%3fattribution+up%3aevidence+%3fevidence+.%0d%0a++++++++OPTIONAL+%7b%0d%0a++++++++++++%3fattribution+up%3asource+%3fsource%0d%0a++++++++%7d%0d%0a++++%7d%0d%0a%7d%0d%0a%0d%0a&format=csv"
wget -O other_sites.csv "https://sparql.uniprot.org/sparql?query=PREFIX+xsd%3a+%3chttp%3a%2f%2fwww.w3.org%2f2001%2fXMLSchema%23%3e%0d%0aPREFIX+vg%3a+%3chttp%3a%2f%2fbiohackathon.org%2fresource%2fvg%23%3e%0d%0aPREFIX+uniprotkb%3a+%3chttp%3a%2f%2fpurl.uniprot.org%2funiprot%2f%3e%0d%0aPREFIX+uberon%3a+%3chttp%3a%2f%2fpurl.obolibrary.org%2fobo%2fuo%23%3e%0d%0aPREFIX+sp%3a+%3chttp%3a%2f%2fspinrdf.org%2fsp%23%3e%0d%0aPREFIX+SLM%3a+%3chttps%3a%2f%2fswisslipids.org%2frdf%2f%3e%0d%0aPREFIX+skos%3a+%3chttp%3a%2f%2fwww.w3.org%2f2004%2f02%2fskos%2fcore%23%3e%0d%0aPREFIX+sio%3a+%3chttp%3a%2f%2fsemanticscience.org%2fresource%2f%3e%0d%0aPREFIX+sh%3a+%3chttp%3a%2f%2fwww.w3.org%2fns%2fshacl%23%3e%0d%0aPREFIX+schema%3a+%3chttp%3a%2f%2fschema.org%2f%3e%0d%0aPREFIX+rh%3a+%3chttp%3a%2f%2frdf.rhea-db.org%2f%3e%0d%0aPREFIX+rdfs%3a+%3chttp%3a%2f%2fwww.w3.org%2f2000%2f01%2frdf-schema%23%3e%0d%0aPREFIX+pubmed%3a+%3chttp%3a%2f%2frdf.ncbi.nlm.nih.gov%2fpubmed%2f%3e%0d%0aPREFIX+patent%3a+%3chttp%3a%2f%2fdata.epo.org%2flinked-data%2fdef%2fpatent%2f%3e%0d%0aPREFIX+owl%3a+%3chttp%3a%2f%2fwww.w3.org%2f2002%2f07%2fowl%23%3e%0d%0aPREFIX+orthodbGroup%3a+%3chttp%3a%2f%2fpurl.orthodb.org%2fodbgroup%2f%3e%0d%0aPREFIX+orthodb%3a+%3chttp%3a%2f%2fpurl.orthodb.org%2f%3e%0d%0aPREFIX+orth%3a+%3chttp%3a%2f%2fpurl.org%2fnet%2forth%23%3e%0d%0aPREFIX+np%3a+%3chttp%3a%2f%2fnextprot.org%2frdf%23%3e%0d%0aPREFIX+nextprot%3a+%3chttp%3a%2f%2fnextprot.org%2frdf%2fentry%2f%3e%0d%0aPREFIX+mnx%3a+%3chttps%3a%2f%2frdf.metanetx.org%2fschema%2f%3e%0d%0aPREFIX+mnet%3a+%3chttps%3a%2f%2frdf.metanetx.org%2fmnet%2f%3e%0d%0aPREFIX+mesh%3a+%3chttp%3a%2f%2fid.nlm.nih.gov%2fmesh%2f%3e%0d%0aPREFIX+lscr%3a+%3chttp%3a%2f%2fpurl.org%2flscr%23%3e%0d%0aPREFIX+keywords%3a+%3chttp%3a%2f%2fpurl.uniprot.org%2fkeywords%2f%3e%0d%0aPREFIX+insdc%3a+%3chttp%3a%2f%2fidentifiers.org%2finsdc%2f%3e%0d%0aPREFIX+identifiers%3a+%3chttp%3a%2f%2fidentifiers.org%2f%3e%0d%0aPREFIX+glyconnect%3a+%3chttps%3a%2f%2fpurl.org%2fglyconnect%2f%3e%0d%0aPREFIX+glycan%3a+%3chttp%3a%2f%2fpurl.jp%2fbio%2f12%2fglyco%2fglycan%23%3e%0d%0aPREFIX+genex%3a+%3chttp%3a%2f%2fpurl.org%2fgenex%23%3e%0d%0aPREFIX+foaf%3a+%3chttp%3a%2f%2fxmlns.com%2ffoaf%2f0.1%2f%3e%0d%0aPREFIX+eunisSpecies%3a+%3chttp%3a%2f%2feunis.eea.europa.eu%2frdf%2fspecies-schema.rdf%23%3e%0d%0aPREFIX+ensembltranscript%3a+%3chttp%3a%2f%2frdf.ebi.ac.uk%2fresource%2fensembl.transcript%2f%3e%0d%0aPREFIX+ensemblterms%3a+%3chttp%3a%2f%2frdf.ebi.ac.uk%2fterms%2fensembl%2f%3e%0d%0aPREFIX+ensemblprotein%3a+%3chttp%3a%2f%2frdf.ebi.ac.uk%2fresource%2fensembl.protein%2f%3e%0d%0aPREFIX+ensemblexon%3a+%3chttp%3a%2f%2frdf.ebi.ac.uk%2fresource%2fensembl.exon%2f%3e%0d%0aPREFIX+ensembl%3a+%3chttp%3a%2f%2frdf.ebi.ac.uk%2fresource%2fensembl%2f%3e%0d%0aPREFIX+ec%3a+%3chttp%3a%2f%2fpurl.uniprot.org%2fenzyme%2f%3e%0d%0aPREFIX+dc%3a+%3chttp%3a%2f%2fpurl.org%2fdc%2fterms%2f%3e%0d%0aPREFIX+cco%3a+%3chttp%3a%2f%2frdf.ebi.ac.uk%2fterms%2fchembl%23%3e%0d%0aPREFIX+chebihash%3a+%3chttp%3a%2f%2fpurl.obolibrary.org%2fobo%2fchebi%23%3e%0d%0aPREFIX+CHEBI%3a+%3chttp%3a%2f%2fpurl.obolibrary.org%2fobo%2fCHEBI_%3e%0d%0aPREFIX+bibo%3a+%3chttp%3a%2f%2fpurl.org%2fontology%2fbibo%2f%3e%0d%0aPREFIX+allie%3a+%3chttp%3a%2f%2fallie.dbcls.jp%2f%3e%0d%0aPREFIX+GO%3a+%3chttp%3a%2f%2fpurl.obolibrary.org%2fobo%2fGO_%3e%0d%0aPREFIX+obo%3a+%3chttp%3a%2f%2fpurl.obolibrary.org%2fobo%2f%3e%0d%0aPREFIX+up%3a%3chttp%3a%2f%2fpurl.uniprot.org%2fcore%2f%3e%0d%0aPREFIX+taxon%3a%3chttp%3a%2f%2fpurl.uniprot.org%2ftaxonomy%2f%3e%0d%0aPREFIX+rdf%3a%3chttp%3a%2f%2fwww.w3.org%2f1999%2f02%2f22-rdf-syntax-ns%23%3e%0d%0aPREFIX+faldo%3a%3chttp%3a%2f%2fbiohackathon.org%2fresource%2ffaldo%23%3e%0d%0aSELECT%0d%0a+++++++(SUBSTR(STR(%3fprotein)%2c+33)+AS+%3fprimary_accession)%0d%0a+++++++(SUBSTR(STR(%3fsequence)%2c+34)+AS+%3fsequence_accession)%0d%0a+++++++(%3fbegin+AS+%3fposition)%0d%0a+++++++%3fdata%0d%0a+++++++(SUBSTR(STR(%3fevidence)%2c+32)+AS+%3feco)%0d%0a+++++++%3fsource%0d%0aWHERE%0d%0a%7b%0d%0a++%3fprotein+a+up%3aProtein+%3b%0d%0a+++++++++up%3aorganism+taxon%3a9606+%3b%0d%0a+++++++++up%3aannotation+%3fannotation+%3b%0d%0a+++++++++rdfs%3alabel+%3fname+.%0d%0a++VALUES+%3fannotationType+%7b%0d%0a+++++++up%3aModified_Residue_Annotation%0d%0a++%7d%0d%0a++%3fannotation+a+%3fannotationType%3b%0d%0a++++++++++++rdfs%3acomment+%3fdata+%3b%0d%0a++++++++++++up%3arange%2ffaldo%3abegin%0d%0a++++++++++++%5b+faldo%3aposition+%3fbegin+%3b%0d%0a+++++++++++++++++++++++++++++faldo%3areference+%3fsequence+%5d+.%0d%0aOPTIONAL+%7b%0d%0a++++%5b%5d+rdf%3aobject+%3fannotation+%3b%0d%0a++++++++++++++++++up%3aattribution+%3fattribution+.%0d%0a++++++++%3fattribution+up%3aevidence+%3fevidence+.%0d%0a++++++++OPTIONAL+%7b%0d%0a++++++++++++%3fattribution+up%3asource+%3fsource%0d%0a++++++++%7d%0d%0a++++%7d%0d%0a%7d%0d%0a%0d%0a&format=csv"


cd ..
