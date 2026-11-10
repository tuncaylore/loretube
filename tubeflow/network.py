"""Yerel ag adresini bulma."""

from __future__ import annotations

import ipaddress
import socket


def get_lan_ip(override: str | None = None) -> str | None:
    """Telefonun erisebilecegi ozel ag IPv4 adresini dondurur."""
    if override:
        try:
            address = ipaddress.ip_address(override)
        except ValueError:
            return None
        if address.version == 4 and not address.is_loopback:
            return str(address)
        return None

    candidates: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(0.5)
            sock.connect(("8.8.8.8", 80))
            candidates.append(sock.getsockname()[0])
    except OSError:
        pass

    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            candidates.append(info[4][0])
    except OSError:
        pass

    for candidate in candidates:
        try:
            address = ipaddress.ip_address(candidate)
        except ValueError:
            continue
        if address.version != 4:
            continue
        if address.is_loopback or address.is_link_local or address.is_unspecified:
            continue
        if address.is_private:
            return str(address)
    return None
