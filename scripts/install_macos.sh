#!/usr/bin/env bash
# Install TUC system dependencies on macOS (Apple Silicon or Intel). Safe to run repeatedly.
set -euo pipefail

bold() { printf "\033[1m%s\033[0m\n" "$*"; }
ok()   { printf "  \033[32m✓\033[0m %s\n" "$*"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$*"; }
fail() { printf "  \033[31m✗\033[0m %s\n" "$*"; exit 1; }

[[ "$(uname -s)" == "Darwin" ]] || fail "This script is for macOS. See deploy/linux for Linux."

bold "1. Homebrew"
if ! command -v brew >/dev/null 2>&1; then
  for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [[ -x "$candidate" ]] && eval "$("$candidate" shellenv)" && break
  done
fi
if ! command -v brew >/dev/null 2>&1; then
  warn "Homebrew is not installed. Install it first, then re-run this script:"
  echo '    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  exit 1
fi
ok "brew $(brew --version | head -1 | awk '{print $2}') at $(brew --prefix) ($(uname -m))"

bold "2. Packages (mysql, tesseract, tesseract-lang, node, uv)"
for pkg in mysql tesseract tesseract-lang node uv; do
  if brew list --formula "$pkg" >/dev/null 2>&1; then
    ok "$pkg already installed"
  elif [[ "$pkg" == "mysql" ]] && brew list --formula | grep -q '^mysql@8'; then
    ok "mysql@8 already installed"
  else
    brew install "$pkg"
    ok "$pkg installed"
  fi
done

bold "3. MySQL service"
MYSQL_FORMULA=mysql
brew list --formula mysql >/dev/null 2>&1 || MYSQL_FORMULA="$(brew list --formula | grep '^mysql@8' | head -1)"
if brew services list | awk -v f="$MYSQL_FORMULA" '$1==f {print $2}' | grep -q started; then
  ok "$MYSQL_FORMULA already running"
else
  brew services start "$MYSQL_FORMULA"
  ok "$MYSQL_FORMULA started (brew services)"
fi
for _ in {1..20}; do
  mysqladmin ping --silent >/dev/null 2>&1 && break
  sleep 1
done
mysqladmin ping --silent >/dev/null 2>&1 && ok "MySQL answers ping" || warn "MySQL is not answering yet — check: brew services list"

bold "4. Tesseract languages"
LANGS="$(tesseract --list-langs 2>/dev/null | tail -n +2 || true)"
for lang in ara eng; do
  if grep -qx "$lang" <<<"$LANGS"; then ok "tesseract language '$lang' present"
  else fail "tesseract language '$lang' missing — run: brew reinstall tesseract-lang"; fi
done

bold "5. Next steps"
cat <<'NEXT'
  mysql -u root < scripts/setup_mysql.sql
  uv sync
  cp -n .env.example .env && chmod 600 .env     # then edit .env
  uv run python -m app.cli health-check
  uv run python -m app.cli init-db
NEXT
