#!/usr/bin/env bash
# scripts/sync_upstream.sh — Upstream sync for Korean translation
#
# Detects changes in the upstream English repo, translates changed
# markdown files via Anthropic API (curl + jq), and creates an
# auto-merged PR in the Korean translation repo.

set -Euo pipefail

######################################################################
# Config
######################################################################

UPSTREAM_OWNER="lawmaster10"
UPSTREAM_REPO="howcryptoworksbook"
UPSTREAM_BRANCH="master"

SYNC_STATE=".github/sync-state.json"
GUIDELINES="CLAUDE.md"

MODEL="claude-sonnet-4-20250514"
MAX_TOKENS=16384

API_URL="https://api.anthropic.com/v1/messages"
API_VERSION="2023-06-01"

######################################################################
# Setup
######################################################################

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

log()  { printf '  %s\n' "$*"; }
die()  { printf '❌ %s\n' "$*" >&2; exit 1; }

for cmd in gh jq curl git; do
  command -v "$cmd" >/dev/null 2>&1 || die "$cmd is required"
done

[[ -n "${ANTHROPIC_API_KEY:-}" ]] || die "ANTHROPIC_API_KEY not set"

######################################################################
# Helpers
######################################################################

should_skip() {
  local name lower
  name="$(basename "$1")"
  lower="${name,,}"
  # Skip non-markdown
  [[ "$lower" != *.md ]] && return 0
  # Skip customized files
  case "$lower" in
    readme.md|contributing.md) return 0 ;;
  esac
  return 1
}

fetch_upstream_file() {
  # $1=filepath  $2=ref  $3=output_file
  gh api "repos/$UPSTREAM_OWNER/$UPSTREAM_REPO/contents/$1?ref=$2" \
    --jq '.content' 2>/dev/null | base64 -d > "$3" 2>/dev/null
}

strip_fences() {
  # Remove wrapping ```markdown ... ``` the model may add
  local file="$1"
  local first last
  first=$(head -1 "$file")
  last=$(tail -1 "$file")
  if [[ "$first" =~ ^\`\`\` ]] && [[ "$last" == '```' ]]; then
    sed -i '1d;$d' "$file"
  fi
}

call_anthropic() {
  # $1=system_file  $2=user_file  $3=output_file
  local payload="$WORK/payload.json"
  local response="$WORK/response.json"

  jq -n \
    --arg model "$MODEL" \
    --argjson max_tokens "$MAX_TOKENS" \
    --rawfile system "$1" \
    --rawfile user "$2" \
    '{
      model: $model,
      max_tokens: $max_tokens,
      system: $system,
      messages: [{role: "user", content: $user}]
    }' > "$payload"

  local http_code
  http_code=$(curl -sS -w '%{http_code}' -o "$response" \
    -H "content-type: application/json" \
    -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "anthropic-version: $API_VERSION" \
    -d @"$payload" \
    "$API_URL")

  if [[ "$http_code" -lt 200 || "$http_code" -ge 300 ]]; then
    log "API returned HTTP $http_code"
    jq -r '.error.message // .' < "$response" >&2 || cat "$response" >&2
    return 1
  fi

  if ! jq -er '.content[0].text' < "$response" > "$3"; then
    log "Failed to extract text from API response"
    jq . < "$response" >&2 2>/dev/null || true
    return 1
  fi

  strip_fences "$3"
  return 0
}

translate_one() {
  # $1=filename  $2=status (added/modified/etc)
  local filename="$1"
  local safe="${filename//\//_}"
  local en_file="$WORK/en_${safe}"
  local out_file="$WORK/out_${safe}"
  local sys_file="$WORK/system.txt"
  local user_file="$WORK/user_${safe}.txt"

  # Fetch new English content
  if ! fetch_upstream_file "$filename" "$HEAD_SHA" "$en_file"; then
    log "⚠️ Could not fetch upstream content for $filename"
    return 1
  fi

  # Build system prompt (once, reuse if exists)
  if [[ ! -f "$sys_file" ]]; then
    {
      echo "You are a professional Korean translator for a technical cryptocurrency textbook."
      echo "Follow these project-specific translation guidelines exactly:"
      echo ""
      cat "$GUIDELINES"
      echo ""
      echo "CRITICAL RULES:"
      echo "- Output ONLY the translated markdown content"
      echo "- Do NOT wrap output in code fences"
      echo "- Do NOT add any explanatory text before or after"
      echo "- Preserve all markdown formatting exactly"
      echo "- Follow the glossary for every technical term"
    } > "$sys_file"
  fi

  # Build user prompt
  if [[ -f "$filename" ]]; then
    # Existing file — update translation
    {
      echo "## Task"
      echo ""
      echo "The upstream English file \`$filename\` has been updated. Update the existing Korean translation to reflect the changes."
      echo ""
      echo "## Current Korean Translation"
      echo ""
      cat "$filename"
      echo ""
      echo "## Updated English Source"
      echo ""
      cat "$en_file"
      echo ""
      echo "## Instructions"
      echo ""
      echo "1. Compare the updated English source with the current Korean translation."
      echo "2. Identify sections that are new, modified, or removed in the English version."
      echo "3. Apply equivalent changes to the Korean translation:"
      echo "   - NEW sections: translate them and insert at the correct position"
      echo "   - MODIFIED sections: update the Korean text to match the new English meaning"
      echo "   - REMOVED sections: remove them from the Korean translation"
      echo "4. Keep ALL unchanged Korean text EXACTLY as-is — do not rephrase, reformat, or improve existing translations."
      echo "5. Follow the translation guidelines strictly (glossary, style, formatting)."
      echo "6. Output ONLY the complete updated Korean markdown file. No explanations, no code fences."
    } > "$user_file"
  else
    # New file — full translation
    {
      echo "## Task"
      echo ""
      echo "Translate the following English markdown file \`$filename\` to Korean."
      echo ""
      echo "## English Source"
      echo ""
      cat "$en_file"
      echo ""
      echo "## Instructions"
      echo ""
      echo "1. Translate the entire file to Korean following the guidelines strictly."
      echo "2. Include the standard file header as specified in the guidelines."
      echo "3. Use the glossary for technical terms."
      echo "4. Keep markdown structure, links, image paths, code blocks, and URLs unchanged."
      echo "5. Output ONLY the complete Korean markdown file. No explanations, no code fences."
    } > "$user_file"
  fi

  # Call Anthropic
  if ! call_anthropic "$sys_file" "$user_file" "$out_file"; then
    return 1
  fi

  # Write result
  mkdir -p "$(dirname "$filename")"
  cp "$out_file" "$filename"
  return 0
}

######################################################################
# Main
######################################################################

echo "📡 Checking upstream for changes..."
LAST_SHA=$(jq -r '.last_synced_sha' "$SYNC_STATE")
HEAD_SHA=$(gh api "repos/$UPSTREAM_OWNER/$UPSTREAM_REPO/commits/$UPSTREAM_BRANCH" --jq '.sha')

log "Last synced: ${LAST_SHA:0:7}"
log "Upstream HEAD: ${HEAD_SHA:0:7}"

force="${FORCE_SYNC:-false}"
if [[ "$HEAD_SHA" == "$LAST_SHA" && "$force" != "true" ]]; then
  echo "✅ No upstream changes detected. Exiting."
  exit 0
fi

[[ "$force" == "true" ]] && log "⚡ Force sync — proceeding regardless."

# ── Get changed files ──────────────────────────────────────────────

echo ""
echo "📋 Getting changed files..."

mapfile -t raw_files < <(
  gh api "repos/$UPSTREAM_OWNER/$UPSTREAM_REPO/compare/${LAST_SHA}...${HEAD_SHA}" \
    --jq '.files[] | "\(.status)\t\(.filename)"' 2>/dev/null || true
)

# Handle no-diff case (same SHA with force, or only non-file changes)
if [[ ${#raw_files[@]} -eq 0 || -z "${raw_files[0]:-}" ]]; then
  log "No files changed."
  if [[ "$HEAD_SHA" != "$LAST_SHA" ]]; then
    jq --arg sha "$HEAD_SHA" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      '.last_synced_sha = $sha | .last_synced_at = $ts' "$SYNC_STATE" > "$WORK/state.json"
    mv "$WORK/state.json" "$SYNC_STATE"
    git add "$SYNC_STATE"
    git diff --cached --quiet || {
      git commit -m "chore: update sync state (no translatable changes)"
      git push origin main
    }
  fi
  echo "✅ Done."
  exit 0
fi

# Filter translatable files
changed=()
skipped=()
for line in "${raw_files[@]}"; do
  [[ -z "$line" ]] && continue
  file_status="${line%%$'\t'*}"
  file_name="${line#*$'\t'}"
  if should_skip "$file_name"; then
    skipped+=("$file_name")
  else
    changed+=("$file_status:$file_name")
  fi
done

if [[ ${#changed[@]} -eq 0 ]]; then
  log "No translatable markdown files."
  jq --arg sha "$HEAD_SHA" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    '.last_synced_sha = $sha | .last_synced_at = $ts' "$SYNC_STATE" > "$WORK/state.json"
  mv "$WORK/state.json" "$SYNC_STATE"
  git add "$SYNC_STATE"
  git diff --cached --quiet || {
    git commit -m "chore: update sync state (no translatable changes)"
    git push origin main
  }
  echo "✅ Done."
  exit 0
fi

log "${#changed[@]} file(s) to translate, ${#skipped[@]} skipped"
for entry in "${changed[@]}"; do
  log "  📄 ${entry#*:} (${entry%%:*})"
done

# ── Translate ──────────────────────────────────────────────────────

echo ""
echo "🔄 Translating files..."

branch="sync/upstream-${HEAD_SHA:0:7}"
git checkout -b "$branch"

translated=()
failed=()

for entry in "${changed[@]}"; do
  file_status="${entry%%:*}"
  filename="${entry#*:}"

  echo ""
  log "📝 $filename ($file_status)..."

  if translate_one "$filename" "$file_status"; then
    translated+=("$filename")
    log "✅ $filename"
  else
    failed+=("$filename")
    log "❌ $filename"
  fi
done

if [[ ${#translated[@]} -eq 0 ]]; then
  echo ""
  echo "❌ All translations failed. Aborting."
  git checkout main
  git branch -D "$branch" 2>/dev/null || true
  exit 1
fi

# ── Commit & Push ──────────────────────────────────────────────────

echo ""
echo "📦 Committing..."
git add -A
git commit -m "번역 동기화: upstream ${HEAD_SHA:0:7}"

# Update sync state in the branch
jq --arg sha "$HEAD_SHA" --arg ts "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  '.last_synced_sha = $sha | .last_synced_at = $ts' "$SYNC_STATE" > "$WORK/state.json"
mv "$WORK/state.json" "$SYNC_STATE"
git add "$SYNC_STATE"
git commit -m "chore: update sync state to ${HEAD_SHA:0:7}"

echo ""
echo "🚀 Pushing $branch..."
git push origin "$branch"

# ── Create PR ──────────────────────────────────────────────────────

echo ""
echo "📝 Creating PR..."

gh label create "auto-translation" --color 0E8A16 \
  --description "자동 번역 PR" --force 2>/dev/null || true

pr_body="$WORK/pr-body.md"
{
  echo "## 📡 Upstream 동기화"
  echo ""
  echo "### 포함된 upstream 커밋"
  gh api "repos/$UPSTREAM_OWNER/$UPSTREAM_REPO/compare/${LAST_SHA}...${HEAD_SHA}" \
    --jq '.commits[] | "- [`\(.sha[0:7])`](https://github.com/'"$UPSTREAM_OWNER/$UPSTREAM_REPO"'/commit/\(.sha)) \(.commit.message | split("\n")[0]) — \(.commit.author.name)"' \
    2>/dev/null || echo "- (커밋 정보를 가져올 수 없음)"
  echo ""
  echo "### 번역된 파일"
  for f in "${translated[@]}"; do echo "- ✅ \`$f\`"; done

  if [[ ${#failed[@]} -gt 0 ]]; then
    echo ""
    echo "### ❌ 번역 실패"
    for f in "${failed[@]}"; do echo "- ❌ \`$f\`"; done
    echo ""
    echo "> ⚠️ 일부 파일 번역 실패. 수동 리뷰 필요."
  fi

  if [[ ${#skipped[@]} -gt 0 ]]; then
    echo ""
    echo "### ⏭️ 건너뛴 파일"
    for f in "${skipped[@]}"; do echo "- ⏭️ \`$f\`"; done
  fi

  echo ""
  echo "---"
  echo "⚡ 이 PR은 자동 번역 시스템에 의해 생성되었습니다."
  echo "📖 동기화 범위: \`${LAST_SHA:0:7}\` → \`${HEAD_SHA:0:7}\`"
} > "$pr_body"

# PR title from first commit message
first_msg=$(
  gh api "repos/$UPSTREAM_OWNER/$UPSTREAM_REPO/compare/${LAST_SHA}...${HEAD_SHA}" \
    --jq '.commits[0].commit.message | split("\n")[0]' 2>/dev/null \
    | head -c 60 || true
)
pr_title="[자동번역] Upstream 동기화: ${first_msg:-${LAST_SHA:0:7}..${HEAD_SHA:0:7}}"

pr_url=$(gh pr create \
  --title "$pr_title" \
  --body-file "$pr_body" \
  --head "$branch" \
  --base main)
echo "  ✅ PR: $pr_url"

gh pr edit "$pr_url" --add-label "auto-translation" 2>/dev/null || true

# ── Auto-merge ─────────────────────────────────────────────────────

if [[ ${#failed[@]} -eq 0 ]]; then
  echo ""
  echo "🔀 Auto-merging..."
  if gh pr merge "$pr_url" --squash --delete-branch; then
    echo "  ✅ Merged!"
  else
    echo "  ⚠️ Auto-merge failed. PR left open for review."
  fi
else
  echo ""
  echo "⚠️ Some translations failed. PR left open for manual review."
fi

echo ""
echo "🎉 Done!"
