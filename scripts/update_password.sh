#!/bin/bash
HASH=$(htpasswd -bnBC 10 "" '你的新密码' | tr -d ':\n' | sed 's/^\$2y\$/$2b$/')
sqlite3 data/mynexus.db "UPDATE users SET password_hash='$HASH', updated_at=datetime('now') WHERE username='admin';"