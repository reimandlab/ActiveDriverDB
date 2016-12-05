#!/bin/bash

# make dir if does not exist
mkdir -p precompiled

# protein view templates
nunjucks-precompile macros.njk > precompiled/protein.js
nunjucks-precompile mimp.njk >> precompiled/protein.js
nunjucks-precompile mimp_image.njk >> precompiled/protein.js
nunjucks-precompile needle_tooltip.njk >> precompiled/protein.js
nunjucks-precompile row_details.njk >> precompiled/protein.js
nunjucks-precompile short_url_popup.njk >> precompiled/protein.js

# network view templates
nunjucks-precompile node_tooltip.njk > precompiled/network.js
nunjucks-precompile short_url_popup.njk >> precompiled/network.js

# pathway view templates
nunjucks-precompile pathways_gene_list.njk > precompiled/pathway.js
nunjucks-precompile pathway_details.njk >> precompiled/pathway.js
