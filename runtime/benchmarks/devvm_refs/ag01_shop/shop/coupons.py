import re

KINDS = ("percent", "fixed")


class CouponBook:
    def __init__(self):
        self._coupons = {}

    def add(self, code, kind, value, min_net=0):
        if not isinstance(code, str) or not re.fullmatch(r"[A-Z0-9]{3,12}", code):
            raise ValueError("code")
        if kind not in KINDS:
            raise ValueError("kind")
        if type(value) is not int or value < 1 or (kind == "percent" and value > 100):
            raise ValueError("value")
        if code in self._coupons:
            raise ValueError("duplicate")
        self._coupons[code] = {"kind": kind, "value": value, "min_net": min_net, "used": False}

    def find(self, code, net):
        coupon = self._coupons.get(str(code).upper())
        if coupon is None:
            raise ValueError("unknown_coupon")
        if coupon["used"]:
            raise ValueError("coupon_used")
        if net < coupon["min_net"]:
            raise ValueError("coupon_min")
        return coupon

    def amount(self, coupon, net):
        return (net * coupon["value"] + 50) // 100 if coupon["kind"] == "percent" else min(coupon["value"], net)

    def mark_used(self, code):
        self._coupons[str(code).upper()]["used"] = True
