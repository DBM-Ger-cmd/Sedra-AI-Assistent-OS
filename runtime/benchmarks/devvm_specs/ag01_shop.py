"""AG-01 agent test (Captain 2026-10-12: "beide Modelle sollen und duerfen Agenten nutzen; wenn die Tests dafuer nicht geeignet sind, neue anlegen"). Unlike the E-specs
(one new module from scratch, where an explorer has nothing to read) the work here is a CHANGE to an existing package of eight files (benchmarks/devvm_seeds/ag01_shop):
the rules sit in several files (cart, catalog, discounts, tax, money, orders, report), so reading, reviewing and asking a helper can pay off. Run with
--seed benchmarks/devvm_seeds/ag01_shop and --mode delegating (helpers: explorer, reviewer, strong coder) or --mode solo for the comparison. Claude wrote the seed,
this file, the hidden tests (expected numbers worked out by hand) and the reference (benchmarks/devvm_refs/ag01_shop)."""

SEED = "benchmarks/devvm_seeds/ag01_shop"      # PIPE-10: devvm_build takes this folder as --seed when none is given
NOTES = '''# Notes for the shop
The package `shop/` already exists and works; read shop/README.md first. All money is in integer cents; percent_of rounds half up.
Change only what a stage asks for, keep every existing name and behaviour, standard library only, no comments and no docstrings in new code.
'''

COMMON = r'''
from shop.catalog import Catalog
from shop.cart import Cart
from shop.orders import OrderBook
from shop.discounts import Rules
IMPORTS
ITEMS = {"A": {"name": "Apple", "price": 120, "stock": 10, "category": "reduced"},
         "B": {"name": "Bread", "price": 250, "stock": 5, "category": "reduced"},
         "C": {"name": "Cable", "price": 999, "stock": 3, "category": "standard"},
         "D": {"name": "Doc", "price": 1500, "stock": 2, "category": "exempt"},
         "E": {"name": "Eraser", "price": 120, "stock": 50, "category": "standard"}}

def raises(kind, text, fn, *args, **kw):
    try:
        fn(*args, **kw)
    except kind as e:
        assert str(e).strip("'") == text, (str(e), text)
        return
    raise AssertionError(f"no {kind.__name__}({text!r})")
BODY
print("ok")
'''


def hidden(imports, body):
    return COMMON.replace("IMPORTS", imports).replace("BODY", body)


C1 = r"""
cat = Catalog(ITEMS)
cart = Cart(cat)
cart.add("C", 2); cart.add("C", 1)
raises(ValueError, "out_of_stock", cart.add, "C", 1)
assert [(l["sku"], l["qty"]) for l in cart.lines()] == [("C", 3)]
raises(ValueError, "out_of_stock", cart.add, "D", 3)
assert [l["sku"] for l in cart.lines()] == ["C"]
raises(KeyError, "unknown_sku", cart.add, "X", 1)
raises(ValueError, "qty", cart.add, "A", 0)
book = OrderBook(cat)
order = book.place(cart)
assert order["number"] == 1 and cat.stock("C") == 0
raises(ValueError, "out_of_stock", Cart(cat).add, "C", 1)
c3 = Cart(cat); c3.add("A", 4); c3.add("B", 5)
c4 = Cart(cat); c4.add("B", 3)
o2 = book.place(c3)
assert cat.stock("B") == 0 and cat.stock("A") == 6
raises(ValueError, "out_of_stock", book.place, c4)
assert cat.stock("A") == 6 and cat.stock("B") == 0 and len(book.orders) == 2
assert o2["totals"]["subtotal"] == 480 + 1250 and o2["totals"]["net"] == 1730
cat2 = Catalog(ITEMS)
c6 = Cart(cat2); c6.add("A", 3); c6.add("D", 2)
cat2.take("D", 1)
book2 = OrderBook(cat2)
raises(ValueError, "out_of_stock", book2.place, c6)
assert cat2.stock("A") == 10 and cat2.stock("D") == 1 and book2.orders == []
c7 = Cart(Catalog(ITEMS)); c7.add("A", 4)
o7 = OrderBook(c7.catalog).place(c7)
assert o7["totals"]["net"] == 480 and o7["totals"]["tax"] == 34 and o7["totals"]["total"] == 514
raises(ValueError, "empty_cart", OrderBook(cat).place, Cart(cat))
"""

C2 = r"""
books = CouponBook()
books.add("SAVE10", "percent", 10)
books.add("FIVE", "fixed", 500, min_net=2000)
books.add("BIG", "fixed", 10000)
books.add("SEVEN", "percent", 7)
for args, text in ((("ab", "percent", 10), "code"), (("TOOLONGCODE123", "percent", 10), "code"), (("X1!", "fixed", 5), "code"), ((5, "fixed", 5), "code"),
                   (("HALF", "half", 50), "kind"), (("ZERO", "percent", 0), "value"), (("OVER", "percent", 101), "value"), (("NIL", "fixed", 0), "value"),
                   (("FLT", "fixed", 2.5), "value"), (("SAVE10", "percent", 20), "duplicate")):
    raises(ValueError, text, books.add, *args)
cat = Catalog(ITEMS)
rules = Rules(); rules.buy_x_pay_y("A", 3, 2)
book = OrderBook(cat, rules, books)
cart = Cart(cat); cart.add("A", 4); cart.add("B", 2); cart.add("C", 1)
o = book.place(cart, coupon="SAVE10")
assert o["coupon"] == "SAVE10"
assert [(l["sku"], l["discount"], l["coupon"], l["net"], l["tax"]) for l in o["lines"]] == [("A", 120, 36, 324, 23), ("B", 0, 50, 450, 32), ("C", 0, 100, 899, 171)]
assert o["totals"] == {"subtotal": 1979, "discount": 120, "coupon": 186, "net": 1673, "tax": 226, "total": 1899}
assert cat.stock("A") == 6 and cat.stock("C") == 2
again = Cart(cat); again.add("A", 1)
raises(ValueError, "coupon_used", book.place, again, coupon="save10")
raises(ValueError, "unknown_coupon", book.place, again, coupon="NOPE")
assert cat.stock("A") == 6 and len(book.orders) == 1
plain = book.place(again)
assert plain["coupon"] is None and plain["totals"]["coupon"] == 0 and plain["lines"][0]["coupon"] == 0
cat2 = Catalog(ITEMS)
book2 = OrderBook(cat2, None, books)
small = Cart(cat2); small.add("B", 2)
raises(ValueError, "coupon_min", book2.place, small, coupon="FIVE")
assert cat2.stock("B") == 5 and book2.orders == []
doc = Cart(cat2); doc.add("D", 2)
od = book2.place(doc, coupon="five")
assert od["coupon"] == "FIVE" and od["totals"] == {"subtotal": 3000, "discount": 0, "coupon": 500, "net": 2500, "tax": 0, "total": 2500}
raises(ValueError, "coupon_used", book2.place, small, coupon="FIVE")
one = Cart(cat2); one.add("A", 1)
ob = book2.place(one, coupon="BIG")
assert ob["totals"]["coupon"] == 120 and ob["totals"]["net"] == 0 and ob["totals"]["total"] == 0
tie = Cart(cat2); tie.add("A", 1); tie.add("E", 1)
ot = book2.place(tie, coupon="SEVEN")
assert [(l["sku"], l["coupon"], l["net"], l["tax"]) for l in ot["lines"]] == [("A", 9, 111, 8), ("E", 8, 112, 21)]
assert ot["totals"]["coupon"] == 17 and ot["totals"]["net"] == 223 and ot["totals"]["tax"] == 29 and ot["totals"]["total"] == 252
nocoupons = OrderBook(Catalog(ITEMS))
c = Cart(nocoupons.catalog); c.add("A", 1)
raises(ValueError, "unknown_coupon", nocoupons.place, c, coupon="SAVE10")
assert nocoupons.place(c)["totals"]["coupon"] == 0
"""

C3 = r"""
from shop.report import daily
cat = Catalog(ITEMS)
cb = CouponBook(); cb.add("SAVE10", "percent", 10); cb.add("FIVE", "fixed", 500, min_net=2000)
rules = Rules(); rules.buy_x_pay_y("A", 3, 2)
book = OrderBook(cat, rules, cb)
cart = Cart(cat); cart.add("A", 4); cart.add("B", 2); cart.add("C", 1)
o1 = book.place(cart, coupon="SAVE10")
doc = Cart(cat); doc.add("D", 2)
o2 = book.place(doc, coupon="FIVE")
old = {"number": 9, "lines": [{"sku": "Z", "qty": 1}], "totals": {"net": 100, "tax": 19}}
r = daily([o1, o2, old])
assert r == {"orders": 3, "net": "42.73", "tax": "2.45", "top": [("A", 4), ("B", 2), ("D", 2)], "coupons": 2, "coupon_total": "6.86"}
assert daily([]) == {"orders": 0, "net": "0.00", "tax": "0.00", "top": [], "coupons": 0, "coupon_total": "0.00"}
"""

STAGES = [
    {"name": "stock",
     "task": """The shop package in the workspace (read shop/README.md) sells more than it has. Fix this, keep everything else:
- Cart.add: when the quantity of the sku already in the cart plus qty is more than the stock of that sku in the catalog, raise ValueError("out_of_stock") and leave the cart unchanged (the existing checks for qty < 1 and an unknown sku stay first).
- OrderBook.place: before anything is taken from the stock, check every line of the cart against the current stock; if any line has more than the stock (the stock may have changed after the items went into the cart), raise ValueError("out_of_stock") and change nothing: no stock is taken and no order is added.""",
     "hidden": {"hidden_ag01_1.py": hidden("", C1)}},
    {"name": "coupons",
     "task": """Add coupons to the shop package (read shop/README.md, money.py, tax.py, discounts.py and orders.py first). Keep everything else.
- New file shop/coupons.py with class CouponBook: add(code, kind, value, min_net=0). code: a str of 3 to 12 characters, only A-Z and 0-9, else ValueError("code"); kind: "percent" or "fixed", else ValueError("kind"); value: an int (not a float) >= 1 and for "percent" at most 100, else ValueError("value"); an existing code: ValueError("duplicate"). Check in this order.
- OrderBook(catalog, rules=None, coupons=None) and place(cart, coupon=None). With a coupon code (compared case-insensitively): no CouponBook or an unknown code -> ValueError("unknown_coupon"); a code already used by a placed order -> ValueError("coupon_used"); the net after the rule discounts (sum over the lines of amount - discount) below min_net -> ValueError("coupon_min"). These errors, like out_of_stock, change nothing.
- The coupon amount is computed on that net total: percent -> percent_of(net, value); fixed -> min(value, net). It is split over the lines in proportion to their net: each line gets amount * line_net // net_total; the cents that are left go one each to the lines with the largest net (ties: the line that comes first, the lines are sorted by sku). A net total of 0 gives every line 0.
- Each order line gets the key "coupon" (its share, 0 without coupon); its "net" becomes amount - discount - coupon share and its "tax" is tax_for(category, that net). totals gets "coupon" (the coupon amount, 0 without coupon); subtotal, discount, net, tax and total keep their meaning (net and tax after the coupon). The order gets "coupon": the code in upper case, or None.
- A coupon is used only when its order was placed.""",
     "hidden": {"hidden_ag01_2.py": hidden("from shop.coupons import CouponBook", C1 + C2)}},
    {"name": "report",
     "task": """Extend shop/report.py daily(orders) by two keys, keep the others unchanged: "coupons" (the number of orders whose "coupon" is set and not None; orders from before the coupons have no such key) and "coupon_total" (fmt of the sum of totals["coupon"] over all orders, a missing key counts 0).""",
     "hidden": {"hidden_ag01_3.py": hidden("from shop.coupons import CouponBook", C1 + C2 + C3)}},
]
