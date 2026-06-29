#!/usr/bin/env bash
# This script finds the top-N largest uname directories under /data/ohmywod/report/
# and migrates them using migrate-uname-report.sh.
# Supports a dry-run flag and custom limit.

set -euo pipefail

# Default values
limit=10
dry_run=false

# Helper for script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
MIGRATE_SCRIPT="$SCRIPT_DIR/migrate-uname-report.sh"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    -n|--limit)
      if [ -z "${2:-}" ]; then
        echo "Error: --limit requires a value"
        exit 1
      fi
      limit="$2"
      shift 2
      ;;
    --dry-run|--dryrun)
      dry_run=true
      shift
      ;;
    -h|--help)
      echo "Usage: $0 [--limit <number>] [--dry-run]"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      echo "Usage: $0 [--limit <number>] [--dry-run]"
      exit 1
      ;;
  esac
done

# Validate limit is a positive integer
if [[ ! "$limit" =~ ^[0-9]+$ ]] || [ "$limit" -eq 0 ]; then
  echo "Error: limit must be a positive integer greater than 0"
  exit 1
fi

# Ensure base directory exists
base_dir="/data/ohmywod/report"
if [ ! -d "$base_dir" ]; then
  echo "Error: Base directory $base_dir does not exist."
  exit 1
fi

# Ensure migration script exists and is executable if not running dryrun
if [ "$dry_run" = false ] && [ ! -x "$MIGRATE_SCRIPT" ]; then
  echo "Error: Migration script not found or not executable at $MIGRATE_SCRIPT"
  exit 1
fi

echo "Scanning $base_dir for the top $limit largest directories (excluding symlinks)..."

# Find actual directories (excluding symlinks), sort by human-readable size, and limit results
mapfile -d $'\0' candidates < <(find "$base_dir" -mindepth 1 -maxdepth 1 -type d ! -type l -print0)

if [ ${#candidates[@]} -eq 0 ]; then
  echo "No candidate directories found for migration."
  exit 0
fi

# We run du -sh on the candidates and sort
# We use standard sort -hr to sort human-readable sizes (G > M > K)
# We use head -n "$limit" to get top N
mapfile -t lines < <(du -sh "${candidates[@]}" | sort -hr | head -n "$limit")

if [ ${#lines[@]} -eq 0 ]; then
  echo "No folders found."
  exit 0
fi

# Define tab character for splitting
tab=$'\t'

if [ "$dry_run" = true ]; then
  echo -e "\n--- [DRY RUN] Top $limit Largest User Report Directories ---"
  printf "%-10s %-20s %s\n" "Size" "User (uname)" "Action"
  printf "%-10s %-20s %s\n" "----" "------------" "------"
  for line in "${lines[@]}"; do
    size="${line%%"$tab"*}"
    path="${line#*"$tab"}"
    uname=$(basename "$path")
    printf "%-10s %-20s %s\n" "$size" "$uname" "Would migrate to extra/report"
  done
  echo -e "--------------------------------------------------------\n"
  echo "Dry run complete. No changes were made."
else
  echo -e "\nStarting migration of top $limit directories...\n"
  for line in "${lines[@]}"; do
    size="${line%%"$tab"*}"
    path="${line#*"$tab"}"
    uname=$(basename "$path")
    
    echo ">>> Migrating '$uname' (Size: $size) ..."
    "$MIGRATE_SCRIPT" "$uname"
    echo ">>> Finished '$uname'"
    echo "----------------------------------------"
  done
  echo "All migrations completed!"
fi
