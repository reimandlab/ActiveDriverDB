#!/usr/bin/env bash
sudo apt-get install libffi-dev python3-dev build-essential

# Use examplar configuration for the beginning
cd website
mv example_config.py config.py
cd ..

git clone https://github.com/juanmirocks/Levenshtein-MySQL-UDF
cd Levenshtein-MySQL-UDF
gcc -o levenshtein.so -fPIC -shared levenshtein.c -I /usr/include/mysql/
sudo cp levenshtein.so /usr/lib/mysql/plugin/
# for MariaDB use:
# plugin_dir=$(sudo mysql -e 'select @@plugin_dir;' | grep -v '@')
# sudo cp levenshtein.so $plugin_dir
cd ..
rm -rf Levenshtein-MySQL-UDF

# install autoprefixer, clean-css and nunjucks
npm install -g autoprefixer@^9 postcss-cli@^8 postcss@^8 nunjucks sass

# fix nunjucks to add jinja-compat mode for precompile
wget https://github.com/mozilla/nunjucks/commit/5108b8e09dd50638ef01555f8c4d100ea6e7783e.patch
patch node_modules/nunjucks/bin/precompile 5108b8e09dd50638ef01555f8c4d100ea6e7783e.patch
rm 5108b8e09dd50638ef01555f8c4d100ea6e7783e.patch

# to be replaced with 'clean-css clean-css-cli' after a new release of webassets:
# currently integration fails for new versions but the fix seems to be already implemented on master branch
sudo npm install -g clean-css@3.4.24

# install broker for celery
sudo apt-get install rabbitmq-server

# generate keys (for testing only!)
mkdir -p celery
cd celery
ssh-keygen -t rsa -b 4096 -f worker.key -q -N '' -m PEM
yes '' | openssl req -new -key worker.key -out worker.csr
openssl x509 -req -days 1 -in worker.csr -signkey worker.key -out worker.crt
cd ..

# create celery user
sudo groupadd celery
sudo useradd -g celery celery

cp celeryd .autogen_celeryd

sed "s|^CELERY_BIN=.*|CELERY_BIN=\"$(which celery)\"|" .autogen_celeryd -i
sed "s|^CELERYD_CHDIR=.*|CELERYD_CHDIR=\"$(pwd)\/website\"|" .autogen_celeryd -i

echo "Please modify /etc/default/celeryd script to adjust absolute paths to celery executable and website dir"
sudo cp .autogen_celeryd /etc/default/celeryd

mkdir temp -p
cd temp
wget https://raw.githubusercontent.com/celery/celery/3.1/extra/generic-init.d/celeryd
sudo mv celeryd /etc/init.d/celeryd
sudo chmod 755 /etc/init.d/celeryd
sudo chown root:root /etc/init.d/celeryd
cd ..
rm -r temp

sudo apt-get install acl

setfacl -m u:celery:rwx website
setfacl -m u:celery:rwx website/logs
setfacl -m u:celery:rwx website/logs/app.log

setfacl -R -m u:celery:rwx celery
setfacl -R -m u:celery:rwx website/databases

# redis
sudo apt-get install redis-server

# (re) start everything
sudo /etc/init.d/celeryd restart
sudo /etc/init.d/redis-server restart

# install R
sudo apt-get install r-base

# and R building dependencies
sudo apt-get install r-base-dev

sudo R -e 'install.packages("ggiraph")'
sudo R -e 'install.packages("knitr")'
sudo R -e 'install.packages("ggplot2")'
sudo R -e 'install.packages("htmlwidgets")'

# install ActiveDriver and progress bar
# R -e 'install.packages("ActiveDriver")'
sudo R -e 'install.packages("pbmcapply")'

# fetch forked copy of ActiveDriver
cd website
git clone https://github.com/krassowski/ActiveDriver
cd ..


# ActivePathways will hopefully be on cran soon
# git clone https://github.com/reimandlab/activeDriverPW.git
# R -e 'install.packages(c("metap", "data.table"), repos = "http://cran.us.r-project.org")'
# R -e 'install.packages("activeDriverPW", repos=NULL)'

#sudo apt-get install r-bioc-biocgenerics r-bioc-genomicranges r-bioc-biostrings
git clone https://github.com/reimandlab/rmimp.git
cd rmimp
git checkout refactored
cd ..

# NB: GenomicRanges require RCurl and might need:
# sudo apt-get install libcurl4-gnutls-dev
# sudo R -e 'install.packages("RCurl", repos = "http://cran.us.r-project.org")'

sudo R -e 'install.packages("BiocManager")'
sudo R -e 'BiocManager::install(c("S4Vectors", "GenomicRanges", "Biostrings", "BiocGenerics"))'
#sudo R -e 'install.packages("devtools", repos = "http://cran.us.r-project.org")'
#sudo R -e 'devtools::install("rmimp", dependencies = TRUE)'

sudo R -e 'install.packages(c("mclust", "ROCR", "data.table"), repos = "http://cran.us.r-project.org")'
export R_INSTALL_STAGED=false
sudo R -e 'install.packages("rmimp", repos=NULL)'

# sudo apt-get install libcairo2-dev - needed for svglite
sudo R -e 'install.packages(c("ggseqlogo", "ggplot2", "svglite"), repos = "http://cran.us.r-project.org")'

# needed only if using sqlite3 for tests
sudo apt-get install sqlite3 sqlite3-pcre

# pip3 install pygraphviz
# on ubuntu:
# pip3 install pygraphviz --install-option="--include-path=/usr/include/graphviz" --install-option="--library-path=/usr/lib/graphviz/"
# on debian
# sudo apt-get install libcgraph6 graphviz graphviz-dev
sudo pip install git+https://github.com/krassowski/pygraphviz
