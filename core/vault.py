"""
core/vault.py
─────────────
Password-protected storage for sensitive clipboard items.

Encryption
──────────
AES-256-CBC + HMAC-SHA256 via pycryptodome (required, in requirements.txt).
Key derivation: PBKDF2-HMAC-SHA256, 600 000 iterations.

PIN
────
The PIN is never stored. A random 16-byte salt + PBKDF2-HMAC-SHA256
verifier hash is stored in config.json.
"""

import hashlib
import hmac
import importlib
import logging
import secrets

from utils.config_manager import cfg as _cfg

logger = logging.getLogger(__name__)

_ITERATIONS = 600_000
_SALT_LEN   = 16
_KEY_LEN    = 32   # AES-256


def _load_crypto() -> tuple[object, object, object]:
    """
    Import the AES cipher and PKCS#7 padding helpers.

    Prefer ``pycryptodome``'s ``Crypto`` package, but also accept
    ``pycryptodomex`` installations that expose ``Cryptodome``.
    """
    candidates = (
        ("Crypto.Cipher.AES", "Crypto.Util.Padding"),
        ("Cryptodome.Cipher.AES", "Cryptodome.Util.Padding"),
    )

    for aes_mod, padding_mod in candidates:
        try:
            aes = importlib.import_module(aes_mod)
            padding = importlib.import_module(padding_mod)
            return aes, padding.pad, padding.unpad
        except ModuleNotFoundError:
            continue

    raise RuntimeError(
        "Locked Notes encryption is unavailable. Install pycryptodome."
    )


# ── Key derivation ────────────────────────────────────────────────────────────

def _derive_key(pin: str, salt: bytes) -> bytes:
    return hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        salt,
        _ITERATIONS,
        dklen=_KEY_LEN,
    )

# ── Encryption: AES-256-CBC + HMAC-SHA256 (requires pycryptodome) ─────────────

def _encrypt(plaintext: bytes, key: bytes) -> bytes:
    """
    Returns:  IV(16) + AES-256-CBC(plaintext) + HMAC-SHA256(IV+ciphertext, key)(32)
    Requires: pycryptodome  (listed in requirements.txt)
    """
    AES, pad, _ = _load_crypto()
    iv     = secrets.token_bytes(16)
    cipher = AES.new(key, AES.MODE_CBC, iv)
    ct     = cipher.encrypt(pad(plaintext, AES.block_size))
    payload = iv + ct
    mac     = hmac.new(key, payload, hashlib.sha256).digest()
    return payload + mac


def _decrypt(blob: bytes, key: bytes) -> bytes:
    """Inverse of _encrypt. Raises ValueError on wrong PIN or corrupted data."""
    AES, _, unpad = _load_crypto()

    if len(blob) < 16 + 32:
        raise ValueError("Blob too short")

    payload, mac_stored = blob[:-32], blob[-32:]
    mac_calc = hmac.new(key, payload, hashlib.sha256).digest()
    if not hmac.compare_digest(mac_calc, mac_stored):
        raise ValueError("HMAC mismatch — wrong PIN or corrupted data")

    iv, ct = payload[:16], payload[16:]
    cipher = AES.new(key, AES.MODE_CBC, iv)
    return unpad(cipher.decrypt(ct), AES.block_size)


# ── PIN management ────────────────────────────────────────────────────────────

class VaultManager:
    """
    High-level interface for the encrypted vault.

    Usage
    -----
    vm = VaultManager(db)
    vm.setup_pin("mysecret")        # first-time setup
    vm.unlock("mysecret")           # subsequent opens
    vm.add_item("my password", "label")
    items = vm.get_items()
    vm.lock()
    """

    def __init__(self, db) -> None:
        self._db  = db
        self._key: bytes | None = None   # in-memory session key

    # ── PIN ───────────────────────────────────────────────────────────────────

    def has_pin(self) -> bool:
        return bool(_cfg.get("vault_salt") and _cfg.get("vault_verifier"))

    def setup_pin(self, pin: str) -> None:
        """Set or change the vault PIN.  Re-encrypts existing items."""
        old_key = self._key   # may be None if first setup
        salt    = secrets.token_bytes(_SALT_LEN)
        new_key = _derive_key(pin, salt)

        # Re-encrypt all existing vault items with the new key
        if old_key is not None:
            items = self._db.get_vault_items_raw()
            for item in items:
                try:
                    plain = _decrypt(item["content_enc"], old_key)
                    new_enc = _encrypt(plain, new_key)
                    self._db.update_vault_item_enc(item["id"], new_enc)
                except Exception as exc:
                    logger.warning("Re-encrypt vault item %s failed: %s", item["id"], exc)

        # Store salt + verifier (PBKDF2 of known sentinel)
        verifier = _derive_key("__veilclip_vault_verify__" + pin, salt).hex()
        _cfg.update({
            "vault_salt":     salt.hex(),
            "vault_verifier": verifier,
        })
        self._key = new_key
        logger.info("Vault PIN configured.")

    def verify_pin(self, pin: str) -> bool:
        salt_hex = _cfg.get("vault_salt", "")
        expected = _cfg.get("vault_verifier", "")
        if not salt_hex or not expected:
            return False
        salt   = bytes.fromhex(salt_hex)
        actual = _derive_key("__veilclip_vault_verify__" + pin, salt).hex()
        return hmac.compare_digest(actual, expected)

    def unlock(self, pin: str) -> bool:
        """Derive and store the session key.  Returns True on success."""
        if not self.verify_pin(pin):
            return False
        salt = bytes.fromhex(_cfg.get("vault_salt", ""))
        self._key = _derive_key(pin, salt)
        logger.info("Vault unlocked.")
        return True

    def lock(self) -> None:
        self._key = None
        logger.info("Vault locked.")

    def is_unlocked(self) -> bool:
        return self._key is not None

    # ── Items ─────────────────────────────────────────────────────────────────

    def add_item(self, plaintext: str, label: str = "") -> int | None:
        """Encrypt and store a vault item.  Returns new id or None."""
        if not self.is_unlocked():
            raise RuntimeError("Vault is locked")
        enc = _encrypt(plaintext.encode("utf-8"), self._key)
        return self._db.add_vault_item(enc, label)

    def get_items(self) -> list[dict]:
        """
        Return decrypted vault items.
        Each dict: {id, label, plaintext, created_at}
        Items that fail to decrypt are skipped (wrong key guard).
        """
        if not self.is_unlocked():
            raise RuntimeError("Vault is locked")
        raw   = self._db.get_vault_items_raw()
        result = []
        for item in raw:
            try:
                plain = _decrypt(item["content_enc"], self._key).decode("utf-8")
                result.append({
                    "id":         item["id"],
                    "label":      item.get("label", ""),
                    "plaintext":  plain,
                    "created_at": item.get("created_at", ""),
                })
            except Exception as exc:
                logger.warning("Vault item %s decrypt failed: %s", item["id"], exc)
        return result

    def delete_item(self, vault_id: int) -> bool:
        return self._db.delete_vault_item(vault_id)

    def update_label(self, vault_id: int, label: str) -> bool:
        return self._db.update_vault_item_label(vault_id, label)
