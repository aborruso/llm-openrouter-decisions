#!/usr/bin/env bash
# 500 random English articles from 2024 with "transparency" in the title.
# The fixed seed makes the sample reproducible. Needs OPENALEX_API_KEY.
set -euo pipefail
out="$(dirname "$0")/publications.csv"
echo 'title,doi' > "$out"
for page in 1 2 3; do
  curl -sS --get 'https://api.openalex.org/works' --data-urlencode 'filter=title.search:transparency,publication_year:2024,type:article,language:en' --data-urlencode 'sample=500' --data-urlencode 'seed=42' --data-urlencode 'per-page=200' --data-urlencode "page=$page" --data-urlencode 'select=display_name,doi' --data-urlencode "api_key=$OPENALEX_API_KEY" | jq -r '.results[] | [.display_name, (.doi // "")] | @csv'
done | head -n 500 >> "$out"
