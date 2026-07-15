#!/usr/bin/env bash
# 步骤 1：把 JuiceFS 里「扁平」的 <category> 归位成 <owner>/<category>。
#
# 背景：早期迁移把战报按 rname(=category)扁平拷进 /mnt/jfs/reports/<category>，丢了 owner 层。
# owner 归属由 /data(及 /mnt/extra-report)里「指向 jfs 的 category 级软链」唯一确定
#   /data/<owner>/<category> -> /mnt/jfs/reports/<category>   ⇒  该 category 归 <owner>
#   同名的「真实目录」是另一个 owner 的独立战报，不算归属（已用生产数据核实 107/107 唯一、0 冲突）。
#
# 动作（每个扁平 category）：
#   1) mkdir -p /mnt/jfs/reports/<owner>
#   2) mv /mnt/jfs/reports/<category> -> /mnt/jfs/reports/<owner>/<category>   （JuiceFS 内 mv=纯元数据，零数据传输）
#   3) 把所有指向旧位置的软链 repoint 到新位置（保持站点在切 DATA_DIR 前仍可用）
#   4) 删除顶层杂物文件（如 test.log）
#
# 幂等：软链目标已是 <owner>/<category>（3 段）的跳过；只处理仍是 <category>（2 段扁平）的。
# 用法：bash jfs-report-owner-backfill.sh [--dry-run] [--jfs DIR] [--purge-junk]
set -euo pipefail

JFS="/mnt/jfs/reports"
REPORT_TREES=("/data/ohmywod/report" "/mnt/extra-report/extra/report")
DRY_RUN=false
PURGE_JUNK=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift;;
    --jfs) JFS="$2"; shift 2;;
    --purge-junk) PURGE_JUNK=true; shift;;
    -h|--help) grep '^#' "$0" | sed 's/^# \?//'; exit 0;;
    *) echo "未知参数: $1"; exit 1;;
  esac
done

run() { if $DRY_RUN; then echo "  [dry-run] $*"; else eval "$@"; fi; }
log() { printf '\033[1;34m[backfill]\033[0m %s\n' "$*"; }

[ -d "$JFS" ] || { echo "错误：$JFS 不存在（JuiceFS 未挂载？）"; exit 1; }

# ---- 1. 收集「指向 jfs 扁平 category 的软链」→ (symlink_path, category, owner) ----
# 只认 target 恰为 $JFS/<单段> 的软链（扁平）；已是 $JFS/<owner>/<cat> 的忽略（已归位）。
MAP="$(mktemp)"; trap 'rm -f "$MAP"' EXIT
for base in "${REPORT_TREES[@]}"; do
  [ -d "$base" ] || continue
  while IFS= read -r link; do
    tgt="$(readlink "$link" 2>/dev/null || true)"
    case "$tgt" in
      "$JFS"/*)
        rel="${tgt#"$JFS"/}"
        # rel 里若含 "/" 说明已是 <owner>/<cat>，跳过；只要单段的
        if [[ "$rel" != */* ]]; then
          owner="$(basename "$(dirname "$link")")"
          printf '%s\t%s\t%s\n' "$link" "$rel" "$owner" >> "$MAP"
        fi
        ;;
    esac
  done < <(find "$base" -mindepth 2 -maxdepth 2 -type l 2>/dev/null)
done

n_links=$(wc -l < "$MAP" | tr -d ' ')
n_cats=$(cut -f2 "$MAP" | sort -u | wc -l | tr -d ' ')
log "发现指向扁平 category 的软链 $n_links 条，涉及 $n_cats 个 category"

# ---- 2. 冲突自检：同一 category 是否被多个 owner 的软链指向 ----
conflicts="$(cut -f2,3 "$MAP" | sort -u | cut -f1 | sort | uniq -d || true)"
if [ -n "$conflicts" ]; then
  echo "错误：以下 category 有多 owner 软链冲突，请人工处理后再跑："; echo "$conflicts"; exit 1
fi

# ---- 3. 逐个 category 归位 + repoint ----
moved=0; repointed=0
while IFS= read -r cat; do
  owner="$(awk -F'\t' -v c="$cat" '$2==c{print $3; exit}' "$MAP")"
  src="$JFS/$cat"
  dest_dir="$JFS/$owner"
  dest="$dest_dir/$cat"

  if [ -d "$src" ] && [ ! -L "$src" ]; then
    if [ -e "$dest" ]; then
      echo "  ⚠ 目标已存在，跳过 mv（人工确认）：$dest"
    else
      log "归位: $cat  ->  $owner/$cat"
      if [ "$owner" = "$cat" ]; then
        # owner 与 category 同名：不能把目录 mv 进自身子目录，先移到临时名中转
        tmp="$JFS/.backfill-tmp-$cat.$$"
        run "mv \"$src\" \"$tmp\""
        run "mkdir -p \"$dest_dir\""
        run "mv \"$tmp\" \"$dest\""
      else
        run "mkdir -p \"$dest_dir\""
        run "mv \"$src\" \"$dest\""
      fi
      moved=$((moved+1))
    fi
  fi

  # repoint 该 category 的所有软链到新位置（即便 mv 已幂等跳过，也确保软链正确）
  while IFS=$'\t' read -r link _c _o; do
    [ "$_c" = "$cat" ] || continue
    run "ln -sfn \"$dest\" \"$link\""
    repointed=$((repointed+1))
  done < "$MAP"
done < <(cut -f2 "$MAP" | sort -u)

log "归位 $moved 个 category，repoint $repointed 条软链"

# ---- 4. 顶层杂物文件（非目录）----
junk="$(find "$JFS" -maxdepth 1 -type f 2>/dev/null || true)"
if [ -n "$junk" ]; then
  echo "顶层杂物文件："; echo "$junk" | sed 's/^/  /'
  if $PURGE_JUNK; then
    while IFS= read -r f; do [ -n "$f" ] && run "rm -f \"$f\""; done <<< "$junk"
    log "已删杂物文件"
  else
    log "如需删除加 --purge-junk"
  fi
fi

log "完成。$($DRY_RUN && echo '(dry-run，未改动)')"
