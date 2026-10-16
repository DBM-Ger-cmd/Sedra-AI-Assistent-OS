from .money import percent_of

RATES = {"standard": 19, "reduced": 7, "exempt": 0}


def tax_for(category, net):
    return percent_of(net, RATES[category])
