# ipsubnet

An IP subnetting and addressing calculator for the command line. Give it an IP address with a subnet mask or CIDR prefix. It prints the network address, broadcast address, usable host range and host counts, and it can split the network into a list of subnets. It works with IPv4 and IPv6 on Windows, macOS and Linux.

## Install

**Windows** (PowerShell):

```powershell
irm https://raw.githubusercontent.com/ShazanZaidii/ipsubnet/main/scripts/install.ps1 | iex
```

**macOS / Linux**:

```sh
curl -fsSL https://raw.githubusercontent.com/ShazanZaidii/ipsubnet/main/scripts/install.sh | sh
```

**With Python** (any OS, Python 3.8+):

```sh
pip install git+https://github.com/ShazanZaidii/ipsubnet.git
```

You can also download a ready-to-run binary from the [Releases page](https://github.com/ShazanZaidii/ipsubnet/releases/latest):

| OS | File |
|---|---|
| Windows | `ipsubnet-windows-x64.exe` |
| macOS (Apple Silicon) | `ipsubnet-macos-arm64` |
| macOS (Intel) | `ipsubnet-macos-x64` |
| Linux (x64) | `ipsubnet-linux-x64` |
| Linux (ARM64) | `ipsubnet-linux-arm64` |

On macOS and Linux, run `chmod +x` on the file first. On macOS, if you downloaded it with a browser, also run `xattr -d com.apple.quarantine <file>`.

## Usage

```
ipsubnet ADDRESS[/PREFIX] [MASK] [--prefix N | --subnets N | --hosts N] [options]
```

| Input | Meaning |
|---|---|
| `192.168.1.10/24` | Address with a CIDR prefix |
| `192.168.1.10 255.255.255.0` | Address and a dotted subnet mask |
| `192.168.1.10 24` | Address and a prefix length |
| `192.168.1.10` | Uses the classful default mask (A=/8, B=/16, C=/24) |
| `2001:db8::1/48` | IPv6 |

| Option | Description |
|---|---|
| `-p, --prefix N` | Split into subnets of size /N |
| `-s, --subnets N` | Split into at least N equal subnets |
| `-H, --hosts N` | Split into the smallest subnets that fit N usable hosts each |
| `-l, --limit N` | Show at most N subnets (default 64) |
| `-a, --all` | Show every subnet |
| `-j, --json` | Output JSON |
| `--no-color` | Turn off colours |

If you run `ipsubnet` with no arguments, it starts in interactive mode and asks for each value. This is also what happens when you double-click the Windows `.exe`.

### Example

```
$ ipsubnet 192.168.1.10/24 --hosts 50

  Address          192.168.1.10
  Network          192.168.1.0/24
  Netmask          255.255.255.0  (/24)
  Wildcard         0.0.0.255
  Network address  192.168.1.0
  Broadcast        192.168.1.255
  Usable range     192.168.1.1 - 192.168.1.254
  Usable hosts     254
  Total addresses  256
  Class            C
  Type             Private

  Binary  (network bits | host bits)
  Address          11000000.10101000.00000001.00001010
  Netmask          11111111.11111111.11111111.00000000
  Network          11000000.10101000.00000001.00000000
  Broadcast        11000000.10101000.00000001.11111111

  Subnets  192.168.1.0/24 into /26: 4 subnets, 62 usable hosts each

  #  Subnet            First host     Last host      Broadcast      Usable
  -  ----------------  -------------  -------------  -------------  ------
  1  192.168.1.0/26    192.168.1.1    192.168.1.62   192.168.1.63       62
  2  192.168.1.64/26   192.168.1.65   192.168.1.126  192.168.1.127      62
  3  192.168.1.128/26  192.168.1.129  192.168.1.190  192.168.1.191      62
  4  192.168.1.192/26  192.168.1.193  192.168.1.254  192.168.1.255      62
```

## How it works

- **Network address**: the IP AND the subnet mask (all host bits set to 0).
- **Broadcast address**: the network address with all host bits set to 1.
- **Usable hosts**: 2^(32 − prefix) − 2 for IPv4, because the network and broadcast addresses can't be assigned to hosts. A /31 has 2 usable addresses (point-to-point links, RFC 3021) and a /32 has 1.
- **Subnetting**: borrowing *b* host bits creates 2^b subnets of prefix + *b*.
  - `--subnets N` borrows ⌈log₂ N⌉ bits.
  - `--hosts N` keeps ⌈log₂(N + 2)⌉ host bits.
- **IPv6** has no broadcast address, so every address in the prefix is counted as usable.

## Development

```sh
pip install -e .
python -m unittest discover -s tests -v
```

Pushing a tag like `v1.0.1` makes GitHub Actions run the tests on all three operating systems, build the binaries and publish a release.

## Authors

Group 4: Shazan Hussain Zaidi, Harshit Agrawal, Prabhat Bhati
