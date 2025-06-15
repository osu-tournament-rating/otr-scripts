#!/bin/bash
# === CONFIG ===
user="postgres"
db="postgres"
container="wonderful_rubin"
date=$(date '+%y_%m_%d_%H_%M_%S')
destination="./postgres_${date}.gz"
# === CONFIG ===

# List of tables to include
tables=(
  players
  tournaments
  matches
  games
  game_scores
  player_highest_ranks
)

# Build the --table arguments
table_args=""
for table in "${tables[@]}"; do
  table_args+=" --table=${table}"
done

# Dump
echo "Creating database dump..."

{
  docker exec ${container} pg_dump -s -c --if-exists -U ${user} ${db}
  docker exec ${container} pg_dump -a --disable-triggers ${table_args} -U ${user} ${db}
} | gzip >${destination}

echo "Done. Database dump saved to ${destination}"
