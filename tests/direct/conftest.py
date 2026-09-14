"""
Windows compatibility shim for genlayer-test's direct-mode stdin injection.

``gltest.direct.loader._inject_message_to_fd0`` duplicates a temp file onto
fd 0 and then immediately tries to ``os.unlink`` the original path. On
Windows this raises ``PermissionError`` because the duplicated handle still
holds the file open (POSIX allows unlinking an open file; Windows does not).
This is a bug in the third-party package's Windows support, unrelated to
AuditLot contract logic. We patch the function to tolerate that one failure
mode rather than modifying the installed package.
"""

import os
import tempfile

from gltest.direct import loader as _gltest_loader


def _inject_message_to_fd0_windows_safe(vm) -> None:
    from genlayer.py import calldata
    from genlayer.py.types import Address

    sender_addr = vm.sender
    if isinstance(sender_addr, bytes):
        sender_addr = Address(sender_addr)

    contract_addr = vm._contract_address
    if isinstance(contract_addr, bytes):
        contract_addr = Address(contract_addr)

    origin_addr = vm.origin
    if isinstance(origin_addr, bytes):
        origin_addr = Address(origin_addr)

    message_data = {
        "contract_address": contract_addr,
        "sender_address": sender_addr,
        "origin_address": origin_addr,
        "stack": [],
        "value": vm._value,
        "datetime": vm._datetime,
        "is_init": False,
        "chain_id": vm._chain_id,
        "entry_kind": 0,
        "entry_data": b"",
        "entry_stage_data": None,
    }

    encoded = calldata.encode(message_data)

    fd, path = tempfile.mkstemp()
    try:
        os.write(fd, encoded)
        os.lseek(fd, 0, os.SEEK_SET)

        original_stdin = os.dup(0)
        vm._original_stdin_fd = original_stdin

        os.dup2(fd, 0)
    finally:
        os.close(fd)
        try:
            os.unlink(path)
        except PermissionError:
            pass


_gltest_loader._inject_message_to_fd0 = _inject_message_to_fd0_windows_safe
