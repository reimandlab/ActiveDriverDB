#!/usr/bin/env bash
set -e

sudo apt-get install libffi-dev build-essential apg mysql-client

# Use examplar configuration for the beginning
cd website

# create example database
SQL_PASS=$(apg -m 128 -n 1 -E "\"'")
mv example_database.sql database.sql
sed "s|user|test_user|" database.sql -i
sed "s|pass|$SQL_PASS|" database.sql -i
sed "s|localhost|%|" database.sql -i
cat database.sql
echo "MySQL user: $MYSQL_USER"
mysql --host 127.0.0.1 --port "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" < database.sql
echo "Database created"
mysql --host 127.0.0.1 --port "$MYSQL_PORT" -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" -e 'SHOW DATABASES;'

mv example_config.py config.py
R_LIBS_SITE=$(Rscript -e 'cat(paste(.libPaths(), collapse=":"))')
echo "R_LIBS_SITE: $R_LIBS_SITE"
sed "s|^R_LIBRARY_PATH = .*|R_LIBRARY_PATH = \"$R_LIBS_SITE\"|" config.py -i
sed "s|user:pass@localhost|test_user:$SQL_PASS@127.0.0.1:$MYSQL_PORT|" config.py -i

RANDOM_KEY=$(apg -m 128 -n 1 -E "\"'")
sed "s|^SECRET_KEY = .*|SECRET_KEY = \"$RANDOM_KEY\"|" config.py -i
cat config.py
cd ..

#git clone https://github.com/juanmirocks/Levenshtein-MySQL-UDF
#cd Levenshtein-MySQL-UDF
#echo `mysql_config --include`
#gcc -o levenshtein.so -fPIC -shared levenshtein.c `mysql_config --include` `mysql_config --include`/server
#sudo cp levenshtein.so `mysql_config --plugindir`
# for MariaDB use:
# plugin_dir=$(sudo mysql -e 'select @@plugin_dir;' | grep -v '@')
# sudo cp levenshtein.so $plugin_dir
#cd ..
#rm -rf Levenshtein-MySQL-UDF

# install autoprefixer, clean-css and nunjucks
npm install -g autoprefixer@^9 postcss-cli@^8 postcss@^8 nunjucks@^3.2 sass

# fix nunjucks to add jinja-compat mode for precompile
wget https://github.com/mozilla/nunjucks/commit/5108b8e09dd50638ef01555f8c4d100ea6e7783e.patch
patch $(npm root -g)/nunjucks/bin/precompile 5108b8e09dd50638ef01555f8c4d100ea6e7783e.patch
rm 5108b8e09dd50638ef01555f8c4d100ea6e7783e.patch

# to be replaced with 'clean-css clean-css-cli' after a new release of webassets:
# currently integration fails for new versions but the fix seems to be already implemented on master branch
sudo npm install -g clean-css@3.4.24

# rabbitmq-server: broker for celery
# keeping it down there as it takes quite some time
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
cat .autogen_celeryd
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
mkdir -p website/logs
setfacl -m u:celery:rwx website/logs
touch website/logs/app.log
setfacl -m u:celery:rwx website/logs/app.log

setfacl -R -m u:celery:rwx celery
mkdir -p website/databases
mkdir website/databases/dna_to_protein
mkdir website/databases/gene_to_isoform
setfacl -R -m u:celery:rwx website/databases

# redis
sudo apt-get install redis-server

# create tables for all databases and files for hash-based (HDB) databases
cd website
./manage.py migrate
cd ..

# (re) start everything
sudo /etc/init.d/celeryd restart
sudo /etc/init.d/redis-server restart

# install ActiveDriver and progress bar
# R -e 'install.packages("ActiveDriver")'

# fetch forked copy of ActiveDriver
cd website
git clone https://github.com/krassowski/ActiveDriver
cd ..

# ActivePathways will hopefully be on cran soon
# git clone https://github.com/reimandlab/activeDriverPW.git
# R -e 'install.packages(c("metap", "data.table"), repos = "http://cran.us.r-project.org")'
# R -e 'install.packages("activeDriverPW", repos=NULL)'

git clone https://github.com/reimandlab/rmimp.git
cd rmimp
git checkout refactored
cd ..

# sudo R -e 'install.packages(c("mclust", "ROCR", "data.table"), repos = "http://cran.us.r-project.org")'
export R_INSTALL_STAGED=false
sudo R -e 'install.packages("rmimp", repos=NULL)'

# sudo apt-get install libcairo2-dev - needed for svglite

# needed only if using sqlite3 for tests
sudo apt-get install sqlite3 sqlite3-pcre

# pip3 install pygraphviz
# on ubuntu:
# pip3 install pygraphviz --install-option="--include-path=/usr/include/graphviz" --install-option="--library-path=/usr/lib/graphviz/"
# on debian
# sudo apt-get install libcgraph6 graphviz graphviz-dev
