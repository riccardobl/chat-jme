#!/bin/bash

echo "
{
    \"TRANSLATION_SERVICE\":\"$TRANSLATION_SERVICE\",
    \"INDEX_PATH\":\"$INDEX_PATH/\",
    \"CACHE_PATH\":\"$CACHE_PATH/\",
    \"JME_HUB_URL\":\"$JME_HUB_URL\"
}
" > "$CONFIG_PATH"

echo bash "$1.sh" "$CONFIG_PATH"