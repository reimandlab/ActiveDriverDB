#!/usr/bin/env bash
# Install Berkley DB
wget http://download.oracle.com/berkeley-db/db-6.2.23.NC.tar.gz
tar -xzf db-6.2.23.NC.tar.gz
cd db-6.2.23.NC/build_unix
sudo ../dist/configure
sudo make
sudo make install
cd ../..

# Get recent, patched version of flask-sqlalchemy
cd website
git clone https://github.com/krassowski/flask-sqlalchemy/
mv flask-sqlalchemy/flask_sqlalchemy .
rm -rf flask-sqlalchemy
cd ..

# Use examplar configuration for the beginning
cd website
mv example_config.py config.py
cd ..

# install sass gem
gem install sass

git clone https://github.com/krassowski/Levenshtein-MySQL-UDF
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

echo "Please modify /etc/default/celeryd script to provide absolute paths to celery executable and website dir"
sudo cp celeryd /etc/default/celeryd

mkdir temp -p
cd temp
wget https://raw.githubusercontent.com/celery/celery/3.1/extra/generic-init.d/celeryd
sudo mv celeryd /etc/init.d/celeryd
cd ..
rm -r temp