#!/bin/bash
./ensure_annovar.sh
file=clinvar_20201003.vcf.gz
gunzip ${file} -c > clinvar.avinput

./annovar/table_annovar.pl clinvar.avinput humandb/ -buildver hg19 -out clinvar_annotated -remove -protocol refGene -operation g -nastring . -thread 2 -otherinfo -vcfinput

# also see http://annovar.openbioinformatics.org/en/latest/articles/VCF/

cat clinvar_annotated.hg19_multianno.txt | awk -F '\t' "BEGIN{print \"$(head clinvar_annotated.hg19_multianno.txt -n 1)\";};\$9 ~ /nonsynonymous SNV/" | gzip > clinvar_muts_annotated.txt.gz
