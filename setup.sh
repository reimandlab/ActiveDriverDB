#!/usr/bin/env bash
# Install Berkley DB
mkdir downloads
cd downloads
wget -N http://download.oracle.com/berkeley-db/db-6.2.23.NC.tar.gz -O db.NC.tar.gz
tar -xzf db.NC.tar.gz
cd db-6.2.23.NC/build_unix
sudo ../dist/configure
sudo make
sudo make install
cd ..
cd ../..

export BERKELEYDB_DIR=/usr/local/BerkeleyDB.6.2
export LD_LIBRARY_PATH=/usr/local/BerkeleyDB.6.2/lib:$LD_LIBRARY_PATH
sudo pip3 install bsddb3 --berkeley-db=/usr/local/BerkeleyDB.6.2/include

# Use examplar configuration for the beginning
cd website
mv example_config.py config.py
cd ..

# install sass gem
gem install sass

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
sudo npm install -g autoprefixer postcss-cli nunjucks

# to be replaced with 'clean-css clean-css-cli' after a new release of webassets:
# currently integration fails for new versions but the fix seems to be already implemented on master branch
sudo npm install -g clean-css@3.4.24

# install broker for celery (note: command is Debian/Ubuntu specific)
sudo apt-get install rabbitmq-server

# generate keys (for testing only!)
mkdir -p celery
cd celery
ssh-keygen -t rsa -f worker.key -N 'Password for testing only'
cd ..

# create celery user
sudo groupadd celery
sudo useradd -g celery celery

cp celeryd .autogen_celeryd

sed "s|^CELERY_BIN=.*|CELERY_BIN=\"$(whereis celery | cut -f 2 -d ' ')\"|" .autogen_celeryd
sed "s|^CELERYD_CHDIR=.*|CELERYD_CHDIR=\"$(pwd)\/website\"|" .autogen_celeryd

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

setfacl -m u:celery:rwx website/databases
setfacl -m u:celery:rwx website/databases/berkley_hash_refseq.db
setfacl -m u:celery:rwx website/databases/berkley_hash.db

# redis
sudo apt-get install redis-server

# (re) start everything
sudo /etc/init.d/celeryd restart
sudo /etc/init.d/redis-server restart

# install R
sudo apt-get install r-base

# install ActiveDriver and progress bar
# R -e 'install.packages(c("ActiveDriver", "pbmcapply"))'

# fetch forked copy of ActiveDriver
cd website
git clone https://github.com/krassowski/ActiveDriver
cd ..


# ActivePathways are in private repository
# git clone https://github.com/reimandlab/activeDriverPW.git
# R -e 'install.packages(c("metap", "data.table"), repos = "http://cran.us.r-project.org")'
# R -e 'install.packages("activeDriverPW", repos=NULL)'

sudo apt-get install r-bioc-biocgenerics r-bioc-genomicranges r-bioc-biostrings
git clone https://github.com/reimandlab/rmimp.git
R -e 'install.packages(c("mclust", "ROCR"), repos = "http://cran.us.r-project.org")'
R -e 'install.packages("rmimp", repos=NULL)'

# needed only if using sqlite3 for tests
sudo apt-get install sqlite3-pcre
