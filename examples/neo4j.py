#!/usr/bin/env python
# -*- encoding: utf-8 -*-


import json
import os

from httq import HTTP, basic_auth


http = HTTP(b"localhost:7474", authorization=basic_auth("neo4j", "password"), user_agent=b"httq/0", content_type=b"application/json")

try:
    loops = int(os.getenv("LOOPS", "1"))
except (IndexError, ValueError):
    loops = 1

body = json.dumps({"statements": [{"statement": "RETURN 1"}]}, ensure_ascii=True, separators=",:").encode("UTF-8")


def query():
    if http.request(b"POST", b"/db/data/transaction/commit", body).response().status_code == 200:
        if loops == 1:
            print(http.content)
    else:
        raise RuntimeError()


def main():
    for i in range(loops):
        query()


if __name__ == "__main__":
    main()
