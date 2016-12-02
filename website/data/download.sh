# hierarchy tree
wget ftp://ftp.ebi.ac.uk/pub/databases/interpro/ParentChildTreeFile.txt

# entry list (all data)
wget ftp://ftp.ebi.ac.uk/pub/databases/interpro/interpro.xml.gz

# mappings
# ftp://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/idmapping/README
wget ftp://ftp.uniprot.org/pub/databases/uniprot/current_release/knowledgebase/idmapping/by_organism/HUMAN_9606_idmapping_selected.tab.gz

# pathway lists
wget http://biit.cs.ut.ee/gprofiler/gmt/gprofiler_hsapiens.NAME.gmt.zip

#  All below are dropbox-dependent ===

wget https://www.dropbox.com/s/wdxnyvf7lkbihnp/biomart_protein_domains_20072016.txt

echo 'Downloading mutations:'

mkdir -p mutations
cd mutations

wget https://www.dropbox.com/s/b1c4yqgnznsafqv/TCGA_muts_annotated.txt.gz
wget https://www.dropbox.com/s/zodasbvinx339tw/ESP6500_muts_annotated.txt.gz
wget https://www.dropbox.com/s/du2qe1skxwmuep2/clinvar_muts_annotated.txt.gz
wget https://www.dropbox.com/s/fidorbveacpo0yh/G1000.hg19_multianno_nsSNV.tgz

cd ..

echo 'Downloading MIMP logos':
wget https://www.dropbox.com/s/3gjkaim1qs8xc2o/MIMP_logos.zip
unzip MIMP_logos.zip
