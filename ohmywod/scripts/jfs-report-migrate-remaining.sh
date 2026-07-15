#!/usr/bin/env bash
# 步骤 2+3：把尚未进 JuiceFS 的「真实目录」战报，按 <owner>/<category> 拷进 /mnt/jfs/reports。
#
# 只拷「真实目录」的 category（软链的说明已在 jfs，跳过）。用 rsync，幂等、可断点续跑。
# **不动 /data 原件**（只拷不删）——切 DATA_DIR 到 jfs 前，站点仍从 /data 正常服务，零破坏。
# 切换并观察无碍后，/data 原件作为备份，择日再清。
#
# 覆盖两棵树：/data/ohmywod/report 与 /mnt/extra-report/extra/report（含被软链迁去 extra 的 owner）。
# 按 realpath 去重，避免 /data/<owner> 软链到 extra 时重复处理。
#
# 用法：bash jfs-report-migrate-remaining.sh [--dry-run] [--owner NAME] [--jfs DIR]
set -euo pipefail

JFS="/mnt/jfs/reports"
REPORT_TREES=("/data/ohmywod/report" "/mnt/extra-report/extra/report")
DRY_RUN=false
ONLY_OWNER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift;;
    --owner) ONLY_OWNER="$2"; shift 2;;
    --jfs) JFS="$2"; shift 2;;
    -h|--help) grep '^#' "$0" | sed 's/^# \?//'; exit 0;;
    *) echo "未知参数: $1"; exit 1;;
  esac
done

command -v rsync >/dev/null || { echo "错误：需要 rsync"; exit 1; }
[ -d "$JFS" ] || { echo "错误：$JFS 不存在（JuiceFS 未挂载？）"; exit 1; }

log() { printf '\033[1;34m[migrate]\033[0m %s\n' "$*"; }
RSYNC_OPTS=(-a --no-owner --no-group)
$DRY_RUN && RSYNC_OPTS+=(--dry-run --itemize-changes)

declare -A seen_realdir
copied=0; skipped_link=0; skipped_done=0; conflicts=0

process_owner_dir() {
  local owner="$1" odir="$2"
  local real; real="$(realpath "$odir" 2>/dev/null || echo "$odir")"
  [ -n "${seen_realdir[$real]:-}" ] && return    # 已处理过这个真实目录
  seen_realdir[$real]=1
  [ -d "$real" ] || return

  local cat cpath dest
  for cpath in "$real"/*; do
    [ -e "$cpath" ] || continue
    cat="$(basename "$cpath")"
    if [ -L "$cpath" ]; then skipped_link=$((skipped_link+1)); continue; fi   # 软链=已在 jfs
    [ -d "$cpath" ] || continue
    dest="$JFS/$owner/$cat"

    if [ -d "$dest" ] && [ ! -L "$dest" ]; then
      # 目标已存在：可能上次已拷（rsync 会校验补齐）。用 rsync 幂等续跑，不算冲突。
      skipped_done=$((skipped_done+1))
    fi
    log "$owner/$cat  <-  $cpath"
    if $DRY_RUN; then
      # 捕获后再截断，避免 head 关管道触发 SIGPIPE+pipefail 中止脚本
      out="$(rsync "${RSYNC_OPTS[@]}" --stats "$cpath/" "$dest/" 2>&1 || true)"
      printf '%s\n' "$out" | grep -E 'Number of (files|created files|regular files transferred)' | sed 's/^/    /' || true
    else
      mkdir -p "$JFS/$owner"
      rsync "${RSYNC_OPTS[@]}" "$cpath/" "$dest/"
      # 校验条目数一致（粗校验）
      s=$(find "$cpath" | wc -l); d=$(find "$dest" | wc -l)
      if [ "$s" != "$d" ]; then echo "    ⚠ 条目数不一致 src=$s dest=$d，请复查"; conflicts=$((conflicts+1)); fi
    fi
    copied=$((copied+1))
  done
}

for base in "${REPORT_TREES[@]}"; do
  [ -d "$base" ] || continue
  for odir in "$base"/*; do
    [ -e "$odir" ] || continue
    owner="$(basename "$odir")"
    [ -n "$ONLY_OWNER" ] && [ "$owner" != "$ONLY_OWNER" ] && continue
    process_owner_dir "$owner" "$odir"
  done
done

log "处理 category(真实目录) 拷贝 $copied 个；跳过软链(已在jfs) $skipped_link；目标已存在(rsync续跑) $skipped_done；校验异常 $conflicts"
log "完成。$($DRY_RUN && echo '(dry-run，未改动)')  下一步：验证后切 DATA_DIR 到 $JFS。"
