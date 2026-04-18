#!/usr/bin/env bash
# Install paper-search skill into the current user's Claude Code setup.
# - Creates a local .venv and installs requirements.txt
# - Symlinks this repo into ~/.claude/skills/paper-search
# - Runs the test suite to verify the install

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="paper-search"
SKILLS_DIR="${HOME}/.claude/skills"
LINK_PATH="${SKILLS_DIR}/${SKILL_NAME}"

echo "==> Repo root: ${REPO_ROOT}"

if [[ ! -f "${REPO_ROOT}/SKILL.md" ]]; then
  echo "ERROR: SKILL.md not found at ${REPO_ROOT}. Run this script from the repo root." >&2
  exit 1
fi

# 1. Python venv
if [[ ! -d "${REPO_ROOT}/.venv" ]]; then
  echo "==> Creating virtualenv at .venv"
  python3 -m venv "${REPO_ROOT}/.venv"
fi

echo "==> Installing runtime dependencies"
# shellcheck disable=SC1091
source "${REPO_ROOT}/.venv/bin/activate"
pip install --quiet --upgrade pip
pip install --quiet -r "${REPO_ROOT}/requirements.txt"

# 2. Symlink into ~/.claude/skills/
mkdir -p "${SKILLS_DIR}"
if [[ -L "${LINK_PATH}" ]]; then
  existing="$(readlink "${LINK_PATH}")"
  if [[ "${existing}" != "${REPO_ROOT}" ]]; then
    echo "==> Replacing existing symlink (was pointing to ${existing})"
    rm "${LINK_PATH}"
  fi
fi
if [[ -e "${LINK_PATH}" && ! -L "${LINK_PATH}" ]]; then
  echo "ERROR: ${LINK_PATH} exists and is not a symlink. Move it aside and re-run." >&2
  exit 1
fi
if [[ ! -L "${LINK_PATH}" ]]; then
  echo "==> Linking ${LINK_PATH} -> ${REPO_ROOT}"
  ln -s "${REPO_ROOT}" "${LINK_PATH}"
else
  echo "==> Symlink already correct"
fi

# 3. Sanity check
echo "==> Running tests"
pip install --quiet -r "${REPO_ROOT}/requirements-dev.txt"
(cd "${REPO_ROOT}" && pytest --quiet)

cat <<'EOF'

==> Install complete.

Next steps:
  1. (Optional) export OPENREVIEW_USERNAME and OPENREVIEW_PASSWORD
     in the shell you launch Claude Code from.
  2. Start a fresh Claude Code session in any project directory.
  3. Invoke `/paper-search` (or ask in natural language).

EOF
