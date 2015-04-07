#!/usr/bin/env python
# -*- encoding: utf-8 -*-


import sys
from httq import HTTP


http = HTTP("neo4j:password@localhost:7474", user_agent="httq/0")


def cypher(statement):
    http.post("/db/data/transaction/commit", {"statements": [{"statement": statement}]})
    if http.response().status_code == 200:
        print(http.content)
    else:
        raise RuntimeError()


def main():
    script, args = sys.argv[0], sys.argv[1:]
    cypher(args[0])


if __name__ == "__main__":
    main()
