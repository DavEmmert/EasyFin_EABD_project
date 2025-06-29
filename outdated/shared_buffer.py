from collections import defaultdict, deque

MAX_BUFFER_SIZE = 86400
label_price_buffer = defaultdict(lambda: deque(maxlen=MAX_BUFFER_SIZE))
topics_to_listen = [
    "AAPL_live",
    "BTC-USD_live",
    "NVDA_live",
    "energy_live",
    "ev_live",
]
