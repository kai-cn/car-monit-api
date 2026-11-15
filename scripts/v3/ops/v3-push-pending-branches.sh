#!/usr/bin/env bash
# Retry pushing the six native-image branches until every local commit is on origin.
# Windows Git's schannel backend drops connections through this host's proxy;
# `-c http.sslBackend=openssl` plus bounded retries is the verified workaround.
# Never force-pushes, never rebases, never creates branches.
set -uo pipefail

ROOT="/d/work/IdeaProjects"
MAX=12
BRANCHES=(car-monit-api-jdk17 car-monit-api-jdk21 car-monit-api-jdk25
          car-monit-backend-jdk17 car-monit-backend-jdk21 car-monit-backend-jdk25)

for d in "${BRANCHES[@]}"; do
  D="$ROOT/$d"
  branch=$(git -C "$D" branch --show-current)
  ahead=$(git -C "$D" rev-list --count "origin/$branch..$branch" 2>/dev/null || echo "?")
  echo "==== $d ($branch) commits_ahead=$ahead ===="
  if [[ "$ahead" == "0" ]]; then echo "  already up to date"; continue; fi
  ok=0
  # schannel drops the connection through the proxy ("server closed abruptly"),
  # openssl may lack a CA bundle ("unable to get local issuer certificate").
  # Alternate both backends; whichever succeeds on this attempt wins.
  for i in $(seq 1 "$MAX"); do
    for be in schannel openssl; do
      if git -C "$D" -c http.sslBackend=$be push origin "$branch" >/dev/null 2>&1; then
        echo "  PUSHED backend=$be attempt=$i"; ok=1; break
      fi
    done
    [[ "$ok" == "1" ]] && break
    sleep 4
  done
  [[ "$ok" == "0" ]] && echo "  STILL_PENDING after $MAX attempts"
done
echo "PUSH_RETRY_DONE"
