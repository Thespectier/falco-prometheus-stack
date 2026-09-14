#!/bin/sh
set -e

# 前端在浏览器里读 window.__APP_CONFIG__ 决定是否走登录流程。这里把编排里的
# ACCESS_CONTROL_ENABLED 转成 JS 布尔值，在容器启动时写进静态目录——因此改这个
# 环境变量只要重启容器，不必重新构建镜像。
runtime_config_path=/usr/share/nginx/html/runtime-config.js

# 假值沿用既有的列举方式（编排里可能写成 0/false/no 的各种大小写）；未设置时按开启处理
is_access_control_enabled() {
  case "${ACCESS_CONTROL_ENABLED:-1}" in
    0|false|FALSE|False|no|NO|No)
      return 1
      ;;
    *)
      return 0
      ;;
  esac
}

if is_access_control_enabled; then
  auth_enabled=true
else
  auth_enabled=false
fi

cat > "$runtime_config_path" <<EOF
window.__APP_CONFIG__ = { authEnabled: ${auth_enabled} };
EOF

exec "$@"
