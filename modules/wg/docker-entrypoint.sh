#!/bin/sh
# Runs as root (that's the point): /data is a bind mount, so its ownership
# comes from whatever created it on the host - often root, which the
# unprivileged `wg` user the app actually runs as can't write to. Fixing
# it here means a fresh VPS/clone never needs a manual `chown` on the host.
set -e
chown -R wg:wg /data
exec su -s /bin/sh -c "$*" wg
