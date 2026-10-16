import time

MOD = 1_000_000_007


def part(k):
    h = k
    for i in range(1, 200001):
        h = (h * 31 + i * k) % MOD
    return h


if __name__ == "__main__":
    total = 0
    for k in (1, 2, 3):
        time.sleep(15)
        value = part(k)
        print(f"part {k} of 3: {value}", flush=True)
        total = (total + value) % MOD
    print(f"TOTAL {total}", flush=True)
