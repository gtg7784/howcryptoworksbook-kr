#!/usr/bin/env python3
"""
Upstream sync script for Korean translation of "How Crypto Actually Works".

Detects changes in the upstream English repository, translates changed markdown
files to Korean using the Anthropic API, and creates an auto-merged PR.
"""

import json
import os
import subprocess
import sys
import base64
from pathlib import Path

import anthropic

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

UPSTREAM_OWNER = "lawmaster10"
UPSTREAM_REPO = "howcryptoworksbook"
UPSTREAM_BRANCH = "master"

SYNC_STATE_PATH = ".github/sync-state.json"
CLAUDE_MD_PATH = "CLAUDE.md"

# Files to NEVER translate (customized in KR repo)
SKIP_FILES = {"readme.md", "contributing.md"}

# Only translate markdown files
TARGET_EXTENSIONS = {".md"}

# Anthropic model for translation (cost-effective)
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 16384


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run(cmd: str, check: bool = True, capture: bool = True) -> str:
    """Run a shell command and return stdout."""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=capture,
        text=True,
        check=check,
    )
    return result.stdout.strip() if capture else ""


def gh_api(endpoint: str, jq: str | None = None) -> str:
    """Call GitHub API via gh CLI."""
    cmd = f"gh api {endpoint}"
    if jq:
        cmd += f" --jq '{jq}'"
    return run(cmd)


def load_sync_state() -> dict:
    """Load the sync state file."""
    with open(SYNC_STATE_PATH) as f:
        return json.load(f)


def save_sync_state(state: dict) -> None:
    """Write updated sync state."""
    with open(SYNC_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
        f.write("\n")


def load_translation_guidelines() -> str:
    """Load CLAUDE.md for the system prompt."""
    with open(CLAUDE_MD_PATH) as f:
        return f.read()


def get_upstream_head() -> str:
    """Get the current HEAD SHA of the upstream master branch."""
    return gh_api(
        f"repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/commits/{UPSTREAM_BRANCH}",
        jq=".sha",
    )


def get_changed_files(base_sha: str, head_sha: str) -> list[dict]:
    """Get files changed between two commits."""
    raw = gh_api(
        f"repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/compare/{base_sha}...{head_sha}",
        jq=".files[] | {filename, status, sha, patch}",
    )
    if not raw:
        return []

    files = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            files.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return files


def get_upstream_file_content(filepath: str, ref: str) -> str | None:
    """Fetch file content from upstream at a given ref."""
    try:
        b64 = gh_api(
            f"repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/contents/{filepath}?ref={ref}",
            jq=".content",
        )
        if not b64:
            return None
        # GitHub returns base64 with possible newlines
        return base64.b64decode(b64.replace("\n", "").replace("\\n", "")).decode(
            "utf-8"
        )
    except subprocess.CalledProcessError:
        return None


def get_commits_between(base_sha: str, head_sha: str) -> list[dict]:
    """Get commit list between two SHAs for PR description."""
    raw = gh_api(
        f"repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/compare/{base_sha}...{head_sha}",
        jq=".commits[] | {sha: .sha[0:7], message: .commit.message, author: .commit.author.name}",
    )
    if not raw:
        return []

    commits = []
    for line in raw.split("\n"):
        line = line.strip()
        if not line:
            continue
        try:
            commits.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return commits


def should_translate(filename: str) -> bool:
    """Check if a file should be translated."""
    lower = filename.lower()
    # Skip non-markdown files
    if Path(filename).suffix.lower() not in TARGET_EXTENSIONS:
        return False
    # Skip customized files
    basename = Path(filename).name.lower()
    if basename in SKIP_FILES:
        return False
    return True


# ---------------------------------------------------------------------------
# Translation via Anthropic API
# ---------------------------------------------------------------------------


def translate_file(
    client: anthropic.Anthropic,
    guidelines: str,
    english_content: str,
    korean_content: str | None,
    filename: str,
) -> str | None:
    """Translate or update a Korean translation using Claude."""

    if korean_content:
        user_prompt = f"""## Task

The upstream English file `{filename}` has been updated. Update the existing Korean translation to reflect the changes.

## Current Korean Translation

```markdown
{korean_content}
```

## Updated English Source

```markdown
{english_content}
```

## Instructions

1. Compare the updated English source with the current Korean translation.
2. Identify sections that are new, modified, or removed in the English version.
3. Apply equivalent changes to the Korean translation:
   - NEW sections: translate them and insert at the correct position
   - MODIFIED sections: update the Korean text to match the new English meaning
   - REMOVED sections: remove them from the Korean translation
4. Keep ALL unchanged Korean text EXACTLY as-is — do not rephrase, reformat, or "improve" existing translations.
5. Follow the translation guidelines strictly (glossary, style, formatting).
6. Output ONLY the complete updated Korean markdown file. No explanations, no code fences wrapping the output."""
    else:
        user_prompt = f"""## Task

Translate the following English markdown file `{filename}` to Korean.

## English Source

```markdown
{english_content}
```

## Instructions

1. Translate the entire file to Korean following the guidelines strictly.
2. Include the standard file header as specified in the guidelines.
3. Use the glossary for technical terms.
4. Keep markdown structure, links, image paths, code blocks, and URLs unchanged.
5. Output ONLY the complete Korean markdown file. No explanations, no code fences wrapping the output."""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=f"""You are a professional Korean translator for a technical cryptocurrency textbook.
Follow these project-specific translation guidelines exactly:

{guidelines}

CRITICAL RULES:
- Output ONLY the translated markdown content
- Do NOT wrap output in code fences
- Do NOT add any explanatory text before or after
- Preserve all markdown formatting exactly
- Follow the glossary for every technical term""",
            messages=[{"role": "user", "content": user_prompt}],
        )
        return response.content[0].text
    except Exception as e:
        print(f"  ❌ Anthropic API error for {filename}: {e}", file=sys.stderr)
        return None


# ---------------------------------------------------------------------------
# Git + PR operations
# ---------------------------------------------------------------------------


def create_branch(name: str) -> None:
    run(f"git checkout -b {name}")


def commit_file(filepath: str, message: str) -> None:
    run(f'git add "{filepath}"')
    run(f'git commit -m "{message}"')


def commit_all(message: str) -> None:
    run("git add -A")
    run(f'git commit -m "{message}"')


def push_branch(name: str) -> None:
    run(f"git push origin {name}")


def create_pr(title: str, body: str, branch: str) -> str:
    """Create a PR and return its URL."""
    # Write body to temp file to avoid shell escaping issues
    body_file = "/tmp/pr-body.md"
    with open(body_file, "w") as f:
        f.write(body)

    url = run(
        f'gh pr create --title "{title}" --body-file {body_file} '
        f"--head {branch} --base main"
    )
    return url


def merge_pr(pr_url: str) -> bool:
    """Auto-merge a PR. Returns True on success."""
    try:
        run(f"gh pr merge {pr_url} --squash --delete-branch")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  ⚠️ Auto-merge failed: {e}", file=sys.stderr)
        return False


def ensure_label(name: str, color: str = "0E8A16", description: str = "") -> None:
    """Create a label if it doesn't exist."""
    try:
        run(
            f'gh label create "{name}" --color {color} --description "{description}" --force'
        )
    except subprocess.CalledProcessError:
        pass  # Label may already exist


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    force = os.environ.get("FORCE_SYNC", "false").lower() == "true"

    # Step 0: Validate environment
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("❌ ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    # Step 1: Check for upstream changes
    print("📡 Checking upstream for changes...")
    state = load_sync_state()
    last_sha = state["last_synced_sha"]
    head_sha = get_upstream_head()

    print(f"  Last synced: {last_sha[:7]}")
    print(f"  Upstream HEAD: {head_sha[:7]}")

    if head_sha == last_sha and not force:
        print("✅ No upstream changes detected. Exiting.")
        return

    if force:
        print("  ⚡ Force sync requested — proceeding regardless.")

    # Step 2: Get changed files
    print("\n📋 Getting changed files...")
    changed_files = get_changed_files(last_sha, head_sha)

    translatable = [f for f in changed_files if should_translate(f["filename"])]
    skipped = [f for f in changed_files if not should_translate(f["filename"])]

    if not translatable:
        print("  No translatable markdown files changed. Updating sync state only.")
        # Still update state so we don't re-check these commits
        from datetime import datetime, timezone

        state["last_synced_sha"] = head_sha
        state["last_synced_at"] = datetime.now(timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        save_sync_state(state)
        run("git add .github/sync-state.json")
        run('git commit -m "chore: update sync state (no translatable changes)"')
        run("git push origin main")
        return

    print(f"  {len(translatable)} files to translate, {len(skipped)} skipped")
    for f in translatable:
        print(f"    📄 {f['filename']} ({f['status']})")

    # Step 3: Translate each file
    print("\n🔄 Translating files...")
    client = anthropic.Anthropic(api_key=api_key)
    guidelines = load_translation_guidelines()

    branch_name = f"sync/upstream-{head_sha[:7]}"
    create_branch(branch_name)

    translated = []
    failed = []

    for file_info in translatable:
        filename = file_info["filename"]
        status = file_info["status"]
        print(f"\n  📝 Translating {filename} ({status})...")

        # Get the new English content
        english_content = get_upstream_file_content(filename, head_sha)
        if not english_content:
            print(f"    ⚠️ Could not fetch upstream content for {filename}")
            failed.append(
                {"filename": filename, "reason": "Could not fetch upstream content"}
            )
            continue

        # Get current Korean translation (if exists)
        korean_content = None
        local_path = Path(filename)
        if local_path.exists():
            korean_content = local_path.read_text(encoding="utf-8")

        # Translate
        result = translate_file(
            client, guidelines, english_content, korean_content, filename
        )
        if result is None:
            failed.append({"filename": filename, "reason": "Anthropic API error"})
            continue

        # Write the translated file
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_text(result, encoding="utf-8")
        translated.append(filename)
        print(f"    ✅ {filename} translated successfully")

    if not translated:
        print("\n❌ All translations failed. Aborting.")
        run(f"git checkout main")
        run(f"git branch -D {branch_name}", check=False)
        sys.exit(1)

    # Step 4: Commit, push, create PR
    print("\n📦 Committing changes...")
    commit_all(f"번역 동기화: upstream {head_sha[:7]}")

    # Update sync state
    from datetime import datetime, timezone

    state["last_synced_sha"] = head_sha
    state["last_synced_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    save_sync_state(state)
    run("git add .github/sync-state.json")
    run(f'git commit -m "chore: update sync state to {head_sha[:7]}"')

    print(f"\n🚀 Pushing branch {branch_name}...")
    push_branch(branch_name)

    # Build PR body
    print("\n📝 Creating PR...")
    commits = get_commits_between(last_sha, head_sha)
    ensure_label("auto-translation", "0E8A16", "자동 번역 PR")

    commit_list = "\n".join(
        f"- [`{c['sha']}`](https://github.com/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/commit/{c['sha']}) "
        f"{c['message'].split(chr(10))[0]} — {c['author']}"
        for c in commits
    )

    translated_list = "\n".join(f"- ✅ `{f}`" for f in translated)
    failed_list = "\n".join(f"- ❌ `{f['filename']}`: {f['reason']}" for f in failed)
    skipped_list = "\n".join(f"- ⏭️ `{f['filename']}`" for f in skipped)

    body = f"""## 📡 Upstream 동기화

### 포함된 upstream 커밋
{commit_list if commit_list else "- (커밋 정보를 가져올 수 없음)"}

### 번역된 파일
{translated_list}

"""
    if failed:
        body += f"""### ❌ 번역 실패
{failed_list}

> ⚠️ 일부 파일의 번역이 실패했습니다. 이 PR은 수동 리뷰가 필요합니다.

"""
    if skipped:
        body += f"""### ⏭️ 건너뛴 파일
{skipped_list}

"""
    body += f"""---
⚡ 이 PR은 자동 번역 시스템에 의해 생성되었습니다.
📖 동기화 범위: `{last_sha[:7]}` → `{head_sha[:7]}`"""

    # Create the short description from commits
    if commits:
        first_msg = commits[0]["message"].split("\n")[0][:60]
        title = f"[자동번역] Upstream 동기화: {first_msg}"
    else:
        title = f"[자동번역] Upstream 동기화: {last_sha[:7]}..{head_sha[:7]}"

    pr_url = create_pr(title, body, branch_name)
    print(f"  ✅ PR created: {pr_url}")

    # Add label
    try:
        run(f'gh pr edit {pr_url} --add-label "auto-translation"')
    except subprocess.CalledProcessError:
        pass

    # Auto-merge only if ALL translations succeeded
    if not failed:
        print("\n🔀 Auto-merging PR...")
        if merge_pr(pr_url):
            print("  ✅ PR merged successfully!")
        else:
            print("  ⚠️ Auto-merge failed. PR left open for manual review.")
    else:
        print("\n⚠️ Some translations failed. PR left open for manual review.")

    print("\n🎉 Done!")


if __name__ == "__main__":
    main()
