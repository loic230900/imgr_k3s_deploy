#!/bin/sh
curl -sk --max-time 2 https://127.0.0.1:6443/readyz >/dev/null 2>&1 || exit 1
exit 0
