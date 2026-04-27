#!/usr/bin/env bash
# Operator health probe. Exit 0 when cluster is sane, non-zero on anomaly.
# Tries vm1 then vm2 then vm3 for kubectl ops so it survives single-node loss.
set -euo pipefail

VMS=(vm1 vm2 vm3)
SSH_OPTS=(-o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes)
FAILURES=0

step() { printf '\n=== %s ===\n' "$*"; }
fail() { printf '  [FAIL] %s\n' "$*"; FAILURES=$((FAILURES + 1)); }
ok()   { printf '  [ OK ] %s\n' "$*"; }

# Pick the first VM that answers kubectl. If none does, the cluster is dead.
KCTL_HOST=""
for VM in "${VMS[@]}"; do
  if ssh "${SSH_OPTS[@]}" "$VM" 'sudo k3s kubectl get nodes --no-headers' >/dev/null 2>&1; then
    KCTL_HOST="$VM"; break
  fi
done
if [ -z "$KCTL_HOST" ]; then
  printf '  [FAIL] No VM responded to kubectl, cluster appears down\n'
  exit 1
fi
printf 'Using %s for kubectl ops\n' "$KCTL_HOST"

step "1/4 K3s nodes (expect 3 Ready)"
NODES_RAW=$(ssh "${SSH_OPTS[@]}" "$KCTL_HOST" 'sudo k3s kubectl get nodes --no-headers')
echo "$NODES_RAW"
READY=$(echo "$NODES_RAW" | awk '$2=="Ready"' | wc -l)
[ "$READY" -eq 3 ] && ok "3/3 nodes Ready" || fail "$READY/3 nodes Ready"

step "2/4 imgr pods (expect 6 Running)"
PODS_RAW=$(ssh "${SSH_OPTS[@]}" "$KCTL_HOST" 'sudo k3s kubectl -n imgr get pods --no-headers')
echo "$PODS_RAW"
RUNNING=$(echo "$PODS_RAW" | awk '$3=="Running"' | wc -l)
[ "$RUNNING" -ge 6 ] && ok "$RUNNING pods Running (>=6)" || fail "$RUNNING pods Running, expected >=6"

step "3/4 Floating IP 192.168.27.110 (expect on exactly one VM)"
HOLDERS=()
for VM in "${VMS[@]}"; do
  if ssh "${SSH_OPTS[@]}" "$VM" 'ip addr show | grep -q 192.168.27.110/' 2>/dev/null; then
    HOLDERS+=("$VM"); ok "VIP on $VM"
  fi
done
case "${#HOLDERS[@]}" in
  1) ok "VIP held by exactly one node" ;;
  0) fail "No node holds the floating IP" ;;
  *) fail "Split-brain: VIP on multiple nodes (${HOLDERS[*]})" ;;
esac

step "4/4 /health from each VM"
for VM in "${VMS[@]}"; do
  if BODY=$(ssh "${SSH_OPTS[@]}" "$VM" 'curl -fsS --max-time 5 http://localhost:8080/health' 2>/dev/null); then
    echo "  $VM => $BODY"
    ok "$VM /health responding"
  else
    fail "$VM /health unreachable"
  fi
done

step "Result"
if [ "$FAILURES" -eq 0 ]; then
  ok "Cluster healthy"; exit 0
else
  fail "$FAILURES check(s) failed"; exit 1
fi
