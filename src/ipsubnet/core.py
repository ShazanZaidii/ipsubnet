"""Subnet math: parsing input, describing a network, and splitting it into subnets."""

import ipaddress
import math
from typing import Iterator, List, Optional, Tuple, Union

Interface = Union[ipaddress.IPv4Interface, ipaddress.IPv6Interface]
Network = Union[ipaddress.IPv4Network, ipaddress.IPv6Network]


class SubnetError(ValueError):
    """Raised for any input the calculator cannot work with."""


def classful_prefix(ip: ipaddress.IPv4Address) -> Optional[int]:
    """Default prefix for the IPv4 address class (A=/8, B=/16, C=/24), or None for D/E."""
    first = int(ip) >> 24
    if first < 128:
        return 8
    if first < 192:
        return 16
    if first < 224:
        return 24
    return None


def _parse_mask(mask: str, version: int) -> int:
    """Turn '24', '/24', '255.255.255.0' or a wildcard like '0.0.0.255' into a prefix length."""
    mask = mask.strip().lstrip("/")
    if not mask:
        raise SubnetError("empty subnet mask")
    if mask.isdigit():
        prefix = int(mask)
        limit = 32 if version == 4 else 128
        if not 0 <= prefix <= limit:
            raise SubnetError("prefix /{} is out of range (0-{})".format(prefix, limit))
        return prefix
    if version == 6:
        raise SubnetError("IPv6 needs a prefix length such as /64, not a dotted mask")
    try:
        # ipaddress accepts both netmasks and wildcard (host) masks here.
        return ipaddress.IPv4Network("0.0.0.0/" + mask).prefixlen
    except ValueError:
        raise SubnetError("'{}' is not a valid subnet mask".format(mask)) from None


def parse(address: str, mask: Optional[str] = None) -> Tuple[Interface, Optional[str]]:
    """Parse user input into an interface (address + prefix).

    Returns the interface and an optional note to show the user (e.g. when a
    default mask was assumed).
    """
    address = address.strip()
    if "/" in address:
        if mask:
            raise SubnetError("give the mask either as /CIDR or as a separate argument, not both")
        address, mask = address.split("/", 1)

    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        raise SubnetError("'{}' is not a valid IPv4 or IPv6 address".format(address)) from None

    note = None
    if mask is None:
        if ip.version == 4:
            prefix = classful_prefix(ip)
            if prefix is None:
                raise SubnetError(
                    "{} is a class D/E address and has no default mask; please give one".format(ip)
                )
            note = "No mask given; assumed the classful default /{}.".format(prefix)
        else:
            prefix = 64
            note = "No prefix given; assumed /64."
    else:
        prefix = _parse_mask(mask, ip.version)

    return ipaddress.ip_interface("{}/{}".format(ip, prefix)), note


def ip_class(ip: ipaddress.IPv4Address) -> str:
    first = int(ip) >> 24
    if first < 128:
        return "A"
    if first < 192:
        return "B"
    if first < 224:
        return "C"
    if first < 240:
        return "D (multicast)"
    return "E (reserved)"


DOCUMENTATION_NETS = [ipaddress.ip_network(n) for n in (
    "192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24", "2001:db8::/32")]


def ip_scope(ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]) -> str:
    if ip.is_loopback:
        return "Loopback"
    if ip.is_link_local:
        return "Link-local"
    if ip.is_multicast:
        return "Multicast"
    if ip.is_unspecified:
        return "Unspecified"
    if any(ip.version == n.version and ip in n for n in DOCUMENTATION_NETS):
        return "Documentation (example range)"
    if ip.version == 4 and ip in ipaddress.IPv4Network("100.64.0.0/10"):
        return "Shared address space (CGNAT)"
    if ip.is_private:
        return "Private"
    if ip.is_reserved:
        return "Reserved"
    if ip.is_global:
        return "Public"
    return "Special-purpose"


def host_range(net: Network) -> Tuple[object, object, int]:
    """First usable, last usable and usable count for a network.

    IPv4 /31 links use both addresses (RFC 3021); /32 is a single host.
    IPv6 has no broadcast address, so every address is usable.
    """
    total = net.num_addresses
    if net.version == 6 or net.prefixlen >= net.max_prefixlen - 1:
        return net.network_address, net.broadcast_address, total
    return net.network_address + 1, net.broadcast_address - 1, total - 2


def to_binary(ip: ipaddress.IPv4Address) -> str:
    bits = format(int(ip), "032b")
    return ".".join(bits[i:i + 8] for i in range(0, 32, 8))


def describe(iface: Interface) -> dict:
    """All the facts about an address and the network it sits in."""
    net = iface.network
    ip = iface.ip
    first, last, usable = host_range(net)
    info = {
        "version": ip.version,
        "address": str(ip),
        "cidr": "{}/{}".format(net.network_address, net.prefixlen),
        "prefix": net.prefixlen,
        "network": str(net.network_address),
        "first_host": str(first),
        "last_host": str(last),
        "total_addresses": net.num_addresses,
        "usable_hosts": usable,
        "scope": ip_scope(ip),
    }
    if ip.version == 4:
        info.update({
            "netmask": str(net.netmask),
            "wildcard": str(net.hostmask),
            "broadcast": str(net.broadcast_address),
            "class": ip_class(ip),
            "binary": {
                "address": to_binary(ip),
                "netmask": to_binary(net.netmask),
                "network": to_binary(net.network_address),
                "broadcast": to_binary(net.broadcast_address),
            },
        })
    else:
        info.update({
            "netmask": None,
            "wildcard": None,
            "broadcast": None,
            "expanded": ip.exploded,
        })
    return info


def resolve_new_prefix(net: Network, new_prefix: Optional[int] = None,
                       subnets: Optional[int] = None, hosts: Optional[int] = None) -> int:
    """Work out the target prefix from exactly one of: new prefix, subnet count, hosts per subnet."""
    given = [x is not None for x in (new_prefix, subnets, hosts)]
    if sum(given) != 1:
        raise SubnetError("choose exactly one of --prefix, --subnets or --hosts")

    max_len = net.max_prefixlen
    if new_prefix is not None:
        if not net.prefixlen <= new_prefix <= max_len:
            raise SubnetError(
                "new prefix must be between /{} and /{}".format(net.prefixlen, max_len)
            )
        return new_prefix

    if subnets is not None:
        if subnets < 1:
            raise SubnetError("number of subnets must be at least 1")
        borrowed = math.ceil(math.log2(subnets)) if subnets > 1 else 0
        result = net.prefixlen + borrowed
        if result > max_len:
            raise SubnetError(
                "/{} cannot be split into {} subnets (at most {})".format(
                    net.prefixlen, subnets, 2 ** (max_len - net.prefixlen))
            )
        return result

    if hosts < 1:
        raise SubnetError("hosts per subnet must be at least 1")
    # IPv4 subnets reserve network + broadcast (textbook rule; a single host gets /32).
    if net.version == 4 and hosts > 1:
        needed = hosts + 2
    else:
        needed = hosts
    host_bits = math.ceil(math.log2(needed)) if needed > 1 else 0
    result = max_len - host_bits
    if result < net.prefixlen:
        raise SubnetError(
            "/{} is too small for {} hosts per subnet (it has {} usable)".format(
                net.prefixlen, hosts, host_range(net)[2])
        )
    return result


def split(net: Network, new_prefix: int) -> Iterator[Network]:
    return net.subnets(new_prefix=new_prefix)


def subnet_count(net: Network, new_prefix: int) -> int:
    return 2 ** (new_prefix - net.prefixlen)


def subnet_rows(net: Network, new_prefix: int, limit: Optional[int]) -> List[dict]:
    rows = []
    for i, sub in enumerate(split(net, new_prefix), 1):
        if limit is not None and i > limit:
            break
        first, last, usable = host_range(sub)
        rows.append({
            "index": i,
            "network": str(sub),
            "first_host": str(first),
            "last_host": str(last),
            "broadcast": str(sub.broadcast_address) if sub.version == 4 else None,
            "usable_hosts": usable,
        })
    return rows
