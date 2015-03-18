#!/usr/bin/env python
# -*- encoding: utf-8 -*-


import json
import os

from httq import HTTP


http = HTTP()
http.connect(b"localhost", 7474)

try:
    LOOPS = int(os.getenv("LOOPS", "1"))
except (IndexError, ValueError):
    LOOPS = 1
BODY = json.dumps({"statements": [{"statement": "RETURN 1"}]}, ensure_ascii=True, separators=",:").encode("UTF-8")


def query():
    http.post(b"/db/data/transaction/commit", BODY, content_type=b"application/json")
    if http.response().status_code == 200:
        raw = http.read()
        if LOOPS == 1:
            print(raw)
            content = json.loads(raw.decode("UTF-8"))
            print(content)
    else:
        raise RuntimeError()


def main():
    for i in range(LOOPS):
        query()


if __name__ == "__main__":
    main()
