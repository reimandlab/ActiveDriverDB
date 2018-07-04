#!/bin/bash
if [ -f annovar.latest.tar.gz ];
then
    tar -xvzf annovar.latest.tar.gz
    rm annovar.latest.tar.gz
else
    if [ ! -d annovar ];
    then
        echo "Please, download annovar into data/mutations directory and run data/mutations/annotate_mc3.sh script then"
        exit 1
    fi
fi

if [ ! -d humandb ];
then
    ./annovar/annotate_variation.pl -buildver hg19 -downdb -webfrom annovar refGene humandb/
fi

file=mutations_PANCAN_minus_skin_lymph_esophagus_liver.txt

./annovar/table_annovar.pl $file humandb/ -buildver hg19 -out pcawg_annotated -remove -protocol refGene -operation g -nastring . -thread 2 -otherinfo
cat pcawg_annotated.hg19_multianno.txt | gzip > pcawg_muts_annotated.txt.gz
# keep only those which are nonsynonymous SNVs
cat pcawg_annotated.hg19_multianno.txt | awk -F '\t' '$9 ~ /nonsynonymous SNV/' | gzip > pcawg_muts_annotated.txt.gz