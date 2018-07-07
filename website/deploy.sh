#!/bin/bash

cd static
wget -N https://raw.githubusercontent.com/reimandlab/needleplot/master/needleplot.js
cd ..

# precomiple nunjucks templates
cd static/js_templates
./precompile.sh
cd ..

# compile sass into css files
echo 'Compiling sass files:'
sass --update .:.
cd ..

echo 'Done.'
