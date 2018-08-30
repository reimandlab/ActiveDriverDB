# ActiveDriverDB

[![Build Status](https://travis-ci.org/reimandlab/ActiveDriverDB.svg?branch=master)](https://travis-ci.org/reimandlab/ActiveDriverDB) [![Code Climate](https://codeclimate.com/github/reimandlab/Visualistion-Framework-for-Genome-Mutations/badges/gpa.svg)](https://codeclimate.com/github/reimandlab/Visualistion-Framework-for-Genome-Mutations) [![Coverage Status](https://coveralls.io/repos/github/reimandlab/ActiveDriverDB/badge.svg?branch=master)](https://coveralls.io/github/reimandlab/ActiveDriverDB?branch=master)

The project aims to create an interactive visualisation framework for genome mutations in gene and protein networks. The idea is to display information from co-developed database in the form of different interactive "views". Thanks to the possibility of quickly switching between the views, the user will be able to grasp an analysed gene or protein with it's context and interactions from different angles. It will also provide advanced filtering and interactive loading with AJAX requests.

The needleplot visualisation is now available in a separate repository: [reimandlab/needleplot](https://github.com/reimandlab/needleplot).

# Licence

The application is Open Source and is licensed under the terms of [GNU Lesser General Public License](https://github.com/reimandlab/ActiveDriverDB/blob/master/LICENSE).

# Development

The project is developed with Python 3. It uses Flask as a web framework with database access provided by SQLAlchemy. Templating is performed with Jinja2 on the server side and Nunjucks.js on the client side (they have mostly compatible syntax). On the frontend the styles are written with SASS; the visualizations are jQuery and D3.js based.
All used HTML, CSS and JS features are required to meet 95% level of support in web browsers as calculated by caniuse.com.

## Deployment

The website is developed inside Python3-based virtual environment. To quickly recreate the environment, use:

```bash
virtualenv -p python3 virtual_environment
source virtual_environment/bin/activate
cd website
python3 -m pip install -r requirements.txt
```
In case of problems with the execution of commands above on Debian/Ubuntu running machines, look at the bottom of this page where alternative instructions are given. An additional requirement is `bsddb3` package, which is often easier to install system-wide with your package manager (on Debian named `python3-bsddb3`). You may need to add a symbolic link to the package inside of your virtual environment.

### Backend

#### Prerequisites

To create a basic local copy of ActiveDriverDB you need a machine with at least 4 GB of RAM memory.
If you wish to import genomic mappings for genome variants annotation you will more than 10 GB of RAM (recommended 16 GB).

#### Database creation & configuration

For full deployment two MySQL databases will be needed: one for biological data and one for CMS.

You need to create them, along with relevant database users and privileges. This can be achieved with query like:

```sql
CREATE DATABASE db_bio;
CREATE DATABASE db_cms;
CREATE USER 'user'@'localhost' IDENTIFIED BY 'pass';
GRANT ALL PRIVILEGES ON db_bio.* TO 'user'@'localhost';
GRANT ALL PRIVILEGES ON db_cms.* TO 'user'@'localhost';
GRANT INSERT, DELETE, CREATE ROUTINE, ALTER ROUTINE, EXECUTE ON mysql.* TO 'user'@'localhost';
```
Remember to set secure password; user, database and host names are adjustable too.
You may wish to create two separate users for each of databases, this case is supported too.
Privileges on mysql database are required to allow to create functions.


Afterwards, you can start writing your configuration by copying the exemplar configuration file:
```bash
cp example_config.py config.py
```
Carefully replace variables mentioned in comments in the file as some of those have critical importance on application's security. To check if the database is configured properly, run the following command:
```bash
./manage.py
```
If you see (at the very end): `Scripts loaded successfuly, no tasks specified.` it indicates that everything is working properly.


#### Data import

All data files can be downloaded easily with `./download.sh` script from `website/data` directory.

Before server start, data have to be imported. Safest way to do this is to run:
```bash
./manage.py load all
```

albeit one might want to use Python's optimized mode (so import will be a lot faster, but it shouldn't be used with new, untested data since the assertions won't be checked in this mode):
```bash
python3 -OO manage.py load all
```

The given arguments instruct program to create and import data for: DNA -> protein mappings, biological relational database and Content Management System. During CMS creation you will be asked to set up login credentials for root user.

**Warning:** after each migration affecting protein's identifiers it is crucial to reimport mappings: otherwise the mappings will point to wrong proteins!

With `manage.py` script you can load or remove specific parts of the database and perform very simple automigration (for newly created models). For further details use built-in help option:

```bash
./manage.py -h
```

Note that the helps will adapt to specified subcommands (i.e. it will show more details for: `./manage.py load -h`, and even more for: `./manage.py load mutations -h`)

**MySQL specific:** if you see a message `MySQL server has gone away`, try to `set global max_allowed_packet=1073741824;`

### Frontend
If you don't want to perform steps specified below for every single deployment, you can use `deploy.sh` script (after installing all dependencies listed in the steps below).


#### Stylesheet creation
Stylesheet files are important part of this visualisation framework. To compile them, you will need to have [`sass` gem installed](http://sass-lang.com/install).
To create all `*.css` files, run following command from `website` directory:

```bash
sass --update .:.
```

#### Precompiling Nunjucks templates
Nunjucks templating system is used for client-side templating. It allows to move some repeatedly performed templating tasks to user's browser, which reduces transfer and speeds-up site loading. It uses jinja-nearly-compatible syntax.
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

### Task distribution


#### Cyclic, maintenance tasks

For cyclic tasks a CRON-like package [Advanced Python Scheduler](https://apscheduler.readthedocs.io/en/latest/) is used;
it is fully integrated with application code and no additional setup is required.

The jobs functions are defined in `jobs.py` file and scheduling information is stored in `config.py`, in `JOBS` variable.

#### User jobs

To manage and execute user provided mutation search [Celery Distributed Task Queue](http://docs.celeryproject.org/en/latest/index.html) is used,
with the broker and backend being RabbitMQ.
Both RabitMQ and Celery need to be run as services and set up properly, as described in [Celery](http://docs.celeryproject.org/en/latest/getting-started/brokers/rabbitmq.html#broker-rabbitmq).
On Debian-based machines RabitMQ may be installed as a service directly from repositories.

To run celery worker as a script please use the following command:

```
celery -A celery_worker.celery worker
```

For deployment it should be started as a service.
A major part of configuration will be performed by `setup.sh` automatically but one need to amend configuration file (`celeryd`) so all paths are absolute and correct.
To start the service use `init.d` script:

```
/etc/init.d/celeryd {start|stop|restart|status}
```

### Serving

#### Serving with Werkzeug

To start the webserver simply type:
```bash
./run.py
```

For adjusting the port or IP address, check `-h` switch of the `run.py` script
(note: to run on port 80 sudo privileges may be required).

#### Serving with Apache2

Deployment on Apache2 server is more powerful alternative to Werkzeug webserver.

As you may want to have a virtual environment for this application, `website/app.wsgi` provides ready-to go activation script to use with Apache2 (assuming that the name of your virtual environment is `virtual_environment`). `mod_wsgi` extension is required (`apt-get install libapache2-mod-wsgi-py3` for Debian/Ubuntu).

Following extract from configuration file might be useful help for writing you own configuration:


```apache
DocumentRoot /some_path/website

# Prevent 'Timeout when reading response headers from daemon process'
WSGIApplicationGroup %{GLOBAL}

WSGIDaemonProcess app user=some_username group=some_group threads=2
WSGIScriptAlias / /some_path/website/app.wsgi

<Directory /some_path/website>
    WSGIProcessGroup app
    WSGIApplicationGroup %{GLOBAL}
    # Order deny,allow   # do not use with Apache 2.4 or newer
    # Allow from all     # do not use with Apache 2.4 or newer
    Require all denied   # Apache 2.4 or newer
</Directory>

# Serve static files directly:
Alias /static/ /some_path/static/

<Directory /some_path/website/static/*>
    # Order deny,allow   # do not use with Apache 2.4 or newer
    # Allow from all     # do not use with Apache 2.4 or newer
    Require all granted  # Apache 2.4 or newer
</Directory>

<Location /static>
    SetHandler None
</Location>
```

Usually you can find appropriate configuration files in directories like `/etc/apache2/sites-enabled/` or so.


##### Hard maintenance mode with Apache

Apart from the soft (software, CMS-controlled) maintenance mode, an additional maintenance mode for more advanced works is available.

To set it up, add following code to the Apache configuration:


```apache
# Handle maintenance mode:

Alias /maintenance/ /some_path/website/static/maintenance.html

RewriteEngine On
RewriteCond %{DOCUMENT_ROOT}/maintenance-mode-on -f
RewriteCond %{REQUEST_URI} !^/static.*
RewriteCond %{REQUEST_URI} !^/maintenance
RewriteRule ^(.*) /maintenance/ [R=503,L]
ErrorDocument 503 /maintenance/

RewriteCond %{DOCUMENT_ROOT}/maintenance-mode-off -f
RewriteCond %{REQUEST_URI} ^/maintenance
RewriteRule ^(.*) / [R,L]
```

and enable rewrite engine:

```bash
sudo a2enmod rewrite
```

Then, to enable the maintenance mode from within _website_ directory use:

```bash
mv maintenance-mode-off maintenance-mode-on
```

and to disable:

```bash
mv maintenance-mode-on maintenance-mode-off
```


#### Runing python3 in "optimized" mode

You can modify the default path to python executable used by WSGI by adding a `python_path` argument to `WSGIDaemonProcess` directive. It allows you to use small middleware script turning optimalization mode on. Here is an example script:

```bash
#!/bin/sh
exec python3 -OO "$@"
```


### Using Content Management System

To login to root account (created with `manage.py` script) visit `/login/` page on your server. It will allow you to create, edit and remove standalone pages.

## Debian-based servers

For proper compilation of some requirements, additional software will be needed on Debian-based servers. The required packages are:
```
build-essential python3 libmysqlclient-dev python3-dev git python3-bsddb3 pigz nodejs openjdk-7-jdk
```

Alternative commands to create virtual environment (workaround for Debian not having some essential python3 packages installed):
```bash
python3 -m venv --without-pip virtual_environment
source virtual_environment/bin/activate
curl https://bootstrap.pypa.io/get-pip.py | python3
deactivate
source virtual_environment/bin/activate
cd website
python3 -m pip install -r requirements.txt
```

## Tests

All tests are placed in [website/tests](/website/tests) directory. Please find all steps explained in `readme.md` file inside this subdirectory.

Browser compatibility testing is provided by [BrowserStack](https://www.browserstack.com) which allows cloud testing on desktop browsers, real iOS and Android devices. It also allows automate testing integration.

## Acknowledgments

The project is developed with support from [Ontario Institute of Cancer Research](https://oicr.on.ca/) and received support from [Google Summer of Code 2016](https://developers.google.com/open-source/gsoc/).

[<img src="https://cdn.rawgit.com/reimandlab/ActiveDriverDB/master/thirdparty/images/browserstack.svg" height="30px" valign="bottom">](https://www.browserstack.com)


BrowserStack supports this open source project allowing us to use their testing systems for free.
