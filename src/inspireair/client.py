"""Client OSC X-Air : push ordonné et capture de tranche par nœuds.

Le port OSC officieux de la famille X-Air est 10024 (UDP), sans authentification.
La console répond à l'IP/port source de la requête : la capture utilise donc un
unique socket brut pour émettre et recevoir. Les réponses de nœud arrivent en
liste positionnelle (décodée par oscmap.snapshot_to_preset_values).
"""

from __future__ import annotations

import time
from socket import AF_INET, SO_RCVTIMEO, SOCK_DGRAM, SOL_SOCKET, socket
from struct import pack
from typing import Any, Optional

from pythonosc.osc_message_builder import OscMessageBuilder
from pythonosc.osc_packet import OscPacket
from pythonosc.udp_client import SimpleUDPClient

from .oscmap import OscItem, capture_nodes

DEFAULT_PORT = 10024
DEFAULT_PACING_S = 0.015
FORBIDDEN_PREFIXES = ("/headamp", "/preamp/trim", "/mix/")


class XAirError(RuntimeError):
    """Erreur de communication avec la console."""


class XAirClient:
    def __init__(
        self,
        host: str,
        port: int = DEFAULT_PORT,
        timeout: float = 2.0,
        pacing: float = DEFAULT_PACING_S,
    ) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.pacing = pacing
        self._sender = SimpleUDPClient(host, port)

    def push(self, items: list[OscItem]) -> int:
        """Envoie les couples (adresse, valeur) dans l'ordre fourni."""
        for address, value in items:
            for forbidden in FORBIDDEN_PREFIXES:
                if address.startswith(forbidden):
                    raise XAirError(f"adresse interdite pour la sécurité : {address}")
            self._sender.send_message(address, value)
            if self.pacing:
                time.sleep(self.pacing)
        return len(items)

    def ping(self) -> bool:
        """True si la console répond à un /info."""
        try:
            self._query("/info")
            return True
        except XAirError:
            return False

    def capture(self, channel: int, nodes: Optional[list[str]] = None) -> dict[str, list[Any]]:
        """Interroge chaque nœud du canal et retourne {nœud: [valeurs positionnelles]}."""
        nodes = nodes if nodes is not None else capture_nodes(channel)
        results: dict[str, list[Any]] = {}
        for node in nodes:
            values = self._query(node)
            if values:
                results[node] = values
        return results

    def _query(self, address: str) -> list[Any]:
        msg = OscMessageBuilder(address).build().dgram
        sock = socket(AF_INET, SOCK_DGRAM)
        try:
            seconds = int(self.timeout)
            useconds = int((self.timeout - seconds) * 1_000_000)
            sock.setsockopt(SOL_SOCKET, SO_RCVTIMEO, pack("ll", seconds, useconds))
            sock.sendto(msg, (self.host, self.port))
            try:
                data, _ = sock.recvfrom(8192)
            except OSError:
                raise XAirError(f"pas de réponse de la console sur {self.host}:{self.port}") from None
        finally:
            sock.close()
        values: list[Any] = []
        for timed_msg in OscPacket(data).messages:
            values.extend(timed_msg.message.params)
        return values
