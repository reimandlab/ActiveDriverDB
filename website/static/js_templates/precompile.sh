#!/bin/bash

# make dir if not exists
mkdir -p precompiled

# protein view templates
nunjucks-precompile macros.njk > precompiled/protein.js
nunjucks-precompile mimp.njk >> precompiled/protein.js
nunjucks-precompile mimp_image.njk >> precompiled/protein.js
nunjucks-precompile needle_tooltip.njk >> precompiled/protein.js
nunjucks-precompile row_details.njk >> precompiled/protein.js

# network view templates
nunjucks-precompile node_tooltip.njk > precompiled/network.js
