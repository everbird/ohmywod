#!/usr/bin/env bash
set -euo pipefail

path="$1"
upath=$(dirname "$path")
rname=$(basename "$path")
uname=$(basename $(dirname "$path"))

du -sh "$path"

# Step 1. Copy to jfs
echo "Step 1: Copying $path to jfs ..."
cp -r /data/ohmywod/report/"$uname"/"$rname" /mnt/jfs/reports/

# Step 2. Sync to s3
echo "Step 2: Syncing to s3 ..."
/usr/local/bin/juicefs sync /mnt/jfs/reports 's3://AKIASBWFRLK3W4KELEPN:8IPgMnGBOR6gd5JmgYwxCzD%2FIvkaDb+8Cjp71Sva@ohmywod-reports-devel.s3.ap-northeast-1.amazonaws.com/rstore/reports'

# Step 3. Back up report
echo "Step 3. Back up report ..."
mv "$path" "$path.bak"

# Step 4. Replace with soft link
echo "Step 4. Replace with soft link ..."
ln -s /mnt/jfs/reports/"$rname" "$path"

# Step 5. Remove backup
echo "Step 5. Remove backup ..."
rm -rf "$path.bak"

echo "Migrated successfully!"
ls -lh "$upath"

echo "Done!"