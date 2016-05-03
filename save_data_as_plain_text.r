load("ad_muts.rsav")
write.table(ad_muts, "ad_muts.tsv", sep='\t', quote=F, row.names=F)

load("psite_table.rsav")
write.table(psite_table, "psite_table.tsv", sep='\t', quote=F, row.names=F)

# install.packages("seqinr", repos="http://R-Forge.R-project.org")
library(seqinr)
load("longest_isoform_proteins.fa.rsav")
write.fasta(sequences=as.list(longest_isoform_proteins), names=names(longest_isoform_proteins), file.out='longest_isoform_proteins.fa', as.string=T)
