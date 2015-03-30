#!/usr/bin/env python
# -*- encoding: utf-8 -*-


import json
import os

from httq import HTTP, basic_auth


http = HTTP("localhost:7474", authorization=basic_auth("neo4j", "password"), x_stream=True, user_agent=b"httq/0")

try:
    loops = int(os.getenv("LOOPS", "1"))
except (IndexError, ValueError):
    loops = 1

body = json.dumps({"statements": [{"statement": "RETURN 1"}]}, ensure_ascii=True, separators=",:").encode("UTF-8")


def query():
    http.post(b"/db/data/transaction/commit", body, content_type=b"application/json")
    if http.response().status_code == 200:
        raw = http.content
        if loops == 1:
            print(raw)
            content = json.loads(raw.decode("UTF-8"))
            print(content)
    else:
        raise RuntimeError()


def main():
    for i in range(loops):
        query()


if __name__ == "__main__":
    main()
