import json
import unittest
from contextlib import redirect_stdout
from io import StringIO

from ipsubnet.cli import main
from ipsubnet.core import SubnetError, describe, parse, resolve_new_prefix, subnet_rows


def info(addr, mask=None):
    return describe(parse(addr, mask)[0])


class ParseTests(unittest.TestCase):
    def test_cidr_and_mask_forms_agree(self):
        forms = [("192.168.1.10/24", None), ("192.168.1.10", "255.255.255.0"),
                 ("192.168.1.10", "24"), ("192.168.1.10", "/24"),
                 ("192.168.1.10/255.255.255.0", None), ("192.168.1.10", "0.0.0.255")]
        for addr, mask in forms:
            self.assertEqual(info(addr, mask)["cidr"], "192.168.1.0/24", (addr, mask))

    def test_classful_default(self):
        iface, note = parse("10.1.2.3")
        self.assertEqual(iface.network.prefixlen, 8)
        self.assertIn("classful", note)

    def test_bad_input(self):
        for addr, mask in [("300.1.1.1/24", None), ("1.2.3.4", "255.0.255.0"),
                           ("1.2.3.4/33", None), ("1.2.3.4/24", "24"), ("230.0.0.1", None)]:
            with self.assertRaises(SubnetError):
                parse(addr, mask)


class DescribeTests(unittest.TestCase):
    def test_slash24(self):
        i = info("192.168.1.10/24")
        self.assertEqual(i["network"], "192.168.1.0")
        self.assertEqual(i["broadcast"], "192.168.1.255")
        self.assertEqual(i["first_host"], "192.168.1.1")
        self.assertEqual(i["last_host"], "192.168.1.254")
        self.assertEqual(i["usable_hosts"], 254)
        self.assertEqual(i["wildcard"], "0.0.0.255")
        self.assertEqual(i["class"], "C")
        self.assertEqual(i["scope"], "Private")

    def test_slash31_and_32(self):
        self.assertEqual(info("10.0.0.0/31")["usable_hosts"], 2)
        self.assertEqual(info("10.0.0.5/32")["usable_hosts"], 1)

    def test_odd_prefix(self):
        i = info("172.16.5.77/20")
        self.assertEqual(i["network"], "172.16.0.0")
        self.assertEqual(i["broadcast"], "172.16.15.255")
        self.assertEqual(i["usable_hosts"], 4094)

    def test_ipv6(self):
        i = info("2001:db8::1/64")
        self.assertEqual(i["cidr"], "2001:db8::/64")
        self.assertIsNone(i["broadcast"])
        self.assertEqual(i["total_addresses"], 2 ** 64)


class SplitTests(unittest.TestCase):
    def net(self, s):
        return parse(s)[0].network

    def test_by_subnets(self):
        self.assertEqual(resolve_new_prefix(self.net("10.0.0.0/16"), subnets=8), 19)
        self.assertEqual(resolve_new_prefix(self.net("10.0.0.0/16"), subnets=5), 19)

    def test_by_hosts(self):
        self.assertEqual(resolve_new_prefix(self.net("192.168.0.0/24"), hosts=50), 26)
        self.assertEqual(resolve_new_prefix(self.net("192.168.0.0/24"), hosts=62), 26)
        self.assertEqual(resolve_new_prefix(self.net("192.168.0.0/24"), hosts=63), 25)
        self.assertEqual(resolve_new_prefix(self.net("192.168.0.0/24"), hosts=2), 30)

    def test_impossible(self):
        with self.assertRaises(SubnetError):
            resolve_new_prefix(self.net("192.168.0.0/24"), hosts=300)
        with self.assertRaises(SubnetError):
            resolve_new_prefix(self.net("192.168.0.0/24"), new_prefix=20)

    def test_rows(self):
        rows = subnet_rows(self.net("192.168.0.0/24"), 26, None)
        self.assertEqual([r["network"] for r in rows],
                         ["192.168.0.0/26", "192.168.0.64/26", "192.168.0.128/26", "192.168.0.192/26"])
        self.assertEqual(rows[1]["first_host"], "192.168.0.65")
        self.assertEqual(rows[1]["broadcast"], "192.168.0.127")


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        buf = StringIO()
        with redirect_stdout(buf):
            code = main(list(args))
        return code, buf.getvalue()

    def test_json(self):
        code, out = self.run_cli("10.0.0.0/8", "--prefix", "24", "--json")
        data = json.loads(out)
        self.assertEqual(code, 0)
        self.assertEqual(data["subnetting"]["subnet_count"], 65536)
        self.assertEqual(len(data["subnetting"]["subnets"]), 64)
        self.assertTrue(data["subnetting"]["truncated"])

    def test_table(self):
        code, out = self.run_cli("192.168.1.0/24", "-s", "4", "--no-color")
        self.assertEqual(code, 0)
        self.assertIn("192.168.1.192/26", out)
        self.assertNotIn("\033[", out)


if __name__ == "__main__":
    unittest.main()
