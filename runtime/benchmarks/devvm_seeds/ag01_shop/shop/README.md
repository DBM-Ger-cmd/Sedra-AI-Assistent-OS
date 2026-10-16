# shop

A small shop core. All money is in integer cents.
- money.py: fmt(cents) -> "12.34", percent_of(cents, percent) rounds half up.
- catalog.py: Catalog(items) with get, stock, take.
- cart.py: Cart(catalog) with add, remove, lines, subtotal.
- discounts.py: Rules with percent_off and buy_x_pay_y; line_discount(line).
- tax.py: RATES per category and tax_for(category, net).
- orders.py: OrderBook(catalog, rules=None).place(cart) -> order dict with lines and totals; takes the stock.
- report.py: daily(orders) -> summary dict.
