#!/bin/bash

echo 'Precompiling Nunjucks templates:'

# make dir if does not exist
mkdir -p precompiled

compile () {
    echo "Compiling $1" >&2
    npx nunjucks-precompile -j  $1
}


# protein view templates
compile macros.njk > precompiled/protein.js
compile mimp.njk >> precompiled/protein.js
compile motif_image.njk >> precompiled/protein.js
compile mimp_image.njk >> precompiled/protein.js
compile needle_tooltip.njk >> precompiled/protein.js
compile row_details.njk >> precompiled/protein.js
compile short_url_popup.njk >> precompiled/protein.js
compile kinase_tooltip.njk >> precompiled/protein.js

# network view templates
compile node_tooltip.njk > precompiled/network.js
compile site_mutations_table.njk >> precompiled/network.js
compile short_url_popup.njk >> precompiled/network.js

# pathway view templates
compile pathways_gene_list.njk > precompiled/pathway.js
compile pathway_details.njk >> precompiled/pathway.js

# gene view templates
compile gene_isoforms.njk > precompiled/gene.js

echo 'Nunjucks templates precompiled.'
