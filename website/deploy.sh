#!/bin/bash

# precomiple nunjucks templates
cd static/js_templates
./precompile.sh
cd ..

# compile sass into css files
echo 'Compiling sass files:'
sass --update .:.
cd ..

echo 'Done.'
