from __future__ import absolute_import

import base64
import ctypes
import os
import sys

try:
    from ctypes import wintypes
except ImportError:
    wintypes = None


class CredentialStorageError(RuntimeError):
    pass


_CREDENTIAL_FILE = "api_token.bin"
_CRYPTPROTECT_UI_FORBIDDEN = 0x01


def _local_config_root():
    root = os.environ.get("LOCALAPPDATA")
    if root:
        return os.path.join(root, "RenderHive")
    return os.path.join(os.path.expanduser("~"), ".renderhive")


def get_credential_path():
    return os.path.join(_local_config_root(), _CREDENTIAL_FILE)


def _ensure_parent(path):
    folder = os.path.dirname(path)
    if not os.path.isdir(folder):
        os.makedirs(folder)


def _atomic_write(path, data):
    _ensure_parent(path)
    temp_path = path + ".tmp"
    with open(temp_path, "wb") as handle:
        handle.write(data)
        handle.flush()
        try:
            os.fsync(handle.fileno())
        except Exception:
            pass
    os.replace(temp_path, path)
    try:
        os.chmod(path, 0o600)
    except Exception:
        pass


def _delete_file(path):
    try:
        if os.path.isfile(path):
            os.remove(path)
    except Exception as error:
        raise CredentialStorageError(
            "Could not delete stored API token: {}".format(error)
        )


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


def _protect_windows(data):
    input_blob, input_buffer = _blob_from_bytes(data)
    output_blob = _DATA_BLOB()

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    result = crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "RenderHive API Token",
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )

    if not result:
        raise CredentialStorageError(
            "Windows DPAPI could not encrypt the API token."
        )

    try:
        return ctypes.string_at(
            output_blob.pbData,
            output_blob.cbData,
        )
    finally:
        kernel32.LocalFree(output_blob.pbData)
        del input_buffer


def _unprotect_windows(data):
    input_blob, input_buffer = _blob_from_bytes(data)
    output_blob = _DATA_BLOB()

    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32

    result = crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        _CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(output_blob),
    )

    if not result:
        raise CredentialStorageError(
            "Windows DPAPI could not decrypt the stored API token."
        )

    try:
        return ctypes.string_at(
            output_blob.pbData,
            output_blob.cbData,
        )
    finally:
        kernel32.LocalFree(output_blob.pbData)
        del input_buffer


def storage_mode():
    return "windows_dpapi" if _windows_dpapi_available() else "restricted_file"


def save_token(token):
    token = str(token or "")
    path = get_credential_path()

    if not token:
        _delete_file(path)
        return ""

    raw = token.encode("utf-8")

    if _windows_dpapi_available():
        encoded = b"DPAPI1\n" + base64.b64encode(
            _protect_windows(raw)
        )
    else:
        # Development fallback for non-Windows hosts. The production target is
        # Windows, where DPAPI is always used. The fallback file is separated
        # from config and restricted to the current OS account.
        encoded = b"PLAIN1\n" + base64.b64encode(raw)

    _atomic_write(path, encoded)
    return path


def load_token():
    path = get_credential_path()
    if not os.path.isfile(path):
        return ""

    try:
        with open(path, "rb") as handle:
            encoded = handle.read()
    except Exception as error:
        raise CredentialStorageError(
            "Could not read the stored API token: {}".format(error)
        )

    try:
        header, payload = encoded.split(b"\n", 1)
        raw = base64.b64decode(payload)

        if header == b"DPAPI1":
            if not _windows_dpapi_available():
                raise CredentialStorageError(
                    "This API token is protected by Windows DPAPI and cannot "
                    "be read on this operating system."
                )
            raw = _unprotect_windows(raw)
        elif header != b"PLAIN1":
            raise CredentialStorageError(
                "Stored API credential format is not recognized."
            )

        return raw.decode("utf-8")
    except CredentialStorageError:
        raise
    except Exception as error:
        raise CredentialStorageError(
            "Could not decode the stored API token: {}".format(error)
        )


def delete_token():
    _delete_file(get_credential_path())
