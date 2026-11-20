#!/bin/bash
set -euo pipefail
[[ "$DEPLOY_VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]
base=/opt/to-do-list
release="$base/releases/$DEPLOY_VERSION-$(date +%s)"
previous=$(readlink -f "$base/current")
tempzip=$(mktemp /tmp/todo-release.XXXXXX.zip)
cleanup() { rm -f "$tempzip"; }
trap cleanup EXIT
curl --fail --location --retry 4 --max-time 120 "$DOWNLOAD_URL" --output "$tempzip"
echo "$EXPECTED_SHA  $tempzip" | sha256sum --check -
mkdir -p "$release"
python3.11 - "$tempzip" "$release" <<'PY'
import pathlib, sys, zipfile
target = pathlib.Path(sys.argv[2]).resolve()
with zipfile.ZipFile(sys.argv[1]) as archive:
    for member in archive.infolist():
        if not pathlib.Path(target / member.filename).resolve().is_relative_to(target):
            raise ValueError("Unsafe ZIP path")
    archive.extractall(target)
PY
test "$(tr -d '\r\n' < "$release/VERSION")" = "$DEPLOY_VERSION"
python3.11 -m venv "$release/.venv"
"$release/.venv/bin/pip" install --quiet --no-cache-dir -r "$release/src/requirements.txt"
chown -R todo:todo "$release"
ln -s "$release" "$base/current.next"
mv -Tf "$base/current.next" "$base/current"
systemctl restart to-do-list
for attempt in $(seq 1 30); do
  if curl --fail --silent --max-time 10 http://127.0.0.1:8000/health > /tmp/todo-health.json &&
     python3.11 -c 'import json,os; d=json.load(open("/tmp/todo-health.json")); assert d["database"] == "connected" and d["version"] == os.environ["DEPLOY_VERSION"]'; then
    cat /tmp/todo-health.json
    echo
    echo "Successfully deployed $DEPLOY_VERSION"
    exit 0
  fi
  sleep 5
done
echo "Health verification failed; restoring $previous" >&2
ln -s "$previous" "$base/current.rollback"
mv -Tf "$base/current.rollback" "$base/current"
systemctl restart to-do-list
exit 1
