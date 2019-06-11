#!/bin/bash
if [ -f annovar.latest.tar.gz ];
then
    tar -xvzf annovar.latest.tar.gz
    rm annovar.latest.tar.gz
else
    if [ ! -d annovar ];
    then
        echo "Please, download annovar into data/mutations directory and then run the script again."
        exit 1
    fi
fi

if [ ! -d humandb ];
then
    ./annovar/annotate_variation.pl -buildver hg19 -downdb -webfrom annovar refGene humandb/
fi
