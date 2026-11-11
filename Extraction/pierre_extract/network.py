"""Téléchargement borné. Chaque redirection et adresse DNS est vérifiée.
La connexion utilise l'adresse vérifiée : pas de seconde résolution DNS.
"""

import http.client
import ipaddress
import socket
import ssl
from urllib.parse import urlsplit, urljoin


class UnsafeURL(ValueError):
    pass


def resolve_public(url):
    p = urlsplit(url)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise UnsafeURL("URL HTTP(S) publique requise")
    port = p.port or (443 if p.scheme == "https" else 80)
    if port != (443 if p.scheme == "https" else 80):
        raise UnsafeURL("Port non autorisé")
    addresses = list(
        dict.fromkeys(
            x[4][0]
            for x in socket.getaddrinfo(p.hostname, port, type=socket.SOCK_STREAM)
        )
    )
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise UnsafeURL("Adresse réseau non publique")
    return p, port, addresses[0]


def fetch(url, max_bytes=2_000_000):
    for _ in range(6):
        p, port, address = resolve_public(url)
        host = p.hostname.encode("idna").decode("ascii")
        connection = http.client.HTTPConnection(host, port, timeout=12)
        try:
            sock = socket.create_connection((address, port), timeout=12)
            if p.scheme == "https":
                sock = ssl.create_default_context().wrap_socket(
                    sock, server_hostname=host
                )
            connection.sock = sock
            target = p.path or "/"
            if p.query:
                target += "?" + p.query
            connection.request(
                "GET",
                target,
                headers={
                    "Host": host,
                    "User-Agent": "PierreImport/0.1",
                    "Accept-Encoding": "identity",
                },
            )
            response = connection.getresponse()
            if response.status in (301, 302, 303, 307, 308):
                location = response.getheader("Location")
                if not location:
                    raise ValueError("Redirection sans destination")
                url = urljoin(url, location)
                continue
            if response.status != 200:
                raise ValueError(f"HTTP {response.status}")
            data = response.read(max_bytes + 1)
            if len(data) > max_bytes:
                raise ValueError("Fichier trop volumineux")
            return data, response.getheader("Content-Type", ""), url
        finally:
            connection.close()
    raise ValueError("Trop de redirections")
