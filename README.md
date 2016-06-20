# Visualisation Framework for Genome Mutations
[![Code Climate](https://codeclimate.com/github/reimandlab/Visualistion-Framework-for-Genome-Mutations/badges/gpa.svg)](https://codeclimate.com/github/reimandlab/Visualistion-Framework-for-Genome-Mutations) [![Test Coverage](https://codeclimate.com/github/reimandlab/Visualistion-Framework-for-Genome-Mutations/badges/coverage.svg)](https://codeclimate.com/github/reimandlab/Visualistion-Framework-for-Genome-Mutations/coverage)

The project aims to create an interactive visualisation framework for genome mutations in gene and protein networks. The idea is to display information from co-developed database in the form of different interactive "views". Thanks to the possibility of quickly switching between the views, the user will be able to grasp an analysed gene or protein with it's context and interactions from different angles. It will also provide advanced filtering and interactive loading with AJAX requests. 

# Licence

The application is Open Source and is licensed under the terms of [GNU Lesser General Public License](/reimandlab/Visualistion-Framework-for-Genome-Mutations/blob/master/GNU Lesser General Public License).

# Development

The project is developed with Python 3. It uses Flask as a web framework with database access provided by SQLAlchemy. On the frontend the styles are written with SASS; the visualizations are jQuery and D3.js based.
All used HTML, CSS and JS features are required to meet 95% level of support in web browsers as calculated by caniuse.com.

## Deployment

The website is developed inside Python3-based virtual environment. To quickly recreate the environment, use:

```bash
virtualenv -p python3 website_env
source website_env/bin/activate
cd website
python3 -m pip install -r requirements.py
```


To start the webserver simply type:
```bash
python3 run.py
```

For adjusting the port or IP address, check `-h` switch of the `run.py` script.

## Debian-based servers

For proper compilation of some requirements additional software will be needed on Debian-based servers. The required packages are:
```
build-essential python3 libmysqlclient-dev python3-dev python-dev
```

## Acknowledgments

The project is developed with support from Google Summer Code.
