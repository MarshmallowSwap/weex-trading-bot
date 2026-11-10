# WEEX private encrypted backup

This private repository contains an encrypted, complete snapshot of the local WEEX bot directory, including credentials, local databases, logs, virtual environment and configuration files. **The decryption key is not in GitHub**. Keep a secure offline copy of the key located on the original PC at `D:\FUNDSHOT_DATA\weex_github_backup_key_20261110.txt`.

The encryption format is AES-256-GCM (`WEEXAES1` header, 12-byte nonce, ciphertext, 16-byte authentication tag). Reassemble numbered `weex_backup.partNNN` files in order, decrypt using the key, and extract the ZIP on a trusted computer. The live trading gate is unchanged. Do not upload the key to this repo.
