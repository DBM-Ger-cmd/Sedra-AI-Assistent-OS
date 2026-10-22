from antwort import ANTWORT
assert isinstance(ANTWORT, dict) and set(ANTWORT) == {"lesen", "frage"}, "nur lesen und frage"
urls = ANTWORT["lesen"]
assert isinstance(urls, list) and 1 <= len(urls) <= 5, "1 bis 5 Adressen"
for url in urls:
    assert isinstance(url, str) and url.startswith(("https://", "http://")) and not any(c.isspace() for c in url), "eine Adresse"
assert isinstance(ANTWORT["frage"], str) and ANTWORT["frage"].strip(), "eine Frage"
