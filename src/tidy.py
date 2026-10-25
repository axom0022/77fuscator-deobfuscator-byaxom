import sys

words = set()
for w in ("and break do else elseif end false for function if in local nil not or "
          "repeat return then true until while goto").split():
    words.add(w)

banner = ("-- [[ deobfuscated by Axomic 77fuscator Deobfuscator | "
          "our discord server : https://discord.gg/Sps39CydcZ | "
          "Our YouTube channel : https://youtube.com/@axos0022 ]]")


def toks(text):
    out = []
    i = 0
    n = len(text)
    while i < n:
        c = text[i]
        if c in "\"'":
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == c:
                    break
                j += 1
            out.append(("s", text[i:j + 1]))
            i = j + 1
        elif c.isalpha() or c == "_":
            j = i
            while j < n and (text[j].isalnum() or text[j] == "_"):
                j += 1
            out.append(("w", text[i:j]))
            i = j
        elif c.isdigit():
            j = i
            while j < n and (text[j].isalnum() or text[j] == "."):
                j += 1
            out.append(("n", text[i:j]))
            i = j
        elif c in " \t":
            i += 1
        else:
            got = None
            for size in (3, 2):
                if text[i:i + size] in ("...", "..=", "..", "==", "~=", "<=", ">=", "::", "//"):
                    got = text[i:i + size]
                    break
            if got is None:
                got = c
            out.append(("p", got))
            i += len(got)
    return out


def join(items):
    out = []
    prev = None
    was = None
    for kind, text in items:
        space = False
        if prev is not None:
            if kind == "p" and text in ")]},;:.":
                space = False
            elif prev in "([{.:#":
                space = False
            elif kind == "p" and text == "(":
                space = was != "w" or prev in words
            elif kind == "p" and text == "[":
                space = False
            elif kind == "p" and text == "#":
                space = True
            else:
                space = True
        if space:
            out.append(" ")
        out.append(text)
        prev = text
        was = kind
    return "".join(out)


def plain(text):
    return " ".join(t[1] for t in toks(text))


def split(text):
    t = toks(text)
    depth = 0
    for i, (k, v) in enumerate(t):
        if k == "p" and v in "([{":
            depth += 1
        elif k == "p" and v in ")]}":
            depth -= 1
        elif k == "p" and v == "=" and depth == 0:
            nxt = t[i + 1][1] if i + 1 < len(t) else ""
            prv = t[i - 1][1] if i > 0 else ""
            if nxt == "=" or prv in "=<>~":
                continue
            lhs = "".join(x[1] for x in t[:i]).strip()
            rhs = "".join(x[1] for x in t[i + 1:]).strip()
            return lhs, rhs
    return None


def parts(lhs):
    t = toks(lhs)
    depth = 0
    cur = []
    out = []
    for k, v in t:
        if k == "p" and v == "," and depth == 0:
            out.append(cur)
            cur = []
            continue
        if k == "p" and v in "([{":
            depth += 1
        elif k == "p" and v in ")]}":
            depth -= 1
        cur.append((k, v))
    out.append(cur)
    return out


def targets(lhs):
    names = []
    reads = []
    for part in parts(lhs):
        reserved = [v for k, v in part if k == "w" and v not in words]
        if len(part) == 1 and part[0][0] == "w" and part[0][1] not in words:
            names.append(part[0][1])
        else:
            reads.extend(reserved)
    return names, reads


def refs(text):
    return [v for k, v in toks(text) if k == "w" and v not in words]


def pure(text):
    for k, v in toks(text):
        if k == "p" and v in "([.":
            return False
        if k == "w" and v == "function":
            return False
    return True


def atom(text):
    if text == "":
        return False
    if text.replace(".", "").replace("_", "").isalnum() and text[0].isalpha():
        return True
    if text[0] in "\"'":
        return True
    if text in ("true", "false", "nil"):
        return True
    neg = text[1:] if text.startswith("-") else text
    if neg.replace(".", "").isdigit():
        return text == neg
    return False


def wrap(text):
    if atom(text):
        return text
    return "(" + text + ")"


def sub(text, env, depth, tick):
    t = toks(text)
    out = []
    prev = None
    for i, (k, v) in enumerate(t):
        if k == "w" and v not in words and prev not in (".", ":"):
            item = env.get(v)
            nxt = t[i + 1][1] if i + 1 < len(t) else None
            near = item is not None and tick is not None and (tick - item["tick"]) <= 1
            if item is not None and nxt in (".", ":", "["):
                near = False
            if item is not None and prev == "[":
                near = False
            if item is not None and len(item["text"]) > 60:
                near = False
            if item is not None and not item["pure"] and not (near and item["used"] == 0):
                item = None
            if item is not None:
                item["used"] += 1
                text2 = wrap(item["text"])
                out.extend(toks(text2))
                prev = ")"
            else:
                out.append((k, v))
                prev = k
        else:
            out.append((k, v))
            prev = k if k == "p" else k
    return join(out)


def merge(lines):
    i = 0
    while i + 1 < len(lines):
        a = lines[i]
        b = lines[i + 1]
        if a["k"] == "ln" and b["k"] == "ln":
            got = split(a["s"])
            if got and got[0].strip() in got[0]:
                name = got[0].strip()
                if name.isidentifier() and name not in words:
                    got2 = split(b["s"])
                    if got2:
                        lhs2, rhs2 = got2
                        if rhs2.startswith(name + "(") and rhs2.endswith(")"):
                            inner = rhs2[len(name) + 1:-1]
                            slot = parts(lhs2)
                            args = parts(inner) if inner.strip() else []
                            if len(slot) == len(args) and all(
                                    "".join(x[1] for x in slot[k]).strip() ==
                                    "".join(x[1] for x in args[k]).strip() for k in range(len(slot))):
                                b["s"] = lhs2 + " = " + got[1].strip() + "(" + inner + ")"
                                del lines[i]
                                continue
        i += 1
    for node in lines:
        if node["k"] in ("func", "while", "for", "do", "repeat"):
            merge(node["b"])
        elif node["k"] == "if":
            merge(node["b"])
            for cond, body in node["cl"]:
                merge(body)
            if node["e"]:
                merge(node["e"])
    return lines


def pool(lines):
    count = {}
    value = {}

    def walk(lst):
        for node in lst:
            if node["k"] == "ln":
                got = split(node["s"])
                if got:
                    name = got[0].strip()
                    if name.isidentifier():
                        count[name] = count.get(name, 0) + 1
                        value[name] = got[1].strip()
            elif node["k"] == "if":
                walk(node["b"])
                for cond, body in node["cl"]:
                    walk(body)
                if node["e"]:
                    walk(node["e"])
            else:
                walk(node["b"])
    walk(lines)
    out = {}
    for name, c in count.items():
        if c != 1:
            continue
        v = value[name]
        if v.startswith('"') and v.endswith('"'):
            out[name] = v
        elif v in ("true", "false", "nil"):
            out[name] = v
        elif v.lstrip("-").replace(".", "").isdigit():
            out[name] = v
    changed = True
    while changed:
        changed = False
        for name, c in count.items():
            if c == 1 and name not in out and value.get(name) in out:
                out[name] = out[value[name]]
                changed = True
    return out


def store(text):
    got = split(text)
    if not got:
        return None, None, None
    lhs, rhs = got
    t = toks(lhs)
    if len(t) >= 4 and t[0][0] == "w" and t[1][1] == "[":
        return t[0][1], "".join(x[1] for x in t[2:-1]).strip(), rhs
    return None, None, None


def tabs(lines):
    counts = {}
    stores = {}

    def walk(lst):
        for node in lst:
            if node["k"] == "ln":
                base, key, rhs = store(node.get("new", node["s"]))
                if base:
                    counts[base] = counts.get(base, 0) + 1
                    stores.setdefault(base, []).append((node, key, rhs))
                got = split(node.get("new", node["s"]))
                if got and got[1].strip() == "{}":
                    name = got[0].strip()
                    counts[name] = counts.get(name, 0) + 0
            elif node["k"] == "if":
                walk(node["b"])
                for cond, body in node["cl"]:
                    walk(body)
                if node["e"]:
                    walk(node["e"])
            else:
                walk(node["b"])
    walk(lines)
    lits = pool(lines)
    map = {}
    for name, val in lits.items():
        map[name] = val
    out = {}
    for base, c in counts.items():
        if c < 3:
            continue
        if map.get(base, "{}") != "{}":
            continue
        mapping = {}
        ok = True
        for node, key, rhs in stores.get(base, []):
            val = plain(rhs)
            if val in lits:
                val = lits[val]
            if key is None:
                ok = False
                break
            mapping[key] = val
        if ok and mapping:
            out[base] = mapping
    return out


def swap(text, pool):
    out = text
    for base, mapping in pool.items():
        res = []
        i = 0
        while i < len(out):
            at = out.find(base + "[", i)
            if at < 0:
                res.append(out[i:])
                break
            before = out[at - 1] if at > 0 else " "
            if before.isalnum() or before in "._":
                res.append(out[i:at + len(base) + 1])
                i = at + len(base) + 1
                continue
            close = out.find("]", at)
            if close < 0:
                res.append(out[i:])
                break
            key = out[at + len(base) + 1:close].strip()
            if key in mapping:
                res.append(out[i:at])
                res.append(mapping[key])
                i = close + 1
            else:
                res.append(out[i:close + 1])
                i = close + 1
        out = "".join(res)
    return out


def untab(lines, pool):
    out = []
    for node in lines:
        if node["k"] == "ln":
            drop = False
            if "new" not in node:
                node["new"] = node["s"]
            text = node["new"]
            for base in pool:
                got = split(text)
                if got and got[0].strip() == base and got[1].strip() == "{}":
                    drop = True
                if text.startswith(base + "["):
                    drop = True
                if got and got[1].strip() == base:
                    drop = True
            if not drop:
                node["new"] = swap(text, pool)
                out.append(node)
        else:
            if node["k"] == "if":
                node["c"] = swap(node["c"], pool)
                node["b"] = untab(node["b"], pool)
                for pair in node["cl"]:
                    pair[0] = swap(pair[0], pool)
                    pair[1] = untab(pair[1], pool)
                if node["e"]:
                    node["e"] = untab(node["e"], pool)
            elif node["k"] == "while":
                node["c"] = swap(node["c"], pool)
                node["b"] = untab(node["b"], pool)
            elif node["k"] == "repeat":
                node["b"] = untab(node["b"], pool)
                node["u"] = swap(node["u"], pool)
            elif node["k"] == "for":
                node["h"] = swap(node["h"], pool)
                node["b"] = untab(node["b"], pool)
            else:
                node["b"] = untab(node["b"], pool)
            out.append(node)
    return out


def walk(lines, env, depth, loop, tick):
    tick[0] += 0
    out = env
    for node in lines:
        if node["k"] == "ln":
            tick[0] += 1
            text = node.get("new", node["s"])
            if loop and split(text):
                lhs, rhs = split(text)
                common = set(refs(rhs))
                for name in targets(lhs)[0]:
                    if name in common and not pure(env.get(name, {"text": "x"})["text"]):
                        out.pop(name, None)
            if text.startswith("local "):
                rest = text[len("local "):].strip()
                got = split(rest)
                if got:
                    lhs, rhs = got
                    rhs2 = sub(rhs, out, depth, tick[0])
                    name = lhs.strip()
                    node["new"] = "local " + name + " = " + rhs2
                    if name.isidentifier():
                        out[name] = {"text": rhs2, "pure": pure(rhs2), "depth": depth,
                                     "used": 0, "tick": tick[0]}
                    node["def"] = name
                    node["rhs"] = rhs2
                else:
                    node["new"] = text
                    node["decl"] = [v for k, v in toks(rest) if k == "w" and v not in words]
                    for name in node["decl"]:
                        out.pop(name, None)
            else:
                got = split(text)
                if got:
                    lhs, rhs = got
                    rhs2 = sub(rhs, out, depth, tick[0])
                    node["new"] = lhs + " = " + rhs2
                    name = lhs.strip()
                    node["rhs"] = rhs2
                    if name.isidentifier() and name not in words:
                        node["def"] = name
                        out[name] = {"text": rhs2, "pure": pure(rhs2), "depth": depth,
                                     "used": 0, "tick": tick[0]}
                    else:
                        for nm in refs(lhs):
                            out.pop(nm, None)
                        node["multi"] = True
                else:
                    node["new"] = sub(text, out, depth, tick[0])
        elif node["k"] == "if":
            node["c"] = sub(node["c"], out, depth, tick[0])
            seen = []
            inner = dict(out)
            walk(node["b"], inner, depth + 1, loop, tick)
            seen.extend(n for n in inner if n not in out)
            for pair in node["cl"]:
                pair[0] = sub(pair[0], out, depth, tick[0])
                e2 = dict(out)
                walk(pair[1], e2, depth + 1, loop, tick)
                seen.extend(n for n in e2 if n not in out)
            if node["e"]:
                e3 = dict(out)
                walk(node["e"], e3, depth + 1, loop, tick)
                seen.extend(n for n in e3 if n not in out)
            for name in seen:
                out.pop(name, None)
        elif node["k"] in ("while", "for", "repeat"):
            if node["k"] == "for":
                head = toks(node["h"])
                if head and head[0][0] == "w":
                    rest = join(head[1:])
                    node["h"] = head[0][1] + " " + sub(rest, out, depth, tick[0])
                else:
                    node["h"] = sub(node["h"], out, depth, tick[0])
            else:
                node["c"] = sub(node["c"], out, depth, tick[0])
            walk(node["b"], {}, depth + 1, True, tick)
            if node["k"] == "repeat":
                node["u"] = sub(node["u"], {}, depth + 1, tick[0])
            for name in mine(node):
                out.pop(name, None)
        elif node["k"] == "func":
            walk(node["b"], {}, depth + 1, loop, tick)
            name = title(node["h"])
            if name:
                out.pop(name, None)
            for inner in upvalues(node["b"]):
                out.pop(inner, None)
        elif node["k"] == "do":
            walk(node["b"], dict(out), depth + 1, loop, tick)
    return out


def title(head):
    t = toks(head)
    if len(t) >= 3 and t[0][1] == "local" and t[1][1] == "function":
        return t[2][1]
    if len(t) >= 2 and t[0][1] == "function":
        return t[1][1]
    return None


def mine(node):
    found = set()

    def go(lst):
        for item in lst:
            if item["k"] == "ln":
                text = item.get("new", item["s"])
                got = split(text)
                if got:
                    for name in targets(got[0])[0]:
                        found.add(name)
                elif text.startswith("local "):
                    for k, v in toks(text):
                        if k == "w" and v not in words:
                            found.add(v)
            elif item["k"] == "if":
                go(item["b"])
                for pair in item["cl"]:
                    go(pair[1])
                if item["e"]:
                    go(item["e"])
            elif item["k"] == "for":
                first = toks(item["h"])
                if first:
                    found.add(first[0][1])
                go(item["b"])
            elif item["k"] in ("while", "repeat", "do"):
                go(item["b"])
    go(node["b"] if node["k"] != "ln" else [node])
    return found


def upvalues(lines):
    found = set()

    def go(lst):
        for item in lst:
            if item["k"] == "ln":
                text = item.get("new", item["s"])
                got = split(text)
                if got:
                    for name in targets(got[0])[0]:
                        found.add(name)
            elif item["k"] == "if":
                go(item["b"])
                for pair in item["cl"]:
                    go(pair[1])
                if item["e"]:
                    go(item["e"])
            elif item["k"] == "func":
                go(item["b"])
            elif item["k"] in ("while", "for", "repeat", "do"):
                go(item["b"])
    go(lines)
    return found


def events(lines):
    ev = []
    idx = [0]
    skip = set()

    def roam(lst, nest):
        for node in lst:
            idx[0] += 1
            if node["k"] == "ln":
                text = node.get("new", node["s"])
                if text.startswith("local "):
                    rest = text[6:]
                    got = split(rest)
                    if got:
                        text = got[0] + " = " + got[1]
                    else:
                        for name in node.get("decl", []):
                            skip.add(name)
                        for k, v in toks(rest):
                            if k == "w" and v not in words:
                                ev.append((idx[0], "d", v, None, False))
                        continue
                got = split(text)
                if got:
                    lhs, rhs = got
                    names, reads = targets(lhs)
                    for name in reads:
                        ev.append((idx[0], "r", name, None, False))
                    for name in names:
                        if nest:
                            skip.add(name)
                        ev.append((idx[0], "d", name, node, pure(rhs)))
                    for name in refs(rhs):
                        ev.append((idx[0], "r", name, None, False))
                else:
                    for name in refs(text):
                        ev.append((idx[0], "r", name, None, False))
            elif node["k"] == "if":
                for name in refs(node["c"]):
                    ev.append((idx[0], "r", name, None, False))
                roam(node["b"], nest)
                for pair in node["cl"]:
                    for name in refs(pair[0]):
                        ev.append((idx[0], "r", name, None, False))
                    roam(pair[1], nest)
                if node["e"]:
                    roam(node["e"], nest)
            elif node["k"] in ("while", "repeat"):
                for name in refs(node["c"] if node["k"] == "while" else node["u"]):
                    ev.append((idx[0], "r", name, None, False))
                roam(node["b"], True)
            elif node["k"] == "for":
                for name in refs(node["h"]):
                    ev.append((idx[0], "r", name, None, False))
                roam(node["b"], True)
            elif node["k"] == "func":
                name = title(node["h"])
                if name:
                    ev.append((idx[0], "d", name, node, False))
                roam(node["b"], True)
            elif node["k"] == "do":
                roam(node["b"], nest)
    roam(lines, False)
    return ev, skip


def prune(lines):
    out = []
    for node in lines:
        if node["k"] == "ln":
            if not node.get("dead"):
                out.append(node)
        elif node["k"] == "if":
            node["b"] = prune(node["b"])
            extra = []
            for pair in node["cl"]:
                body = prune(pair[1])
                extra.append([pair[0], body])
            node["cl"] = extra
            if node["e"]:
                node["e"] = prune(node["e"])
            if node["b"] or node["cl"] or node["e"]:
                out.append(node)
        else:
            node["b"] = prune(node["b"])
            out.append(node)
    return out


def obf(name):
    if len(name) < 4 or "_" not in name:
        return False
    head, _, tail = name.partition("_")
    if head[:1] not in ("L", "A"):
        return False
    return head[1:].isdigit() and tail.isdigit()


def versionize(lines):
    cur = {}
    dirty = {}
    total = [0]

    def fresh(name):
        total[0] += 1
        cur[name] = "k%d" % total[0]
        return cur[name]

    def read(text):
        t = toks(text)
        out = []
        prev = None
        for k, v in t:
            if k == "w" and v not in words and prev not in (".", ":") and obf(v):
                if v not in cur:
                    fresh(v)
                out.append(("w", cur[v]))
                dirty[v] = True
            else:
                out.append((k, v))
            prev = v if k == "p" else None
        return join(out)

    def define(lhs):
        t = toks(lhs)
        out = []
        depth = 0
        prev = None
        for k, v in t:
            if k == "p" and v in "([{":
                depth += 1
            elif k == "p" and v in ")]}":
                depth -= 1
            if k == "w" and v not in words and depth == 0 and prev not in (".", ":") and obf(v):
                if v not in cur:
                    fresh(v)
                if dirty.get(v):
                    fresh(v)
                out.append(("w", cur[v]))
                dirty[v] = False
            else:
                out.append((k, v))
            prev = v if k == "p" else None
        return join(out)

    def go(lst):
        for node in lst:
            if node["k"] == "ln":
                text = node.get("new", node["s"])
                if text.startswith("local "):
                    rest = text[6:]
                    got = split(rest)
                    if got:
                        value = read(got[1])
                        node["new"] = "local " + define(got[0]) + " = " + value
                    else:
                        node["new"] = "local " + define(rest)
                else:
                    got = split(text)
                    if got:
                        value = read(got[1])
                        node["new"] = define(got[0]) + " = " + value
                    else:
                        node["new"] = read(text)
            elif node["k"] == "if":
                node["c"] = read(node["c"])
                go(node["b"])
                for pair in node["cl"]:
                    pair[0] = read(pair[0])
                    go(pair[1])
                if node["e"]:
                    go(node["e"])
            elif node["k"] == "while":
                node["c"] = read(node["c"])
                go(node["b"])
            elif node["k"] == "repeat":
                go(node["b"])
                node["u"] = read(node["u"])
            elif node["k"] == "for":
                t = toks(node["h"])
                first = t[0][1] if t else None
                rest = node["h"][len(first):] if first else node["h"]
                if first and first not in words and obf(first):
                    total[0] += 1
                    cur[first] = "k%d" % total[0]
                    dirty[first] = False
                    node["h"] = cur[first] + read(rest)
                else:
                    node["h"] = read(node["h"])
                go(node["b"])
            elif node["k"] == "func":
                node["h"] = read(node["h"])
                go(node["b"])
            elif node["k"] == "do":
                go(node["b"])
    go(lines)
    return lines


def chain(lines):
    i = 0
    while i + 1 < len(lines):
        a = lines[i]
        b = lines[i + 1]
        done = False
        if a["k"] == "ln" and b["k"] == "ln":
            got = split(a.get("new", a["s"]))
            if got and got[0].strip().isidentifier():
                name = got[0].strip()
                got2 = split(b.get("new", b["s"]))
                if got2 and refs(got2[1]).count(name) == 1 and name not in refs(got[1]) \
                        and got2[0].strip() != name:
                    merged = sub(got2[1], {name: {"text": got[1], "pure": True,
                                                    "depth": 0, "used": 0, "tick": 0}},
                                   0, None)
                    b["new"] = got2[0] + " = " + merged
                    del lines[i]
                    done = True
        if not done:
            i += 1
    for node in lines:
        if node["k"] == "if":
            chain(node["b"])
            for pair in node["cl"]:
                chain(pair[1])
            if node["e"]:
                chain(node["e"])
        elif node["k"] in ("func", "while", "for", "do", "repeat"):
            chain(node["b"])
    return lines


def lit(text):
    t = plain(text)
    if t in ("true", "false", "nil") or t.lstrip("-").replace(".", "").isdigit():
        return True
    if t.startswith('"') and t.endswith('"'):
        return True
    return False


def judge(cond):
    t = toks(cond)
    depth = 0
    for i in range(len(t) - 1):
        k, v = t[i]
        if k == "p" and v in "([{":
            depth += 1
        elif k == "p" and v in ")]}":
            depth -= 1
        elif k == "p" and v in ("==", "~=") and depth == 0:
            lhs = join(t[:i]).strip()
            rhs = join(t[i + 1:]).strip()
            if lit(lhs) and lit(rhs):
                same = plain(lhs) == plain(rhs)
                return same if v == "==" else not same
            return None
    base = plain(cond)
    if base == "true":
        return True
    if base in ("false", "nil"):
        return False
    return None


def scoped(lines):
    for node in lines:
        if node["k"] == "ln" and node.get("new", node["s"]).startswith("local "):
            return True
        if node["k"] == "if":
            if scoped(node["b"]):
                return True
            for pair in node["cl"]:
                if scoped(pair[1]):
                    return True
            if node["e"] and scoped(node["e"]):
                return True
        elif node["k"] in ("func", "while", "for", "do", "repeat"):
            if scoped(node["b"]):
                return True
    return False


def elide(lines):
    out = []
    for node in lines:
        if node["k"] == "if":
            node["b"] = elide(node["b"])
            node["cl"] = [[pair[0], elide(pair[1])] for pair in node["cl"]]
            if node["e"]:
                node["e"] = elide(node["e"])
            value = judge(node["c"])
            if value is True:
                body = node["b"]
                if body and scoped(body):
                    out.append({"k": "do", "b": body})
                else:
                    out.extend(body)
            elif value is False:
                if node["cl"]:
                    first = node["cl"][0]
                    out.append({"k": "if", "c": first[0], "b": first[1],
                                "cl": node["cl"][1:], "e": node["e"]})
                elif node["e"]:
                    body = node["e"]
                    if body and scoped(body):
                        out.append({"k": "do", "b": body})
                    else:
                        out.extend(body)
            else:
                out.append(node)
        else:
            if node["k"] in ("func", "while", "for", "do", "repeat"):
                node["b"] = elide(node["b"])
            out.append(node)
    return out


def scope(lines):
    first = {}
    order = []
    assign = set()
    nodeof = {}
    inner = set()

    def seen(name, kind, node):
        if name not in first:
            first[name] = kind
            nodeof[name] = node
            order.append(name)

    def scan(text, where, inbody):
        got = split(text)
        if got:
            lhs, rhs = got
            names, reads = targets(lhs)
            for name in names:
                assign.add(name)
                seen(name, "inner" if inbody else "def", where)
            for name in reads:
                seen(name, "read", None)
        elif text.startswith("local "):
            rhs = ""
        else:
            rhs = text
        for name in refs(rhs):
            seen(name, "read", None)

    def go(lst, inbody):
        for node in lst:
            if node["k"] == "ln":
                scan(node.get("new", node["s"]), node, inbody)
            elif node["k"] == "if":
                for name in refs(node["c"]):
                    seen(name, "read", None)
                go(node["b"], inbody)
                for pair in node["cl"]:
                    for name in refs(pair[0]):
                        seen(name, "read", None)
                    go(pair[1], inbody)
                if node["e"]:
                    go(node["e"], inbody)
            elif node["k"] in ("while", "repeat"):
                for name in refs(node["c"] if node["k"] == "while" else node["u"]):
                    seen(name, "read", None)
                go(node["b"], inbody)
            elif node["k"] == "for":
                t = toks(node["h"])
                if t:
                    first.setdefault(t[0][1], "loop")
                rest = node["h"][len(t[0][1]):] if t else ""
                for name in refs(rest):
                    seen(name, "read", None)
                go(node["b"], inbody)
            elif node["k"] == "func":
                name = title(node["h"])
                if name:
                    assign.add(name)
                    seen(name, "inner" if inbody else "owner", node)
                head = node["h"]
                open = head.find("(")
                close = head.rfind(")")
                if open >= 0 and close > open:
                    for k, v in toks(head[open + 1:close]):
                        if k == "w" and v not in words:
                            first[v] = "param"
                go(node["b"], True)
            elif node["k"] == "do":
                go(node["b"], inbody)
    go(lines, False)
    decl = []
    for name in order:
        if name not in assign or name in words:
            continue
        kind = first[name]
        if kind == "def":
            node = nodeof[name]
            text = node.get("new", node["s"])
            if not text.startswith("local ") and split(text) and \
                    split(text)[0].strip() == name:
                node["new"] = "local " + text
            else:
                decl.append(name)
        elif kind == "owner":
            node = nodeof[name]
            if not node["h"].startswith("local "):
                node["h"] = "local " + node["h"]
        elif kind not in ("loop", "param", "inner"):
            decl.append(name)
    if decl:
        lines.insert(0, {"k": "ln", "s": "local " + ", ".join(decl),
                         "new": "local " + ", ".join(decl), "synth": True})
    return lines


def rename(lines):
    mapping = {}
    count = [0]

    def fix(text):
        out = []
        prev = None
        for k, v in toks(text):
            if k == "w" and v[:1] in ("v", "k") and v[1:].isdigit() and prev not in (".", ":"):
                if v not in mapping:
                    count[0] += 1
                    mapping[v] = "v%d" % count[0]
                out.append(("w", mapping[v]))
            else:
                out.append((k, v))
            prev = v if k == "p" else None
        return join(out)

    def go(lst):
        for node in lst:
            if node["k"] == "ln":
                node["new"] = fix(node.get("new", node["s"]))
            elif node["k"] == "if":
                node["c"] = fix(node["c"])
                go(node["b"])
                for pair in node["cl"]:
                    pair[0] = fix(pair[0])
                    go(pair[1])
                if node["e"]:
                    go(node["e"])
            elif node["k"] == "while":
                node["c"] = fix(node["c"])
                go(node["b"])
            elif node["k"] == "repeat":
                go(node["b"])
                node["u"] = fix(node["u"])
            elif node["k"] == "for":
                node["h"] = fix(node["h"])
                go(node["b"])
            elif node["k"] == "func":
                node["h"] = fix(node["h"])
                go(node["b"])
            else:
                go(node["b"])
    go(lines)
    return lines


def pairs(text):
    t = toks(text)
    stack = []
    match = {}
    for i, (k, v) in enumerate(t):
        if k == "p" and v == "(":
            stack.append(i)
        elif k == "p" and v == ")" and stack:
            match[stack.pop()] = i
    return t, match


def ops(v):
    return v in ("+", "-", "*", "/", "%", "^", "==", "~=", "<", ">", "<=", ">=",
                 "and", "or", "not", "#")


def deparen(text, whole):
    t, match = pairs(text)
    if not match:
        return text
    dots = {}
    for i in range(1, len(t)):
        if t[i][1] == "." and t[i - 1][1] == ".":
            dots[i] = True
            dots[i - 1] = True

    def behind(i):
        while i >= 0 and t[i][0] == "b":
            i -= 1
        return i if i >= 0 else None

    def ahead(i):
        while i < len(t) and t[i][0] == "b":
            i += 1
        return i if i < len(t) else None

    def prior(i):
        if i is None:
            return True
        k, v = t[i]
        if k == "w":
            return v in ("and", "or", "not", "return", "then", "do", "else",
                         "elseif", "until", "in", "local")
        if k in ("s", "n"):
            return False
        if dots.get(i):
            return True
        return v not in (")", "]", "#")

    def after(i):
        if i is None:
            return True
        k, v = t[i]
        if k in ("s", "n"):
            return False
        if dots.get(i):
            return True
        return v not in (":", "[", "{", ".")

    def ctx(pi, ni):
        if pi is not None:
            k, v = t[pi]
            if k == "w" and v in ("and", "or", "not"):
                return True
            if k == "p" and ops(v) and v not in ("(", ",", "="):
                return True
            if dots.get(pi):
                return True
        if ni is not None:
            k, v = t[ni]
            if k == "w" and v in ("and", "or"):
                return True
            if k == "p" and ops(v) and v != "#":
                return True
            if dots.get(ni):
                return True
        return False

    def truncates(open, close, pi, ni):
        last = behind(close - 1)
        if last is None:
            return False
        k, v = t[last]
        call = False
        if k == "p" and v == ")":
            depth = 0
            hit = None
            for j in range(last, -1, -1):
                if t[j][0] == "p" and t[j][1] == ")":
                    depth += 1
                if t[j][0] == "p" and t[j][1] == "(":
                    depth -= 1
                    if depth == 0:
                        hit = j
                        break
            if hit is None:
                call = True
            else:
                before = t[behind(hit - 1)] if behind(hit - 1) is not None else None
                if before is not None:
                    if before[0] == "w" and before[1] not in words:
                        call = True
                    elif before[0] == "p" and before[1] in (")", "]"):
                        call = True
        a3 = behind(last - 1)
        if a3 is not None and dots.get(a3) and dots.get(last):
            a4 = behind(a3 - 1)
            if a4 is not None and t[a4][1] == ".":
                call = True
        if not call:
            return False
        if ctx(pi, ni):
            return False
        if ni is None:
            return not whole
        v2 = t[ni][1]
        return v2 in (",", ")", "}", "]")

    drop = set()
    for open, close in match.items():
        pi = behind(open - 1)
        ni = ahead(close + 1)
        if prior(pi) and after(ni) and (ctx(pi, ni) or not truncates(open, close, pi, ni)):
            drop.add(open)
            drop.add(close)
    if not drop:
        return text
    return "".join(v for i, (k, v) in enumerate(t) if i not in drop)


def step(header):
    t = toks(header)
    commas = []
    depth = 0
    for i, (k, v) in enumerate(t):
        if k == "p" and v in "([{":
            depth += 1
        elif k == "p" and v in ")]}":
            depth -= 1
        elif k == "p" and v == "," and depth == 0:
            commas.append(i)
    if len(commas) != 2:
        return header
    tail = "".join(x[1] for x in t[commas[1] + 1:]).strip()
    if tail != "1":
        return header
    head = "".join(x[1] for x in t[:commas[1]])
    return head


def finish(lines):
    for node in lines:
        if node["k"] == "ln":
            text = node.get("new", node["s"])
            whole = bool(split(text)) or text.startswith("local ")
            node["new"] = deparen(text, whole and not text.startswith("return"))
        elif node["k"] == "if":
            node["c"] = deparen(node["c"], False)
            finish(node["b"])
            for pair in node["cl"]:
                pair[0] = deparen(pair[0], False)
                finish(pair[1])
            if node["e"]:
                finish(node["e"])
        elif node["k"] == "while":
            node["c"] = deparen(node["c"], False)
            finish(node["b"])
        elif node["k"] == "repeat":
            finish(node["b"])
            node["u"] = deparen(node["u"], False)
        elif node["k"] == "for":
            node["h"] = step(deparen(node["h"], False))
            finish(node["b"])
        elif node["k"] in ("func", "do"):
            finish(node["b"])
    return lines


def parse(lines):
    pos = [0]

    def blk(stops):
        out = []
        while pos[0] < len(lines):
            text = lines[pos[0]].strip()
            first = text.split(" ")[0] if text else ""
            if text == "":
                pos[0] += 1
                continue
            if text in stops or first in stops:
                return out
            if text.endswith(" then") and text.startswith("if "):
                node = {"k": "if", "c": text[3:-5].strip(), "b": [], "cl": [], "e": None}
                pos[0] += 1
                node["b"] = blk({"else", "elseif", "end"})
                while pos[0] < len(lines) and lines[pos[0]].strip().startswith("elseif "):
                    cond = lines[pos[0]].strip()[7:-5].strip()
                    pos[0] += 1
                    node["cl"].append([cond, blk({"else", "elseif", "end"})])
                if pos[0] < len(lines) and lines[pos[0]].strip() == "else":
                    pos[0] += 1
                    node["e"] = blk({"end"})
                if pos[0] < len(lines):
                    pos[0] += 1
                out.append(node)
            elif text.startswith("while ") and text.endswith(" do"):
                node = {"k": "while", "c": text[6:-3].strip(), "b": []}
                pos[0] += 1
                node["b"] = blk({"end"})
                if pos[0] < len(lines):
                    pos[0] += 1
                out.append(node)
            elif text.startswith("for ") and text.endswith(" do"):
                node = {"k": "for", "h": text[4:-3].strip(), "b": []}
                pos[0] += 1
                node["b"] = blk({"end"})
                if pos[0] < len(lines):
                    pos[0] += 1
                out.append(node)
            elif text == "repeat":
                pos[0] += 1
                node = {"k": "repeat", "b": [], "u": "true"}
                node["b"] = blk({"until"})
                if pos[0] < len(lines):
                    node["u"] = lines[pos[0]].strip()[5:].strip()
                    pos[0] += 1
                out.append(node)
            elif text.startswith("local function ") or text.startswith("function ") or \
                    (text.endswith(")") and "function(" in text.replace(" ", "")):
                node = {"k": "func", "h": text, "b": []}
                pos[0] += 1
                node["b"] = blk({"end"})
                if pos[0] < len(lines):
                    pos[0] += 1
                out.append(node)
            elif text == "do":
                pos[0] += 1
                node = {"k": "do", "b": []}
                node["b"] = blk({"end"})
                if pos[0] < len(lines):
                    pos[0] += 1
                out.append(node)
            else:
                out.append({"k": "ln", "s": text})
                pos[0] += 1
        return out
    return blk(set())


def render(lines, depth, out):
    pad = "  " * depth
    for node in lines:
        if node["k"] == "ln":
            out.append(pad + node.get("new", node["s"]))
        elif node["k"] == "if":
            out.append(pad + "if " + join(toks(node["c"])) + " then")
            render(node["b"], depth + 1, out)
            for cond, body in node["cl"]:
                out.append(pad + "elseif " + cond + " then")
                render(body, depth + 1, out)
            if node["e"]:
                out.append(pad + "else")
                render(node["e"], depth + 1, out)
            out.append(pad + "end")
        elif node["k"] == "while":
            out.append(pad + "while " + join(toks(node["c"])) + " do")
            render(node["b"], depth + 1, out)
            out.append(pad + "end")
        elif node["k"] == "for":
            out.append(pad + "for " + join(toks(node["h"])) + " do")
            render(node["b"], depth + 1, out)
            out.append(pad + "end")
        elif node["k"] == "repeat":
            out.append(pad + "repeat")
            render(node["b"], depth + 1, out)
            out.append(pad + "until " + node["u"])
        elif node["k"] == "do":
            out.append(pad + "do")
            render(node["b"], depth + 1, out)
            out.append(pad + "end")
        elif node["k"] == "func":
            out.append(pad + node["h"])
            render(node["b"], depth + 1, out)
            out.append(pad + "end")
            if depth == 0:
                out.append("")


def now(node):
    return node.get("new", node["s"])


def count(text, name):
    out = 0
    prev = ""
    for k, v in toks(text):
        if k == "w" and v == name and prev not in (".", ":"):
            out += 1
        prev = v if k == "p" else ""
    return out


def put(text, name, value):
    out = []
    prev = ""
    for k, v in toks(text):
        if k == "w" and v == name and prev not in (".", ":"):
            out.extend(toks(value))
            prev = ")"
            continue
        out.append((k, v))
        prev = v if k == "p" else ""
    return join(out)


def deep(lines, name):
    text = []
    render(lines, 0, text)
    return sum(count(one, name) for one in text)


def heads(node, name):
    out = 0
    spot = None
    for key in ("c", "h", "u"):
        if node.get(key):
            got = count(node[key], name)
            if got:
                out += got
                spot = key
    return out, spot


def seek(lines, i, name):
    hits = 0
    spot = None
    for j in range(i + 1, len(lines)):
        node = lines[j]
        if node["k"] == "ln":
            text = now(node)
            got = count(text, name)
            lead = split(text)
            if lead is not None and lead[0].strip() == name:
                if got == 1 and hits == 0:
                    return ("self", j, None)
                return None
            if got:
                hits += got
                if hits > 1:
                    return None
                spot = ("ln", j, None)
            continue
        got, key = heads(node, name)
        if got:
            hits += got
            if hits > 1:
                return None
            spot = ("node", j, key)
        if deep(node.get("b") or [], name):
            return None
        if node.get("e") and deep(node["e"], name):
            return None
        for pair in node.get("cl", []):
            if deep(pair[1], name):
                return None
    if hits != 1:
        return None
    return spot


def inline(lines):
    for node in lines:
        if node["k"] == "ln":
            continue
        body = node.get("b")
        if body is not None:
            inline(body)
        for pair in node.get("cl", []):
            inline(pair[1])
        if node.get("e"):
            inline(node["e"])
    moved = True
    while moved:
        moved = False
        i = len(lines) - 1
        while i >= 0:
            node = lines[i]
            if node["k"] != "ln":
                i -= 1
                continue
            got = split(now(node))
            if got is None:
                i -= 1
                continue
            lhs = got[0].strip()
            rhs = got[1].strip()
            if not lhs.isidentifier() or rhs == "":
                i -= 1
                continue
            spot = seek(lines, i, lhs)
            if spot is None:
                i -= 1
                continue
            kind, j, key = spot
            if kind == "self":
                other = split(now(lines[j]))
                lines[j]["new"] = lhs + " = " + put(other[1], lhs, rhs)
            elif kind == "ln":
                lines[j]["new"] = put(now(lines[j]), lhs, rhs)
            else:
                lines[j][key] = put(lines[j][key], lhs, rhs)
            del lines[i]
            moved = True
            i -= 1
    return lines


def read(lines):
    out = set()
    for node in lines:
        if node["k"] == "ln":
            got = split(now(node))
            text = got[1] if got else now(node)
            for name in refs(text):
                out.add(name)
            for key in ("h", "c", "u"):
                if node.get(key):
                    for name in refs(node[key]):
                        out.add(name)
        else:
            for key in ("h", "c", "u"):
                if node.get(key):
                    for name in refs(node[key]):
                        out.add(name)
            out |= read(node["b"])
            for pair in node.get("cl", []):
                for name in refs(pair[0]):
                    out.add(name)
                out |= read(pair[1])
            if node.get("e"):
                out |= read(node["e"])
    return out


def flush(lines):
    live = read(lines)
    i = 0
    while i < len(lines):
        node = lines[i]
        if node["k"] == "ln":
            got = split(now(node))
            if got and got[0].strip().isidentifier() and got[0].strip() not in live \
                    and atom(got[1].strip()) or (got and got[0].strip().isidentifier()
                                                   and got[0].strip() not in live
                                                   and pure(got[1].strip())):
                del lines[i]
                continue
        i += 1
    for node in lines:
        if node["k"] == "ln":
            continue
        body = node.get("b")
        if body is not None:
            flush(body)
        for pair in node.get("cl", []):
            flush(pair[1])
        if node.get("e"):
            flush(node["e"])
    return lines


def dead(lines, i, name):
    for j in range(i + 1, len(lines)):
        node = lines[j]
        if node["k"] == "ln":
            text = now(node)
            got = split(text)
            if got is not None and got[0].strip() == name:
                return bool(name in refs(got[1]))
            if count(text, name):
                return False
        elif node["k"] == "func" and title(node["h"]) == name:
            return True
        elif node["k"] == "for" and toks(node["h"]) and toks(node["h"])[0][1] == name:
            return True
        else:
            if node.get("b") and deep(node["b"], name):
                return False
            if node.get("e") and deep(node["e"], name):
                return False
            for pair in node.get("cl", []):
                if deep(pair[1], name):
                    return False
            for key in ("c", "h", "u"):
                if node.get(key) and count(node[key], name):
                    return False
    return True


def dust(lines):
    for node in lines:
        if node["k"] == "ln":
            continue
        body = node.get("b")
        if body is not None:
            dust(body)
        for pair in node.get("cl", []):
            dust(pair[1])
        if node.get("e"):
            dust(node["e"])
    i = len(lines) - 1
    while i >= 0:
        node = lines[i]
        if node["k"] == "ln":
            got = split(now(node))
            if got and got[0].strip().isidentifier():
                name = got[0].strip()
                rhs = got[1].strip()
                if name not in refs(rhs) and (atom(rhs) or pure(rhs)) \
                        and dead(lines, i, name):
                    del lines[i]
        i -= 1
    return lines


def grind(lines):
    for i in range(8):
        before = []
        render(lines, 0, before)
        inline(lines)
        dust(lines)
        after = []
        render(lines, 0, after)
        if before == after:
            break
    return lines


def work(lines):
    keep = []
    for text in lines:
        stripped = text.strip()
        if stripped.startswith("local ") and split(stripped[6:]) is None:
            continue
        keep.append(text)
    tree = parse(keep)
    tree = merge(tree)
    grind(tree)
    found = tabs(tree)
    if found:
        tree = untab(tree, found)
    grind(tree)
    tree = chain(tree)
    grind(tree)
    tree = elide(tree)
    grind(tree)
    scope(tree)
    versionize(tree)
    tree = rename(tree)
    tree = finish(tree)
    flat = []
    render(tree, 0, flat)
    while flat and flat[-1] == "":
        flat.pop()
    return "\n".join(flat)


def main(argv):
    if len(argv) < 2:
        print("usage: work.py <in.lua> <out.txt>")
        return 2
    try:
        with open(argv[0], "r", encoding="latin-1") as f:
            text = f.read()
    except OSError:
        print("input not found: " + argv[0])
        return 2
    body = work(text.split("\n"))
    out = body + "\n"
    with open(argv[1], "w", encoding="latin-1") as f:
        f.write(banner + "\n\n" + out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
