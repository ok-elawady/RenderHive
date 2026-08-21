from __future__ import absolute_import

import base64
import ctypes
import os

try:
    from ctypes import wintypes
except ImportError:
    wintypes = None


class CredentialStorageError(RuntimeError):
    pass


_CREDENTIAL_FILE = "api_token.bin"
_CRYPTPROTECT_UI_FORBIDDEN = 0x01


def _local_root():
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return os.path.join(root, "RenderHive")
    return os.path.join(os.path.expanduser("~"), ".renderhive")


def get_credential_path():
    return os.path.join(_local_root(), _CREDENTIAL_FILE)


def _windows_dpapi_available():
    return (
        os.name == "nt"
        and wintypes is not None
        and hasattr(ctypes, "windll")
        and hasattr(ctypes.windll, "crypt32")
    )


if wintypes is not None:
    class _DATA_BLOB(ctypes.Structure):
        _fields_ = [
            ("cbData", wintypes.DWORD),
            ("pbData", ctypes.POINTER(ctypes.c_byte)),
        ]
else:
    _DATA_BLOB = None


def _blob_from_bytes(data):
    buffer_value = ctypes.create_string_buffer(data)
    blob = _DATA_BLOB(
        len(data),
        ctypes.cast(buffer_value, ctypes.POINTER(ctypes.c_byte)),
    )
    return blob, buffer_value


def _unprotect_windows(data):
    input_blob, input_buffer = _blob_from_bytes(data)
    output_blob = _DATA_BLOB()
    result = ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )
    if not result:
        raise CredentialStorageError("Windows DPAPI could not decrypt the stored API token.")
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(output_blob.pbData)
        del input_buffer


def load_token():
    path = get_credential_path()
    if not os.path.isfile(path):
        return ""
    try:
        with open(path, "rb") as handle:
            encoded = handle.read()
        header, payload = encoded.split(b"\n", 1)
        raw = base64.b64decode(payload)
        if header == b"DPAPI1":
            if not _windows_dpapi_available():
                raise CredentialStorageError(
                    "The API token is protected by Windows DPAPI and is unavailable on this OS."
                )
            raw = _unprotect_windows(raw)
        elif header != b"PLAIN1":
            raise CredentialStorageError("Stored API credential format is not recognized.")
        return raw.decode("utf-8")
    except CredentialStorageError:
        raise
    except Exception as error:
        raise CredentialStorageError("Could not read the stored API token: {}".format(error))
