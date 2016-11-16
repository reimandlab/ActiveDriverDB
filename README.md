# Visualisation Framework for Genome Mutations
[![Code Climate](https://codeclimate.com/github/reimandlab/Visualistion-Framework-for-Genome-Mutations/badges/gpa.svg)](https://codeclimate.com/github/reimandlab/Visualistion-Framework-for-Genome-Mutations)

The project aims to create an interactive visualisation framework for genome mutations in gene and protein networks. The idea is to display information from co-developed database in the form of different interactive "views". Thanks to the possibility of quickly switching between the views, the user will be able to grasp an analysed gene or protein with it's context and interactions from different angles. It will also provide advanced filtering and interactive loading with AJAX requests.

# Licence

The application is Open Source and is licensed under the terms of [GNU Lesser General Public License](/reimandlab/Visualistion-Framework-for-Genome-Mutations/blob/master/GNU Lesser General Public License).

# Development

The project is developed with Python 3. It uses Flask as a web framework with database access provided by SQLAlchemy. Templating is performed with Jinja2 on the server side and Nunjucks.js on the client side (they have mostly compatible syntax). On the frontend the styles are written with SASS; the visualizations are jQuery and D3.js based.
All used HTML, CSS and JS features are required to meet 95% level of support in web browsers as calculated by caniuse.com.

## Deployment

The website is developed inside Python3-based virtual environment. To quickly recreate the environment, use:

```bash
virtualenv -p python3 virtual_environment
source virtual_environment/bin/activate
cd website
python3 -m pip install -r requirements.py
```

As currently there is no new version of flask-sqlalchemy released since Oct 2015, but there are some crucial patches merged to the official repository, you will need to clone [flask_sqlalchemy directory](https://github.com/mitsuhiko/flask-sqlalchemy/tree/master/flask_sqlalchemy) into `website` directory.

### Database creation & configuration

For full deployment two MySQL databases will be needed: one for biological data and one for CMS. You need to create them on your own, along with relevant database users and privileges. Afterwards, you can start writing your configuration by copying the exemplar configuration file:
```bash
cp config_example.py config.py
```
Carefully replace variables mentioned in comments in the file as some of those have critical importance on application's security. To check if the database is configured properly, run the following command:
```bash
python3 db_create.py
```
If you see (at the very end): `Done, all tasks completed.` it indicates that everything is working properly.


### Data import

Before server start, data have to be imported. Safest way to do this is to run:
```bash
python3 db_create.py --import_mappings --reload_biological --recreate_cms
```

albeit one might want to use Python's optimized mode (so import will be a lot faster, but it shouldn't be used with new, untested data since the assertions won't be checked in this mode):
```bash
python3 -OO db_create.py --import_mappings --reload_biological --recreate_cms
```

The given arguments instruct program to create and import data for: DNA -> protein mappings, biological relational database and Content Management System. During CMS creation you will be asked to set up login credentials for root user.

**Warning:** after each migration affecting protein's identifiers it is crucial to reimport mappings: otherwise the mappings will point to wrong proteins!

For further details use built-in help option:

```bash
python3 db_create.py -h
```

### Stylesheet creation
Stylesheet files are important part of this visualisation framework. To compile them, you will need to have [`sass` gem installed](http://sass-lang.com/install).
To create all `*.css` files, run following command from `website` directory:

```bash
sass --update .:.
```

### Precompiling Nunjucks templates
Nunjucks templating system is used for clint-side templating. It allows to move some repeatedly performed templating tasks to user's browser, which reduces transfer and speeds-up site loading. It uses jinja-nearly-compatible syntax.
To keep this process efficient, templates should be precompiled. To do so, you will need to get full nunjucks installation, for example with `npm` (you should be able to install `npm` with your system's package manager):
```bash
sudo npm install -g nunjucks
```

Afterwards compile templates with:
```bash
cd website/static/js_templates
./precompile.sh
```
And you are done. When `DEBUG = False`, precompiled templates will be loaded automatically.


### Serving with Werkzeug

To start the webserver simply type:
```bash
python3 run.py
```

For adjusting the port or IP address, check `-h` switch of the `run.py` script
(note: to run on port 80 sudo privileges may be required).

### Serving with Apache2

Deployment on Apache2 server is more powerful alternative to Werkzeug webserver.

As you may want to have a virtual environment for this application, `website/app.wsgi` provides ready-to go activation script to use with Apache2 (assuming that the name of your virtual environment is `virtual_environment`).

Following extract from configuration file might be useful help for writing you own configuration:


```apache
    DocumentRoot /some_path/website

    WSGIDaemonProcess app user=some_username group=some_group threads=2
    WSGIScriptAlias / /some_path/website/app.wsgi

    <Directory /some_path/website>
            WSGIProcessGroup app
            WSGIApplicationGroup %{GLOBAL}
            Order deny,allow
            Allow from all
            Require all granted
    </Directory>

    # Serve static files directly:
    Alias /static/ /some_path/static/

    <Directory /some_path/website/static/*>
        Order allow,deny
        Allow from all
            Require all granted
    </Directory>

    <Location /static>
            SetHandler None
    </Location>
```

Usually you can find approriate configuration files in directories like `/etc/apache2/sites-enabled/` or so.


#### Runing python3 in "optimized" mode

You can modify the default path to python executable used by WSGI by adding a `python_path` argument to `WSGIDaemonProcess` directive. It allows you to use small middleware script turning optimalization mode on. Here is an example script:

```bash
#!/bin/sh
exec python3 -OO "$@"
```


### Using Content Management System

To login to root account (created with `db_create.py` script) visit `/login/` page on your server. It will allow you to create, edit and remove standalone pages.

## Debian-based servers

For proper compilation of some requirements, additional software will be needed on Debian-based servers. The required packages are:
```
build-essential python3 libmysqlclient-dev python3-dev python-dev
```

## Acknowledgments

The project is developed with support from Google Summer Code.
