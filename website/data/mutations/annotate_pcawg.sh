#!/bin/bash
./ensure_annovar.sh
file=mutations_PANCAN_minus_skin_lymph_esophagus_liver.txt

./annovar/table_annovar.pl $file humandb/ -buildver hg19 -out pcawg_annotated -remove -protocol refGene -operation g -nastring . -thread 2 -otherinfo
cat pcawg_annotated.hg19_multianno.txt | gzip > pcawg_muts_annotated.txt.gz
# keep only those which are nonsynonymous SNVs
cat pcawg_annotated.hg19_multianno.txt | awk -F '\t' '$9 ~ /nonsynonymous SNV/' | gzip > pcawg_muts_annotated.txt.gz
