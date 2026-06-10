#!/usr/bin/bash
#
# MIT License
#
# Copyright (c) by Dan Luca. All rights reserved.
#
#
# trim_services.sh - reversibly disable systemd services that are not useful
# for a headless, network-connected irrigation controller (Raspberry Pi Zero 2 W).
#
# Usage:
#   sudo ./trim_services.sh disable   # disable & stop the non-essential services
#   sudo ./trim_services.sh enable    # restore (re-enable & start) everything
#   sudo ./trim_services.sh status    # show current state of the affected units
#
# Notes:
#   - cloud-init only does first-boot provisioning; it is gated by
#     /etc/cloud/cloud-init.disabled in addition to disabling its units.
#   - avahi-daemon (mDNS / *.local name resolution) is OFF by default in this
#     script. Set TRIM_AVAHI=true below ONLY if you SSH in by IP address.
#   - udisks2 handles hot-plugged media automount; it does NOT mount the
#     microSD root filesystem (that is done at boot via /etc/fstab).
#

set -euo pipefail

# Flip to true only if you never connect via hostname.local (i.e. you use an IP).
TRIM_AVAHI=${TRIM_AVAHI:-false}

# Services safe to disable on a headless irrigation controller.
SERVICES=(
  cloud-config.service
  cloud-final.service
  cloud-init-local.service
  cloud-init-main.service
  cloud-init-network.service
  console-setup.service
  keyboard-setup.service
  systemd-pstore.service
  udisks2.service
)

if [[ "$TRIM_AVAHI" == "true" ]]; then
  SERVICES+=(avahi-daemon.service)
fi

CLOUD_INIT_FLAG=/etc/cloud/cloud-init.disabled

require_root() {
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "This script must be run as root (use sudo)." >&2
    exit 1
  fi
}

do_disable() {
  echo "Gating cloud-init via $CLOUD_INIT_FLAG ..."
  touch "$CLOUD_INIT_FLAG"

  echo "Disabling and stopping non-essential services ..."
  for svc in "${SERVICES[@]}"; do
    if systemctl list-unit-files "$svc" >/dev/null 2>&1; then
      echo "  - $svc"
      systemctl disable --now "$svc" 2>/dev/null || true
    else
      echo "  - $svc (not present, skipping)"
    fi
  done
  echo "Done. Review boot cost with: systemd-analyze blame | head -20"
}

do_enable() {
  echo "Removing cloud-init gate $CLOUD_INIT_FLAG ..."
  rm -f "$CLOUD_INIT_FLAG"

  echo "Re-enabling and starting services ..."
  for svc in "${SERVICES[@]}"; do
    if systemctl list-unit-files "$svc" >/dev/null 2>&1; then
      echo "  - $svc"
      systemctl enable --now "$svc" 2>/dev/null || true
    else
      echo "  - $svc (not present, skipping)"
    fi
  done
  echo "Done."
}

do_status() {
  for svc in "${SERVICES[@]}"; do
    state=$(systemctl is-enabled "$svc" 2>/dev/null || echo "n/a")
    active=$(systemctl is-active "$svc" 2>/dev/null || echo "n/a")
    printf "  %-32s enabled=%-10s active=%s\n" "$svc" "$state" "$active"
  done
  if [[ -f "$CLOUD_INIT_FLAG" ]]; then
    echo "  cloud-init: DISABLED (flag present: $CLOUD_INIT_FLAG)"
  else
    echo "  cloud-init: enabled (no flag file)"
  fi
}

main() {
  local action="${1:-}"
  case "$action" in
    disable) require_root; do_disable ;;
    enable)  require_root; do_enable ;;
    status)  do_status ;;
    *)
      echo "Usage: sudo $0 {disable|enable|status}" >&2
      exit 1
      ;;
  esac
}

main "$@"