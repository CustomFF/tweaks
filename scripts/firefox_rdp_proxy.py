#!/usr/bin/env python3
"""Прокси для Firefox Remote Debugging Protocol.

Держит ОДНО постоянное (уже одобренное кнопкой «Разрешить») соединение с
Firefox и раздаёт его клиентам по очереди. Пережидает перезапуск Firefox:
когда браузер закрылся, прокси сам ищет новый процесс и подключается заново
(прокси-порт для клиентов при этом не меняется).

Использование:
    firefox_rdp_proxy.py --browser /путь/к/firefox [--proxy-port N]
        сам находит запущенный Firefox этого пути и порт его
        debugger-сервера (читает /proc), переподключается после рестарта;
    firefox_rdp_proxy.py [firefox_port] [proxy_port]
        как раньше: фиксированный порт Firefox (по умолчанию 34375), но теперь
        тоже с переподключением.
"""
import argparse
import json
import os
import select
import socket
import sys
import time

FIREFOX_DEFAULT_PORT = 34375
PROXY_DEFAULT_PORT = 34376

# Сколько ждём приветствие от порта-кандидата, прежде чем показать подсказку
# про кнопку «Разрешить»; сам порт при этом не бросаем — ждём дальше.
HINT_AFTER = 3.0
PENDING_GIVE_UP = 120.0
DISCOVERY_POLL = 0.5


def drain_pending(sock):
    """Дочитывает и отбрасывает кадры, оставленные предыдущим клиентом
    (например, недосмотренные ответы/события), не разрывая границу
    length:json-кадра — иначе следующий кадр в общем соединении к Firefox
    десинхронизируется навсегда."""
    while True:
        readable, _, _ = select.select([sock], [], [], 0)
        if not readable:
            return
        if read_rdp_message(sock) is None:
            return


def read_rdp_message(sock):
    """Считывает одно сообщение Firefox RDP (length:json), вместе с префиксом."""
    len_bytes = b''
    while True:
        char = sock.recv(1)
        if not char:
            return None
        if char == b':':
            break
        len_bytes += char
    try:
        length = int(len_bytes.decode('utf-8'))
    except ValueError:
        return None

    data = b''
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            return None
        data += chunk
    return len_bytes + b':' + data


def is_rdp_greeting(msg):
    """Приветствие RDP — от актора root (отличает devtools-порт от, например,
    marionette, у которого тоже length:json-приветствие)."""
    try:
        body = msg.split(b':', 1)[1]
        return json.loads(body.decode('utf-8')).get('from') == 'root'
    except Exception:
        return False


# ─── Поиск процесса и его портов по /proc ────────────────────────────────

def browser_exe_candidates(path):
    """Реальные пути бинарников, считающихся «этим» браузером: указанный
    файл/каталог и firefox-bin рядом (firefox — обычно лаунчер, а процесс
    работает как firefox-bin)."""
    real = os.path.realpath(path)
    base = real if os.path.isdir(real) else os.path.dirname(real)
    cands = {os.path.join(base, 'firefox-bin'), os.path.join(base, 'firefox')}
    if os.path.isfile(real):
        cands.add(real)
    return {os.path.realpath(c) for c in cands}


def read_cmdline(pid):
    try:
        with open(f'/proc/{pid}/cmdline', 'rb') as f:
            return [a.decode('utf-8', 'replace') for a in f.read().split(b'\0') if a]
    except OSError:
        return []


def find_browser_pids(path):
    """PID'ы главных процессов Firefox с указанным путём (без -contentproc)."""
    cands = browser_exe_candidates(path)
    found = []
    for name in os.listdir('/proc'):
        if not name.isdigit():
            continue
        try:
            exe = os.path.realpath(f'/proc/{name}/exe')
        except OSError:
            continue
        if exe not in cands:
            continue
        if '-contentproc' in read_cmdline(name):
            continue
        found.append(int(name))
    return sorted(found)


def listening_loopback_ports(pid):
    """Порты, которые процесс слушает на loopback (через inode сокетов)."""
    inodes = set()
    try:
        for fd in os.listdir(f'/proc/{pid}/fd'):
            try:
                link = os.readlink(f'/proc/{pid}/fd/{fd}')
            except OSError:
                continue
            if link.startswith('socket:['):
                inodes.add(link[8:-1])
    except OSError:
        return []
    ports = []
    for table, loopback in (('/proc/net/tcp', '0100007F'),
                            ('/proc/net/tcp6', '00000000000000000000000001000000')):
        try:
            with open(table) as f:
                lines = f.read().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            cols = line.split()
            if cols[3] != '0A' or cols[9] not in inodes:
                continue
            addr, port = cols[1].split(':')
            if addr == loopback:
                ports.append(int(port, 16))
    return sorted(set(ports))


def cmdline_debugger_port(pid):
    """Порт из `--start-debugger-server N` (или `=N`, `ws:N`), если есть."""
    args = read_cmdline(pid)
    for i, a in enumerate(args):
        val = None
        if a == '--start-debugger-server' and i + 1 < len(args):
            val = args[i + 1]
        elif a.startswith('--start-debugger-server='):
            val = a.split('=', 1)[1]
        if val:
            digits = val.split(':')[-1]
            if digits.isdigit():
                return int(digits)
    return None


# ─── Подключение к Firefox ───────────────────────────────────────────────

class Discovery:
    """Ищет debugger-порт Firefox и возвращает (сокет, приветствие).

    Порт может стартовать позже самого браузера (например, сервер включают из
    меню) и приветствие приходит только после «Разрешить» в Firefox — поэтому
    кандидатов не бросаем по таймауту, а держим «в ожидании» и опрашиваем."""

    def __init__(self, browser, fixed_port):
        self.browser = browser
        self.fixed_port = fixed_port
        self.pending = {}   # (pid, port) -> [sock, since, hinted]
        self.bad = set()    # (pid, port): ответили не-RDP или закрыли
        self.announced = False

    def close_all(self):
        for sock, _, _ in self.pending.values():
            try:
                sock.close()
            except OSError:
                pass
        self.pending.clear()

    def _candidates(self):
        if self.fixed_port is not None:
            return [(0, self.fixed_port)]
        result = []
        for pid in find_browser_pids(self.browser):
            ports = listening_loopback_ports(pid)
            hinted = cmdline_debugger_port(pid)
            if hinted in ports:
                ports.remove(hinted)
                ports.insert(0, hinted)
            result.extend((pid, p) for p in ports)
        return result

    def poll(self):
        """Один проход; возвращает (sock, greeting) или None."""
        candidates = self._candidates()
        if self.browser is not None and not candidates and not self.announced:
            print(f"Жду запущенный Firefox ({self.browser}) с включённым "
                  "debugger-сервером...")
            self.announced = True

        alive = set(candidates)
        # Кандидаты, которых уже нет (процесс/порт исчез) — выбрасываем.
        for key in list(self.pending):
            if key not in alive:
                self.pending.pop(key)[0].close()
        self.bad &= alive

        for key in candidates:
            if key in self.pending or key in self.bad:
                continue
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            try:
                sock.settimeout(2)
                sock.connect(('127.0.0.1', key[1]))
                sock.settimeout(None)
            except OSError:
                sock.close()
                continue
            print(f"Подключение к 127.0.0.1:{key[1]}"
                  + (f" (pid {key[0]})" if key[0] else "") + "...")
            self.pending[key] = [sock, time.time(), False]

        for key, entry in list(self.pending.items()):
            sock, since, hinted = entry
            readable, _, _ = select.select([sock], [], [], 0)
            if readable:
                msg = None
                try:
                    msg = read_rdp_message(sock)
                except OSError:
                    pass
                self.pending.pop(key)
                if msg and is_rdp_greeting(msg):
                    self.close_all()
                    return sock, msg
                sock.close()
                self.bad.add(key)
                if self.fixed_port is None:
                    print(f"Порт {key[1]} — не debugger-сервер Firefox, пропускаю.")
                continue
            waited = time.time() - since
            if not hinted and waited > HINT_AFTER:
                entry[2] = True
                print(f"Порт {key[1]} принял соединение, но молчит — "
                      "ПОЖАЛУЙСТА, НАЖМИ [РАЗРЕШИТЬ] (ALLOW) В ДИАЛОГЕ FIREFOX...")
            if waited > PENDING_GIVE_UP:
                self.pending.pop(key)
                sock.close()
                self.bad.add(key)
                print(f"Порт {key[1]}: ответа нет {int(PENDING_GIVE_UP)} c, бросаю.")
        return None


# ─── Прокси ──────────────────────────────────────────────────────────────

def reject_waiting_clients(proxy_server):
    """Пока Firefox недоступен, клиенты не должны висеть до таймаута —
    закрываем входящие сразу."""
    while True:
        readable, _, _ = select.select([proxy_server], [], [], 0)
        if not readable:
            return
        try:
            client, _ = proxy_server.accept()
            client.close()
        except OSError:
            return


def firefox_closed(ff_sock):
    try:
        return not ff_sock.recv(1, socket.MSG_PEEK | socket.MSG_DONTWAIT)
    except BlockingIOError:
        return False
    except OSError:
        return True


def serve(proxy_server, ff_sock, greeting):
    """Раздаёт соединение с Firefox клиентам. Возврат — Firefox закрылся."""
    while True:
        # Очищаем буфер Firefox перед подключением нового клиента —
        # только целыми кадрами, чтобы не разорвать length:json-границу.
        drain_pending(ff_sock)
        if firefox_closed(ff_sock):
            print("[Firefox разорвал соединение]")
            return

        readable, _, _ = select.select([proxy_server, ff_sock], [], [], 1.0)
        if proxy_server not in readable:
            continue

        client_sock, client_addr = proxy_server.accept()
        print(f"[Клиент подключился: {client_addr}]")

        try:
            client_sock.sendall(greeting)
        except OSError:
            client_sock.close()
            continue

        inputs = [client_sock, ff_sock]
        client_active = True
        firefox_gone = False
        try:
            while client_active:
                readable, _, exceptional = select.select(inputs, [], inputs, 60)
                if exceptional:
                    break
                for s in readable:
                    if s is client_sock:
                        data = client_sock.recv(4096)
                        if not data:
                            client_active = False
                            break
                        ff_sock.sendall(data)
                    else:
                        data = ff_sock.recv(4096)
                        if not data:
                            print("[Firefox разорвал соединение]")
                            firefox_gone = True
                            client_active = False
                            break
                        client_sock.sendall(data)
        except OSError as e:
            print(f"[Ошибка обмена данными: {e}]")
            firefox_gone = firefox_closed(ff_sock)

        try:
            client_sock.close()
        except OSError:
            pass
        print("[Клиент отключился]")
        if firefox_gone:
            return


def parse_args():
    p = argparse.ArgumentParser(
        description="Прокси для Firefox Remote Debugging Protocol "
                    "(переживает перезапуск Firefox).")
    p.add_argument('--browser', metavar='ПУТЬ',
                   help="путь к firefox (файл или каталог установки): порт "
                        "debugger-сервера ищется автоматически среди процессов "
                        "этого браузера, с переподключением после перезапуска")
    p.add_argument('--proxy-port', type=int, default=None,
                   help=f"порт прокси для клиентов (по умолчанию {PROXY_DEFAULT_PORT})")
    p.add_argument('--firefox-port', type=int, default=None,
                   help="фиксированный порт debugger-сервера Firefox")
    p.add_argument('ports', nargs='*', type=int, metavar='PORT',
                   help="старый формат: [firefox_port] [proxy_port]")
    args = p.parse_args()

    fixed = args.firefox_port
    proxy = args.proxy_port
    if args.ports:
        if len(args.ports) > 2:
            p.error("слишком много позиционных аргументов")
        if fixed is None and not args.browser:
            fixed = args.ports[0]
            if len(args.ports) > 1 and proxy is None:
                proxy = args.ports[1]
        elif proxy is None:
            proxy = args.ports[-1]
    if fixed is None and not args.browser:
        fixed = FIREFOX_DEFAULT_PORT
    return args.browser, fixed, proxy or PROXY_DEFAULT_PORT


def main():
    browser, fixed_port, proxy_port = parse_args()

    proxy_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    proxy_server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        proxy_server.bind(('127.0.0.1', proxy_port))
        proxy_server.listen(1)
    except OSError as e:
        print(f"Не удалось привязать прокси-сервер к 127.0.0.1:{proxy_port}: {e}")
        sys.exit(1)

    print(f"Прокси-сервер запущен на 127.0.0.1:{proxy_port}")
    print("Для остановки нажмите Ctrl+C.\n")

    discovery = Discovery(browser, fixed_port)
    try:
        while True:
            conn = None
            while conn is None:
                reject_waiting_clients(proxy_server)
                conn = discovery.poll()
                if conn is None:
                    time.sleep(DISCOVERY_POLL)
            ff_sock, greeting = conn
            print("Подключено к Firefox, приветствие получено:")
            print(greeting.decode('utf-8', errors='ignore'))
            try:
                serve(proxy_server, ff_sock, greeting)
            finally:
                ff_sock.close()
            discovery = Discovery(browser, fixed_port)
            print("Жду перезапуска Firefox...\n")
    except KeyboardInterrupt:
        print("\nОстановка прокси-сервера...")
    finally:
        discovery.close_all()
        proxy_server.close()


if __name__ == '__main__':
    main()
