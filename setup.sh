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
