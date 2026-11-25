"""Client OSC X-Air : push ordonné et capture (« Aspirer la tranche »).

Le port OSC officieux de la famille X-Air est 10024 (UDP), sans authentification.
La console répond à l'IP/port source de la requête : la capture utilise donc
un unique socket brut pour émettre et recevoir.
"""

from __future__ import annotations

import re
import time
from socket import AF_INET, SO_RCVTIMEO, SOCK_DGRAM, SOL_SOCKET, socket
from struct import pack
from typing import Any, Optional

from pythonosc.osc_message_builder import OscMessageBuilder
from pythonosc.osc_packet import OscPacket
from pythonosc.udp_client import SimpleUDPClient

from .oscmap import OscItem, capture_queries

DEFAULT_PORT = 10024
DEFAULT_PACING_S = 0.015
FORBIDDEN_PREFIXES = ("/pre/", "/mix/")
EQ_TYPES = {"PEQ", "VEQ4", "VEQ6", "HShv", "LShv", "LPF1", "HPF1"}


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
        """Teste la présence de la console (« On air ») : True si elle répond."""
        try:
            reply = self._query("/info")
            return reply is not None
        except XAirError:
            return False

    def capture(self, channel: int, queries: Optional[list[str]] = None) -> dict[str, Any]:
        """Interroge chaque adresse du canal et retourne {adresse: valeur}."""
        queries = queries if queries is not None else capture_queries(channel)
        results: dict[str, Any] = {}
        for address in queries:
            values = self._query(address)
            if values:
                results[address] = values[0]
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
                data, _ = sock.recvfrom(4096)
            except OSError:
                raise XAirError(f"pas de réponse de la console sur {self.host}:{self.port}") from None
        finally:
            sock.close()
        values: list[Any] = []
        for timed_msg in OscPacket(data).messages:
            values.extend(timed_msg.message.params)
        return values


def snapshot_to_preset_values(results: dict[str, Any], prefix: str) -> dict[str, Any]:
    """Transforme une capture brute {adresse: valeur} en dictionnaire de preset."""
    gate_map = {"thr": "thr", "rng": "range", "att": "attack", "hold": "hold", "rel": "release"}
    comp_map = {
        "thr": "thr",
        "ratio": "ratio",
        "att": "attack",
        "rel": "release",
        "knee": "knee",
        "mgain": "mgain",
        "wdm": "wdm",
    }
    preset_values: dict[str, Any] = {}
    eq: dict[int, dict[str, Any]] = {}
    for address, value in results.items():
        parts = address.removeprefix(prefix).strip("/").split("/")
        if parts[0] == "config":
            config = preset_values.setdefault("config", {"name": "", "color": 0, "icon": 0})
            if parts[1] == "name" and value is not None:
                config["name"] = str(value)
            elif parts[1] in ("color", "icon"):
                config[parts[1]] = int(value) if value is not None else 0
        elif parts[0] == "hpf":
            hpf = preset_values.setdefault("hpf", {"on": False, "freq": 100.0})
            if parts[1] == "on":
                hpf["on"] = bool(int(value))
            elif parts[1] == "freq":
                hpf["freq"] = round(float(value), 2)
        elif parts[0] == "gate":
            gate = preset_values.setdefault("gate", {})
            if parts[1] == "on":
                gate["on"] = bool(int(value))
            else:
                gate[gate_map[parts[1]]] = round(float(value), 3)
        elif parts[0] == "comp":
            comp = preset_values.setdefault("comp", {})
            if parts[1] == "on":
                comp["on"] = bool(int(value))
            else:
                comp[comp_map[parts[1]]] = round(float(value), 3)
        elif parts[0] == "eq" and len(parts) == 3:
            band = int(re.sub(r"\D", "", parts[1]))
            entry = eq.setdefault(band, {"band": band})
            if parts[2] == "type" and value in EQ_TYPES:
                entry["type"] = value
            elif parts[2] == "freq":
                entry["freq"] = round(float(value), 2)
            elif parts[2] == "g":
                entry["gain"] = round(float(value), 2)
            elif parts[2] == "q":
                entry["q"] = round(float(value), 2)
    if eq:
        preset_values["eq"] = [eq[k] for k in sorted(eq)]
    return preset_values
