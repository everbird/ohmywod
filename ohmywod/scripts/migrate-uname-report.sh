#!/usr/bin/env bash
# This script migrates a specified uname report directory to /mnt/test001/extra/report/
# and replaces the original directory with a symbolic link.

set -euo pipefail

# Check if uname is provided
if [ -z "${1:-}" ]; then
    echo "Usage: $0 <uname>"
    exit 1
fi

uname="$1"
src_dir="/data/ohmywod/report/$uname"
target_parent="/mnt/test001/extra/report"
target_dir="$target_parent/$uname"

# 1. Validation checks
if [ ! -d "$src_dir" ]; then
    echo "Error: Source directory $src_dir does not exist."
    exit 1
fi

if [ -L "$src_dir" ]; then
    echo "Warning: Source directory $src_dir is already a symbolic link. Skipping migration."
    exit 0
fi

if [ -e "$target_dir" ]; then
    echo "Error: Target path $target_dir already exists. Aborting to avoid overwriting."
    exit 1
fi

# Show folder size before migration
echo "Original directory size:"
du -sh "$src_dir"

# 2. Ensure target parent directory exists
echo "Creating target parent directory $target_parent if it doesn't exist..."
mkdir -p "$target_parent"

# Step 1. Copy directory to target destination (preserving attributes)
echo "Step 1: Copying $src_dir to $target_dir ..."
cp -a "$src_dir" "$target_dir"

# Step 2. Back up original directory (rename)
echo "Step 2: Backing up original directory to $src_dir.bak ..."
mv "$src_dir" "$src_dir.bak"

# Step 3. Create symbolic link pointing to the new target
echo "Step 3: Creating symbolic link from $target_dir to $src_dir ..."
ln -s "$target_dir" "$src_dir"

# Step 4. Remove backup directory
echo "Step 4: Removing backup directory $src_dir.bak ..."
rm -rf "$src_dir.bak"

echo "Migration for user '$uname' completed successfully!"
ls -ld "$src_dir"

echo "Done!"
