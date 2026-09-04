#!/usr/bin/env bash
set -euo pipefail

PRODUCT_DIR="${1:-.}"
PRODUCT_ROOT="$(cd "$PRODUCT_DIR" && pwd)"
errors=0

fail() {
  printf 'ERROR: %s\n' "$1" >&2
  errors=$((errors + 1))
}

lock="$PRODUCT_ROOT/.deltafuse/lock.yaml"
config="$PRODUCT_ROOT/.deltafuse/config.yaml"

[ -e "$config" ] || fail "Missing required path: .deltafuse/config.yaml"
[ -e "$lock" ] || fail "Missing required path: .deltafuse/lock.yaml"

config_version=""
lock_version=""
lock_hash=""

path_intake="docs/intake"
path_changes="docs/changes"
path_spec="docs/spec"
path_decisions="docs/decisions"
path_archive="docs/archive"

adapter_roots=()

if [ -f "$config" ]; then
  config_version="$(sed -n 's/^[[:space:]]\{2\}version:[[:space:]]*//p' "$config" | head -n 1)"
  [ -n "$config_version" ] || fail "Config file has no requested framework version"

  val="$(awk '/^paths:[[:space:]]*$/ { in_p=1; next } in_p && /^[[:space:]]+intake:[[:space:]]*/ { sub(/^[[:space:]]+intake:[[:space:]]*/, ""); sub(/[[:space:]]+$/, ""); print; exit } in_p && /^[^[:space:]]/ { in_p=0 }' "$config")"
  [ -z "$val" ] || path_intake="$val"

  val="$(awk '/^paths:[[:space:]]*$/ { in_p=1; next } in_p && /^[[:space:]]+changes:[[:space:]]*/ { sub(/^[[:space:]]+changes:[[:space:]]*/, ""); sub(/[[:space:]]+$/, ""); print; exit } in_p && /^[^[:space:]]/ { in_p=0 }' "$config")"
  [ -z "$val" ] || path_changes="$val"

  val="$(awk '/^paths:[[:space:]]*$/ { in_p=1; next } in_p && /^[[:space:]]+specification:[[:space:]]*/ { sub(/^[[:space:]]+specification:[[:space:]]*/, ""); sub(/[[:space:]]+$/, ""); print; exit } in_p && /^[^[:space:]]/ { in_p=0 }' "$config")"
  [ -z "$val" ] || path_spec="$val"

  val="$(awk '/^paths:[[:space:]]*$/ { in_p=1; next } in_p && /^[[:space:]]+decisions:[[:space:]]*/ { sub(/^[[:space:]]+decisions:[[:space:]]*/, ""); sub(/[[:space:]]+$/, ""); print; exit } in_p && /^[^[:space:]]/ { in_p=0 }' "$config")"
  [ -z "$val" ] || path_decisions="$val"

  val="$(awk '/^paths:[[:space:]]*$/ { in_p=1; next } in_p && /^[[:space:]]+archive:[[:space:]]*/ { sub(/^[[:space:]]+archive:[[:space:]]*/, ""); sub(/[[:space:]]+$/, ""); print; exit } in_p && /^[^[:space:]]/ { in_p=0 }' "$config")"
  [ -z "$val" ] || path_archive="$val"

  while IFS= read -r root; do
    [ -n "$root" ] && adapter_roots+=("$root")
  done < <(awk '
    /^adapters:[[:space:]]*$/ { in_adapters=1; next }
    in_adapters && /^[[:space:]]+roots:[[:space:]]*$/ { in_roots=1; next }
    in_roots && /^[[:space:]]+-[[:space:]]+/ {
      sub(/^[[:space:]]+-[[:space:]]+/, "")
      sub(/[[:space:]]+$/, "")
      print
      next
    }
    in_roots && /^[^[:space:]]/ { in_adapters=0; in_roots=0 }
  ' "$config")
fi

if [ ${#adapter_roots[@]} -eq 0 ]; then
  adapter_roots=(.agents/skills .cursor/skills .gemini/skills)
fi

for required in \
  "$path_intake" \
  "$path_changes" \
  "$path_spec" \
  "$path_decisions" \
  "$path_archive/intake" \
  "$path_archive/changes"; do
  [ -e "$PRODUCT_ROOT/$required" ] || fail "Missing required path: $required"
done

for forbidden in docs/process docs/init docs/todo; do
  [ ! -e "$PRODUCT_ROOT/$forbidden" ] || fail "Legacy product path must be migrated: $forbidden"
done

if [ -f "$lock" ]; then
  lock_version="$(sed -n 's/^[[:space:]]\{2\}version:[[:space:]]*//p' "$lock" | head -n 1)"
  lock_hash="$(sed -n 's/^[[:space:]]\{2\}content_hash:[[:space:]]*//p' "$lock" | head -n 1)"
  [ -n "$lock_version" ] || fail "Lock file has no framework version"
  printf '%s' "$lock_hash" | grep -Eq '^sha256:[a-fA-F0-9]{64}$' || fail "Lock file has no valid framework content hash"
fi

if [ -n "$config_version" ] && [ -n "$lock_version" ] && [ "$config_version" != "$lock_version" ]; then
  fail "Requested framework version $config_version does not match locked version $lock_version"
fi

# 1. Validate capability catalog structure
capabilities="$PRODUCT_ROOT/$path_spec/_capabilities.yaml"
if [ -f "$capabilities" ]; then
  grep -Eq '^schema_version:[[:space:]]*2[[:space:]]*$' "$capabilities" || fail "Capability catalog _capabilities.yaml missing or invalid schema_version (expected 2)"
  grep -Eq '^domains:' "$capabilities" || fail "Capability catalog _capabilities.yaml missing required domains key"
fi

# 2. Validate changes structure
if [ -d "$PRODUCT_ROOT/$path_changes" ]; then
  for change in "$PRODUCT_ROOT/$path_changes"/*; do
    [ -d "$change" ] || continue
    change_name="$(basename "$change")"
    printf '%s' "$change_name" | grep -Eq '^CHG-[0-9]{3,}(-[a-z0-9-]+)?$' || fail "Change directory name '$change_name' does not match pattern '^CHG-[0-9]{3,}(-[a-z0-9-]+)?$'"
    
    [ -f "$change/request.md" ] || fail "Change $change_name is missing request.md"
    
    change_yaml="$change/change.yaml"
    if [ ! -f "$change_yaml" ]; then
      fail "Change $change_name is missing change.yaml"
    else
      grep -Eq '^schema_version:[[:space:]]*2[[:space:]]*$' "$change_yaml" || fail "Change $change_name change.yaml missing or invalid schema_version (expected 2)"
      grep -Eq "^id:[[:space:]]*$change_name[[:space:]]*$" "$change_yaml" || fail "Change $change_name change.yaml id does not match directory name '$change_name'"
      grep -Eq '^status:[[:space:]]*(normalized|analyzing|blocked-on-decision|analyzed|specification-proposed|specified|decomposed|targeting|target-confirmed|implementing|implemented|verifying|converged|archived|rejected|duplicate|not-reproduced|superseded)[[:space:]]*$' "$change_yaml" || fail "Change $change_name change.yaml has missing or invalid status"
      grep -Eq '^title:[[:space:]]*[^[:space:]]' "$change_yaml" || fail "Change $change_name change.yaml missing title"
      grep -Eq '^framework:' "$change_yaml" || fail "Change $change_name change.yaml missing framework section"
    fi

    routing_yaml="$change/routing.yaml"
    if [ -f "$routing_yaml" ]; then
      grep -Eq '^change:[[:space:]]*' "$routing_yaml" || fail "Change $change_name routing.yaml missing change field"
      grep -Eq '^claims:' "$routing_yaml" || fail "Change $change_name routing.yaml missing claims section"
    fi

    coverage_yaml="$change/coverage.yaml"
    if [ -f "$coverage_yaml" ]; then
      grep -Eq '^change:[[:space:]]*' "$coverage_yaml" || fail "Change $change_name coverage.yaml missing change field"
      grep -Eq '^claims:' "$coverage_yaml" || fail "Change $change_name coverage.yaml missing claims section"
    fi

    slices_dir="$change/slices"
    if [ -d "$slices_dir" ]; then
      for slice_file in "$slices_dir"/*.md; do
        [ -f "$slice_file" ] || continue
        slice_name="$(basename "$slice_file")"
        grep -Eq '^id:[[:space:]]*SLICE-[0-9]{2,}[[:space:]]*$' "$slice_file" || fail "Change $change_name slice $slice_name missing or invalid id in frontmatter"
        grep -Eq '^primary_capability:[[:space:]]*[^[:space:]]' "$slice_file" || fail "Change $change_name slice $slice_name missing primary_capability in frontmatter"
        grep -Eq '^status:[[:space:]]*(draft|analyzing|blocked|analyzed|specified|decomposed|verified)[[:space:]]*$' "$slice_file" || fail "Change $change_name slice $slice_name missing or invalid status in frontmatter"
      done
    fi

    tasks_dir="$change/tasks"
    if [ -d "$tasks_dir" ]; then
      for task_file in "$tasks_dir"/*.md; do
        [ -f "$task_file" ] || continue
        task_name="$(basename "$task_file")"
        case "$task_name" in
          *template*) continue ;;
        esac
        grep -Eq '^id:[[:space:]]*TASK-[0-9]{3,}[[:space:]]*$' "$task_file" || fail "Change $change_name task $task_name missing or invalid id in frontmatter"
        grep -Eq '^slice:[[:space:]]*SLICE-[0-9]{2,}[[:space:]]*$' "$task_file" || fail "Change $change_name task $task_name missing or invalid slice in frontmatter"
        grep -Eq '^status:[[:space:]]*(pending|targeting|target-confirmed|implementing|implemented|verified|blocked|cancelled|superseded)[[:space:]]*$' "$task_file" || fail "Change $change_name task $task_name missing or invalid status in frontmatter"
        grep -Eq '^kind:[[:space:]]*(feature|bugfix|refactor|maintenance|documentation)[[:space:]]*$' "$task_file" || fail "Change $change_name task $task_name missing or invalid kind in frontmatter"
      done
    fi
  done
fi

# 3. Validate decisions structure
decisions_dir="$PRODUCT_ROOT/$path_decisions"
if [ -d "$decisions_dir" ]; then
  for dec_file in "$decisions_dir"/DEC-*.md; do
    [ -f "$dec_file" ] || continue
    dec_name="$(basename "$dec_file")"
    [ "$dec_name" != "DEC-0000-template.md" ] || continue
    grep -Eq '^id:[[:space:]]*DEC-[0-9]{4,}[[:space:]]*$' "$dec_file" || fail "Decision $dec_name missing or invalid id in frontmatter"
    grep -Eq '^kind:[[:space:]]*(product|architecture|integration|policy|operational)[[:space:]]*$' "$dec_file" || fail "Decision $dec_name missing or invalid kind in frontmatter"
    grep -Eq '^status:[[:space:]]*(proposed|accepted|rejected|superseded)[[:space:]]*$' "$dec_file" || fail "Decision $dec_name missing or invalid status in frontmatter"
    grep -Eq '^owner:[[:space:]]*[^[:space:]]' "$dec_file" || fail "Decision $dec_name missing owner in frontmatter"
  done
fi

# 4. Validate skills in configured adapter roots
skills="intake analyze-change specify-change decompose-change target-task implement-task verify-change"
for adapter in "${adapter_roots[@]}"; do
  [ -d "$PRODUCT_ROOT/$adapter" ] || { fail "Missing configured adapter root: $adapter"; continue; }
  for skill in $skills; do
    skill_root="$PRODUCT_ROOT/$adapter/$skill"
    [ -f "$skill_root/SKILL.md" ] || { fail "Missing generated skill: $adapter/$skill/SKILL.md"; continue; }
    marker="$skill_root/.deltafuse-generated.yaml"
    [ -f "$marker" ] || { fail "Missing generated metadata: $adapter/$skill"; continue; }
    grep -Fq '# DO NOT EDIT: generated by DeltaFuse installer.' "$skill_root/SKILL.md" || fail "Generated skill is not marked DO NOT EDIT: $adapter/$skill"
    [ -z "$lock_version" ] || grep -Fq "generated_by: deltafuse@$lock_version" "$marker" || fail "Generated skill version mismatch: $adapter/$skill"
    [ -z "$lock_hash" ] || grep -Fq "content_hash: $lock_hash" "$marker" || fail "Generated skill hash mismatch: $adapter/$skill"
  done
done

if [ "$errors" -ne 0 ]; then
  exit 1
fi

printf 'DeltaFuse product layout is valid.\n'
