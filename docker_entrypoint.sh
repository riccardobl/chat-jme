#!/bin/bash
eval "$($CONDA_DIR/bin/conda shell.bash hook)"
conda init bash 
conda activate jmebot
echo "{
    \"TRANSLATION_SERVICE\":\"$TRANSLATION_SERVICE\",
    \"INDEX_PATH\":\"$INDEX_PATH\",
    \"CACHE_PATH\":\"$CACHE_PATH\",
    \"JME_HUB_URL\":\"$JME_HUB_URL\",
    \"JME_HUB_KNOWLEDGE_CUTOFF\":\"$JME_HUB_KNOWLEDGE_CUTOFF\",
    \"JME_HUB_SEARCH_FILTER\":\"$JME_HUB_SEARCH_FILTER\",
    \"DEVICE\":\"$DEVICE\",
    \"USE_SUMY\":$USE_SUMY,
    \"SMART_CACHE\":[
        [30,70],
        [50,50],
        [300,30],
        [400,20],
        [0,17]
    ],
    \"OPENAI_MODEL\":\"$OPENAI_MODEL\"
}" > "$CONFIG_PATH"

bash "$1.sh" "$CONFIG_PATH"