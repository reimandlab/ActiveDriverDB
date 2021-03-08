#!/bin/bash
set -e

cd static
wget https://raw.githubusercontent.com/reimandlab/needleplot/master/needleplot.js -nc
cd ..

# precomiple nunjucks templates
cd static/js_templates
./precompile.sh
cd ..
printf "\n"

# compile sass into css files
echo 'Compiling sass files'
npx sass --update .:. --no-source-map --error-css

echo 'Adding prefixes'
npx postcss sass/*.css --replace --use autoprefixer --verbose
cd ..

echo 'Done.'
