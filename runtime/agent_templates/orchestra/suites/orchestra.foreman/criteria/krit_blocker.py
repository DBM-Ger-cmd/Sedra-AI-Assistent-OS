from antwort import ANTWORT
items = ANTWORT["teilaufgaben"]
for n, item in enumerate(items):
    for b in item["blocker"]:
        assert isinstance(b, int) and 0 <= b < len(items) and b != n, "Blocker ist eine andere Teilaufgabe"
seen, stack = set(), []
def visit(n):
    assert n not in stack, "kein Kreis von Blockern"
    if n in seen:
        return
    stack.append(n)
    for b in items[n]["blocker"]:
        visit(b)
    stack.pop()
    seen.add(n)
for n in range(len(items)):
    visit(n)
