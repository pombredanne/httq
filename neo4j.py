#!/usr/bin/env python
# -*- encoding: utf-8 -*-


import json

from httq import HTTP, POST


http = HTTP()
http.connect(b"localhost", 7474)


payload = json.dumps({"statements": [{"statement": "RETURN 1"}]}, ensure_ascii=True, separators=",:").encode("UTF-8")


def main():
    http.request(POST, b"/db/data/transaction/commit", {b"Content-Type": b"application/json"})
    http.write(payload, b"")
    if http.response() == 200:
        raw = http.read()
        # print(raw)
        # content = json.loads(raw.decode("UTF-8"))
        # print(content)
    else:
        raise RuntimeError()


if __name__ == "__main__":
    main()
