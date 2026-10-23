"""Command-line interface for ipsubnet."""

import argparse
import json
import os
import sys
from typing import List, Optional

from . import __version__
from .core import (SubnetError, describe, parse, resolve_new_prefix, subnet_count,
                   subnet_rows)

DEFAULT_LIMIT = 64

EXAMPLES = """\
examples:
  ipsubnet 192.168.1.10/24
  ipsubnet 192.168.1.10 255.255.255.0
  ipsubnet 10.0.0.0/16 --subnets 8
  ipsubnet 172.16.0.0/22 --hosts 100
  ipsubnet 192.168.0.0/24 --prefix 27
  ipsubnet 2001:db8::1/48 --prefix 52
  ipsubnet 192.168.1.10/24 --json

Run without arguments for interactive mode.
"""


class Style:
    """ANSI colours, switched off when output isn't a terminal or NO_COLOR is set."""

    def __init__(self, enabled: bool):
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return "\033[{}m{}\033[0m".format(code, text) if self.enabled else text

    def bold(self, t): return self._wrap("1", t)
    def dim(self, t): return self._wrap("2", t)
    def cyan(self, t): return self._wrap("36", t)
    def green(self, t): return self._wrap("32", t)
    def yellow(self, t): return self._wrap("33", t)
    def red(self, t): return self._wrap("31", t)
    def magenta(self, t): return self._wrap("35", t)


def _enable_windows_ansi() -> bool:
    if os.name != "nt":
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        return bool(kernel32.SetConsoleMode(handle, mode.value | 0x0004))
    except Exception:
        return False


def make_style(no_color: bool) -> Style:
    if no_color or os.environ.get("NO_COLOR") or not sys.stdout.isatty():
        return Style(False)
    return Style(_enable_windows_ansi())


def fmt_int(n: int) -> str:
    return "{:,}".format(n)


def render_binary(bits: str, prefix: int, s: Style) -> str:
    """Colour network bits and host bits differently."""
    out, seen = [], 0
    for ch in bits:
        if ch == ".":
            out.append(s.dim("."))
            continue
        out.append(s.cyan(ch) if seen < prefix else s.yellow(ch))
        seen += 1
    return "".join(out)


def render_summary(info: dict, s: Style) -> str:
    rows = [("Address", info["address"])]
    rows.append(("Network", s.green(info["cidr"])))
    if info["version"] == 4:
        rows += [
            ("Netmask", "{}  (/{})".format(info["netmask"], info["prefix"])),
            ("Wildcard", info["wildcard"]),
            ("Network address", info["network"]),
            ("Broadcast", info["broadcast"]),
        ]
    else:
        rows += [
            ("Expanded", info["expanded"]),
            ("Prefix length", "/{}".format(info["prefix"])),
            ("Network address", info["network"]),
        ]
    rows += [
        ("Usable range", s.green("{} - {}".format(info["first_host"], info["last_host"]))),
        ("Usable hosts", fmt_int(info["usable_hosts"])),
        ("Total addresses", fmt_int(info["total_addresses"])),
    ]
    if info["version"] == 4:
        rows.append(("Class", info["class"]))
    rows.append(("Type", info["scope"]))

    width = max(len(k) for k, _ in rows)
    lines = ["  {}  {}".format(s.bold(k.ljust(width)), v) for k, v in rows]

    if info["version"] == 4:
        b = info["binary"]
        lines += ["", "  " + s.bold("Binary") + s.dim("  (network bits | host bits)")]
        for label in ("address", "netmask", "network", "broadcast"):
            lines.append("  {}  {}".format(
                label.capitalize().ljust(width),
                render_binary(b[label], info["prefix"], s)))
    return "\n".join(lines)


def render_table(rows: List[dict], s: Style) -> str:
    ipv4 = rows and rows[0]["broadcast"] is not None
    headers = ["#", "Subnet", "First host", "Last host"]
    if ipv4:
        headers.append("Broadcast")
    headers.append("Usable")

    data = []
    for r in rows:
        line = [str(r["index"]), r["network"], r["first_host"], r["last_host"]]
        if ipv4:
            line.append(r["broadcast"])
        line.append(fmt_int(r["usable_hosts"]))
        data.append(line)

    widths = [max(len(h), *(len(d[i]) for d in data)) for i, h in enumerate(headers)]

    def fmt(cells, color=None):
        parts = []
        for i, (c, w) in enumerate(zip(cells, widths)):
            # Right-align numeric columns.
            cell = c.rjust(w) if i in (0, len(cells) - 1) else c.ljust(w)
            parts.append(cell)
        text = "  ".join(parts)
        return color(text) if color else text

    out = ["  " + fmt(headers, s.bold), "  " + s.dim("  ".join("-" * w for w in widths))]
    out += ["  " + fmt(d) for d in data]
    return "\n".join(out)


def run(address: str, mask: Optional[str], new_prefix: Optional[int], subnets: Optional[int],
        hosts: Optional[int], limit: Optional[int], as_json: bool, s: Style) -> None:
    iface, note = parse(address, mask)
    info = describe(iface)
    net = iface.network

    split_wanted = any(x is not None for x in (new_prefix, subnets, hosts))
    target = resolve_new_prefix(net, new_prefix, subnets, hosts) if split_wanted else None

    if as_json:
        payload = dict(info)
        if note:
            payload["note"] = note
        if target is not None:
            payload["subnetting"] = {
                "new_prefix": target,
                "subnet_count": subnet_count(net, target),
                "subnets": subnet_rows(net, target, limit),
                "truncated": limit is not None and subnet_count(net, target) > limit,
            }
        print(json.dumps(payload, indent=2))
        return

    print()
    if note:
        print("  " + s.yellow(note))
        print()
    print(render_summary(info, s))

    if target is not None:
        count = subnet_count(net, target)
        rows = subnet_rows(net, target, limit)
        per = rows[0]["usable_hosts"]
        print()
        print("  {}  {} into /{}: {} subnet{}, {} usable host{} each".format(
            s.bold("Subnets"), info["cidr"], target, fmt_int(count), "" if count == 1 else "s",
            fmt_int(per), "" if per == 1 else "s"))
        print()
        print(render_table(rows, s))
        if count > len(rows):
            print()
            print("  " + s.dim("... showing {} of {} subnets. Use --limit N or --all to see more."
                               .format(fmt_int(len(rows)), fmt_int(count))))
    print()


def _ask(prompt: str, s: Style) -> str:
    try:
        return input(s.magenta("? ") + prompt).strip()
    except EOFError:
        raise KeyboardInterrupt from None


def interactive(s: Style, limit: Optional[int]) -> int:
    print()
    print("  " + s.bold("ipsubnet {}".format(__version__)) + " - IP subnetting calculator")
    print("  " + s.dim("Press Enter on an empty line or Ctrl+C to quit."))
    while True:
        print()
        try:
            address = _ask("IP address (e.g. 192.168.1.10 or 192.168.1.10/24): ", s)
            if not address:
                return 0
            mask = None
            if "/" not in address:
                mask = _ask("Subnet mask or CIDR (e.g. 255.255.255.0 or 24, Enter for default): ", s) or None
            split = _ask("Split into subnets? Enter /prefix, N subnets ('8s'), N hosts ('50h'), "
                         "or Enter to skip: ", s).lower()
        except KeyboardInterrupt:
            print()
            return 0

        new_prefix = subnets = hosts = None
        try:
            if split:
                if split.endswith("s") and split[:-1].isdigit():
                    subnets = int(split[:-1])
                elif split.endswith("h") and split[:-1].isdigit():
                    hosts = int(split[:-1])
                elif split.lstrip("/").isdigit():
                    new_prefix = int(split.lstrip("/"))
                else:
                    raise SubnetError("didn't understand '{}'".format(split))
            run(address, mask, new_prefix, subnets, hosts, limit, False, s)
        except SubnetError as e:
            print("  " + s.red("error: ") + str(e))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ipsubnet",
        description="IP subnetting and addressing calculator for IPv4 and IPv6. "
                    "Shows the network address, broadcast, usable host range and "
                    "can split a network into subnets.",
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("address", nargs="?",
                   help="IP address, optionally with CIDR (192.168.1.10/24) or mask (192.168.1.10/255.255.255.0)")
    p.add_argument("mask", nargs="?",
                   help="subnet mask or prefix if not included in the address (255.255.255.0 or 24)")

    g = p.add_argument_group("subnetting (pick one)")
    ex = g.add_mutually_exclusive_group()
    ex.add_argument("-p", "--prefix", type=int, metavar="N", help="split into subnets of prefix /N")
    ex.add_argument("-s", "--subnets", type=int, metavar="N", help="split into at least N equal subnets")
    ex.add_argument("-H", "--hosts", type=int, metavar="N",
                    help="split into the smallest subnets that fit N usable hosts each")

    o = p.add_argument_group("output")
    o.add_argument("-l", "--limit", type=int, default=DEFAULT_LIMIT, metavar="N",
                   help="max subnets to list (default {})".format(DEFAULT_LIMIT))
    o.add_argument("-a", "--all", action="store_true", help="list every subnet (can be huge)")
    o.add_argument("-j", "--json", action="store_true", help="print JSON instead of a table")
    o.add_argument("--no-color", action="store_true", help="disable coloured output")
    p.add_argument("-V", "--version", action="version", version="ipsubnet " + __version__)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    s = make_style(args.no_color or args.json)
    limit = None if args.all else max(args.limit, 1)

    if args.address is None:
        if sys.stdin.isatty():
            return interactive(s, limit)
        build_parser().print_help()
        return 2

    try:
        run(args.address, args.mask, args.prefix, args.subnets, args.hosts, limit, args.json, s)
    except SubnetError as e:
        print("ipsubnet: error: {}".format(e), file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
    except BrokenPipeError:
        # e.g. `ipsubnet ... --all | head`
        sys.stderr.close()
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
