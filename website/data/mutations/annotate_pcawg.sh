#!/bin/bash
./ensure_annovar.sh
file=PCAWG_mutations_true.txt.gz
hypermutated=$(zcat "$file" | cut -f 7 | sort | uniq -c | awk '$1 >= 90000')
hypermutated_count=$(wc -l <<< "$hypermutated")
echo "Skipping ${hypermutated_count} hypermutated samples:"
echo "$hypermutated"
query=$(echo "$hypermutated" | awk '{print $2}' | tr '\n' '|' | sed '$s/|$//')
echo "Using negation of query: $query"
zcat $file | grep -v -E "$query" > pcawg_without_hypermutated.txt
echo "Retained $(wc -l pcawg_without_hypermutated.txt) out of $(zcat $file | wc -l) mutations"

echo "Starting annotation:"
./annovar/table_annovar.pl pcawg_without_hypermutated.txt humandb/ -buildver hg19 -out pcawg_annotated -remove -protocol refGene -operation g -nastring . -thread 2 -otherinfo
cat pcawg_annotated.hg19_multianno.txt | gzip > pcawg_muts_annotated.txt.gz
# keep only those which are nonsynonymous SNVs
cat pcawg_annotated.hg19_multianno.txt | awk -F '\t' '$9 ~ /nonsynonymous SNV/' | gzip > pcawg_muts_annotated.txt.gz
