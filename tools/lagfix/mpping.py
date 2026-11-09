#!/usr/bin/env python3
"""mpping.py — честный пинг Minecraft-сервера из стандартной библиотеки.

Печатает время до ответа в миллисекундах и версию/онлайн из ответа.
Нужен, чтобы отличить "сервер тормозит" от "сеть/фаерволл".

    python3 mpping.py 127.0.0.1 25566 [сколько_раз]
"""
import json
import socket
import struct
import sys
import time


def varint(n):
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        if n:
            out += bytes([b | 0x80])
        else:
            out += bytes([b])
            return out


def read_varint(sock):
    num = 0
    for i in range(5):
        b = sock.recv(1)
        if not b:
            raise IOError("соединение закрыто")
        num |= (b[0] & 0x7F) << (7 * i)
        if not b[0] & 0x80:
            return num
    raise IOError("плохой varint")


def read_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise IOError("соединение закрыто")
        buf += chunk
    return buf


def ping(host, port, timeout=10.0, hostname=None):
    t0 = time.time()
    s = socket.create_connection((host, port), timeout=timeout)
    s.settimeout(timeout)
    try:
        name = hostname or host
        # handshake: protocol 767 (1.21.x), адрес, порт, next_state=1 (status)
        addr = name.encode("utf-8")
        body = varint(0x00) + varint(767) + varint(len(addr)) + addr + struct.pack(">H", port) + varint(1)
        s.sendall(varint(len(body)) + body)
        s.sendall(varint(1) + varint(0x00))
        read_varint(s)                       # длина пакета
        pid = read_varint(s)                 # id пакета
        if pid != 0:
            raise IOError("неожиданный пакет %d" % pid)
        ln = read_varint(s)
        raw = read_exact(s, ln).decode("utf-8", "replace")
        ms = (time.time() - t0) * 1000.0
        try:
            data = json.loads(raw)
        except ValueError:
            data = {}
        return ms, data
    finally:
        s.close()


def main():
    if len(sys.argv) < 2:
        print("использование: mpping.py <хост> [порт] [раз] [имя_для_handshake]", file=sys.stderr)
        return 2
    host = sys.argv[1]
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 25565
    times = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    hs = sys.argv[4] if len(sys.argv) > 4 else None

    ok = 0
    worst = 0.0
    for i in range(times):
        try:
            ms, data = ping(host, port, hostname=hs)
            ok += 1
            worst = max(worst, ms)
            ver = (data.get("version") or {}).get("name", "?")
            players = data.get("players") or {}
            motd = data.get("description")
            if isinstance(motd, dict):
                motd = motd.get("text", "")
            print("  попытка %d: %.0f мс, версия %s, онлайн %s/%s" %
                  (i + 1, ms, ver, players.get("online", "?"), players.get("max", "?")))
        except Exception as e:  # noqa: BLE001
            print("  попытка %d: ОШИБКА %s: %s" % (i + 1, type(e).__name__, e))
    print("  итог: %d из %d, худшее %.0f мс" % (ok, times, worst))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
