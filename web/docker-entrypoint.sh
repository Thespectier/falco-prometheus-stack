#!/bin/sh
set -e

enabled="${ACCESS_CONTROL_ENABLED:-1}"

case "$enabled" in
  0|false|FALSE|False|no|NO|No)
    enabled_js="false"
    ;;
  *)
    enabled_js="true"
    ;;
esac

cat > /usr/share/nginx/html/runtime-config.js <<EOF
window.__APP_CONFIG__ = { authEnabled: ${enabled_js} };
EOF

exec "$@"
