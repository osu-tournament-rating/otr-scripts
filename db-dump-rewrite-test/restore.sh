#!/bin/bash
# === CONFIG ===
user="postgres"
db="postgres"
container="xenodochial_bhabha"
pg_dump_dir="."
# === CONFIG ===

docker exec -i ${container} dropdb -f --if-exists -U ${user} ${db}
docker exec -i ${container} createdb -U ${user} ${db}
find ${pg_dump_dir} -name "postgres_*.gz" -type f -printf "%T@ %p\n" | sort -nr | head -1 | cut -d' ' -f2- | xargs gunzip -c | docker exec -i ${container} psql -U ${user} -d ${db}

echo "Database restoration completed successfully."
