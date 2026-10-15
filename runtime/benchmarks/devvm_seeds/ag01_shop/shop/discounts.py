from .money import percent_of


class Rules:
    def __init__(self):
        self._percent = {}
        self._multi = {}

    def percent_off(self, sku, percent):
        self._percent[sku] = percent

    def buy_x_pay_y(self, sku, x, y):
        self._multi[sku] = (x, y)

    def line_discount(self, line):
        discount = 0
        if line["sku"] in self._multi:
            x, y = self._multi[line["sku"]]
            discount += (line["qty"] // x) * (x - y) * line["price"]
        if line["sku"] in self._percent:
            discount += percent_of(line["amount"] - discount, self._percent[line["sku"]])
        return discount
