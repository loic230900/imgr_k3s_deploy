#!/usr/bin/env bash
# Handover snapshot. Captures live deployment intent and secret metadata only.
# Tries vm1 then vm2 then vm3 so it survives single-node loss.
set -euo pipefail

OUT="cluster-info-$(date +%F).yml"
SSH_OPTS=(-o StrictHostKeyChecking=no -o ConnectTimeout=5 -o BatchMode=yes)
VMS=(vm1 vm2 vm3)

# Pick the first VM that answers kubectl
HOST=""
for VM in "${VMS[@]}"; do
  if ssh "${SSH_OPTS[@]}" "$VM" 'sudo k3s kubectl get nodes -o name' >/dev/null 2>&1; then
    HOST="$VM"; break
  fi
done
if [ -z "$HOST" ]; then
  echo "ERROR: no VM responded to kubectl" >&2
  exit 1
fi

{
  echo "# Cluster info snapshot"
  echo "# generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "# host: $(hostname)"
  echo "# read from: $HOST"
  echo "---"
  echo "## Nodes"
  ssh "${SSH_OPTS[@]}" "$HOST" 'sudo k3s kubectl get nodes -o wide'
  echo
  echo "## Workloads, services, PDBs, HPAs, NetworkPolicies (imgr)"
  ssh "${SSH_OPTS[@]}" "$HOST" 'sudo k3s kubectl -n imgr get deploy,statefulset,daemonset,svc,pdb,hpa,netpol -o yaml'
  echo
  echo "## Secrets (metadata only, no data)"
  ssh "${SSH_OPTS[@]}" "$HOST" \
    "sudo k3s kubectl -n imgr get secrets -o jsonpath='{range .items[*]}- name: {.metadata.name}{\"\\n\"}  type: {.type}{\"\\n\"}{end}'"
} > "$OUT"

echo "Wrote $OUT ($(wc -l < "$OUT") lines, read from $HOST)"
