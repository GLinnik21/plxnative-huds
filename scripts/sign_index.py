"""Sign the staged catalog index. The only code that ever sees the publisher's private key.

`index.signed` is one file in two parts, so the signature and the bytes it covers can never come
from different deploys: a compact JSON header line `{"format":1,"key":"<id>","sig":"<hex>"}` and
a newline, then the exact bytes of `index.json`. `sig` is pure Ed25519 (RFC 8032, no prehash,
context or prefix) over those bytes; `key` is the first 16 hex of SHA-256 over the signer's raw
32-byte public key. `keys.json` lists the two accepted public keys the app compiles in.

The key arrives as PKCS#8 PEM in the environment variable below and goes straight into memory:
it is never echoed, never written to a file and never passed to a child process. The causes in the
messages (`malformed`, `unknown-key`, `bad-signature`, `index`, `no-serial`) are the app's own.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature, UnsupportedAlgorithm
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat, load_pem_private_key

from catalog import Invalid, read_json, unique_object

SECRET = "HUD_INDEX_ED25519_KEY"
KEYS = Path(__file__).resolve().parents[1] / "keys.json"
HEADER_LIMIT = 256
ROLES = ("primary", "standby")


class Refused(Invalid):
    """Nothing is signed, written or deployed."""


def key_id(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()[:16]


def load_keys(path: Path) -> list[dict]:
    """The accepted public keys: exactly one primary and one standby, each id derived from its key."""
    value = read_json(path)
    if not isinstance(value, dict) or set(value) != {"format", "keys"} or value["format"] != 1 or type(value["format"]) is not int:
        raise Refused("keys: keys.json must be an object with exactly format 1 and keys")
    keys = value["keys"]
    if not isinstance(keys, list) or [entry.get("role") if isinstance(entry, dict) else None for entry in keys] != list(ROLES):
        raise Refused("keys: keys.json needs exactly the primary key, then the standby key")
    for entry in keys:
        if set(entry) != {"role", "id", "hex"} or not all(isinstance(entry[name], str) for name in entry):
            raise Refused("keys: each key has exactly role, id and hex")
        if not re.fullmatch("[0-9a-f]{64}", entry["hex"]):
            raise Refused(f"keys: the {entry['role']} key is not 32 lower-case hex bytes")
        if entry["id"] != key_id(bytes.fromhex(entry["hex"])):
            raise Refused(f"keys: the {entry['role']} id is not the first 16 hex of SHA-256 over its key")
    if len({entry["hex"] for entry in keys}) != 2:
        raise Refused("keys: the primary and standby keys must differ")
    return keys


def private_key(pem: bytes) -> Ed25519PrivateKey:
    try:
        key = load_pem_private_key(pem, password=None)
    except (ValueError, TypeError, UnsupportedAlgorithm):
        # Deliberately no chained cause: nothing derived from the secret reaches a log.
        raise Refused("key: the signing secret is not an unencrypted PEM private key") from None
    if not isinstance(key, Ed25519PrivateKey):
        raise Refused("key: the signing secret is not an Ed25519 key")
    return key


def public_raw(key: Ed25519PrivateKey) -> bytes:
    return key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)


def accepted(keys: list[dict], raw: bytes) -> dict:
    for entry in keys:
        if entry["hex"] == raw.hex():
            return entry
    raise Refused(f"unknown-key: the signing key {key_id(raw)} is not in keys.json; refusing to sign")


def parse_index(data: bytes) -> int:
    """The part of the app's acceptance the publisher can check: it parses, and it carries a serial."""
    try:
        index = json.loads(data.decode("utf-8"), object_pairs_hook=unique_object)
    except ValueError as exc:  # UnicodeError, JSONDecodeError and a duplicate key
        raise Refused(f"index: not UTF-8 JSON ({exc})") from None
    if not isinstance(index, dict):
        raise Refused("index: the index is not a JSON object")
    serial = index.get("serial")
    if type(serial) is not int or not 0 <= serial < 2 ** 53:
        raise Refused("no-serial: the index has no unsigned integer serial")
    return serial


def assemble(entry_id: str, signature: bytes, data: bytes) -> bytes:
    header = json.dumps({"format": 1, "key": entry_id, "sig": signature.hex()}, separators=(",", ":"))
    return header.encode() + b"\n" + data


def split(signed: bytes) -> tuple[dict, bytes]:
    """The strict header parse every verifier performs first."""
    line, newline, data = signed.partition(b"\n")
    if not newline or len(line) > HEADER_LIMIT:
        raise Refused("malformed: no header line of at most 256 bytes")
    try:
        header = json.loads(line.decode("utf-8"), object_pairs_hook=unique_object)
    except ValueError:
        raise Refused("malformed: the header is not UTF-8 JSON") from None
    if (not isinstance(header, dict) or set(header) != {"format", "key", "sig"} or type(header["format"]) is not int
            or header["format"] != 1 or not isinstance(header["key"], str) or not re.fullmatch("[0-9a-f]{16}", header["key"])
            or not isinstance(header["sig"], str) or not re.fullmatch("[0-9a-f]{128}", header["sig"])):
        raise Refused("malformed: the header needs exactly format 1, a 16-hex key and a 128-hex sig")
    if line != json.dumps({"format": 1, "key": header["key"], "sig": header["sig"]}, separators=(",", ":")).encode():
        raise Refused("malformed: the header is not compact, or its keys are out of order")
    return header, data


def verify_signed(signed: bytes, keys: list[dict]) -> tuple[dict, int]:
    """The app's acceptance order, as far as the publisher can follow it. Returns the key and the serial."""
    header, data = split(signed)
    entry = next((candidate for candidate in keys if candidate["id"] == header["key"]), None)
    if entry is None:
        raise Refused(f"unknown-key: {header['key']} is not an accepted key")
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(entry["hex"])).verify(bytes.fromhex(header["sig"]), data)
    except InvalidSignature:
        raise Refused("bad-signature: the signature does not cover these index bytes") from None
    return entry, parse_index(data)


def sign_site(site: Path, keys_path: Path, pem: bytes) -> Path:
    """Write `site/index.signed` from the one buffer read out of `site/index.json`, then re-verify it."""
    keys = load_keys(keys_path)
    key = private_key(pem)
    entry = accepted(keys, public_raw(key))
    index_path = site / "index.json"
    if index_path.is_symlink() or not index_path.is_file():
        raise Refused("index: index.json must be a regular file (not a symlink)")
    data = index_path.read_bytes()
    parse_index(data)
    staged = site / "index.signed.tmp"
    try:
        staged.write_bytes(assemble(entry["id"], key.sign(data), data))
        written = staged.read_bytes()
        verify_signed(written, keys)
        if written.partition(b"\n")[2] != data or index_path.read_bytes() != data:
            raise Refused("index: index.json changed while it was being signed")
        target = site / "index.signed"
        staged.replace(target)
    finally:
        staged.unlink(missing_ok=True)
    return target


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("site", type=Path, help="the staged catalog directory holding index.json")
    parser.add_argument("--keys", type=Path, default=KEYS)
    args = parser.parse_args(argv)
    secret = os.environ.pop(SECRET, "").strip()
    if not secret:
        print(f"sign_index: {SECRET} is empty or unset; an unsigned index is never deployed", file=sys.stderr)
        return 1
    try:
        target = sign_site(args.site, args.keys, secret.encode())
        entry, serial = verify_signed(target.read_bytes(), load_keys(args.keys))
    except (Invalid, OSError) as exc:
        print(f"sign_index: {exc}", file=sys.stderr)
        return 1
    print(f"Signed index.json (serial {serial}) with the {entry['role']} key {entry['id']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
