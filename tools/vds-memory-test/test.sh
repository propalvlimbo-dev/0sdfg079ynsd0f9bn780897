#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "$0")/../.." && pwd)
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
cp -p "$repo/start.sh" "$work/start.sh"
bash "$repo/tools/vds-memory-test/install.sh" "$work/start.sh"
# The entire output must equal the original except for the one intended setting.
sed 's/-Xms10G/-Xms8G/' "$repo/start.sh" > "$work/expected.sh"
cmp "$work/expected.sh" "$work/start.sh"
backup=("$work"/start.sh.before-xms8.*)
[[ ${#backup[@]} -eq 1 ]]
cmp "$repo/start.sh" "${backup[0]}"
# A second run and ambiguous inputs must fail without changing the target.
if bash "$repo/tools/vds-memory-test/install.sh" "$work/start.sh"; then exit 1; fi
cmp "$work/expected.sh" "$work/start.sh"
cp "$repo/start.sh" "$work/duplicate.sh"
printf '\n# -Xms10G\n' >> "$work/duplicate.sh"
cp "$work/duplicate.sh" "$work/original.sh"
if bash "$repo/tools/vds-memory-test/install.sh" "$work/duplicate.sh"; then exit 1; fi
cmp "$work/original.sh" "$work/duplicate.sh"
ln -s "$work/duplicate.sh" "$work/link.sh"
if bash "$repo/tools/vds-memory-test/install.sh" "$work/link.sh"; then exit 1; fi
bash -n "$repo/tools/vds-memory-test/install.sh"
echo 'All memory-test installer checks passed.'
