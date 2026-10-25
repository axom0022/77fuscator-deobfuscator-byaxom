import os
import sys
import struct

b36 = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
magic = "77FUS|"
digits = "0123456789ABCDEF"


def slurp(path):
    try:
        with open(path, "rb") as f:
            return f.read()
    except OSError:
        return None


def digit(c):
    i = b36.find(c)
    if i < 0:
        return None
    return i


def tokenize(payload):
    codes = []
    i = 0
    n = len(payload)
    while i < n:
        length = digit(payload[i])
        if length is None or length == 0:
            return None
        i += 1
        if i + length > n:
            return None
        value = 0
        for j in range(length):
            d = digit(payload[i + j])
            if d is None:
                return None
            value = value * 36 + d
        i += length
        codes.append(value)
    return codes


def lzw(payload, seed):
    codes = tokenize(payload)
    if not codes:
        return None
    table = {}
    for i in range(seed):
        table[i] = bytes([i % 256])
    top = seed
    if codes[0] not in table:
        return None
    out = bytearray(table[codes[0]])
    word = table[codes[0]]
    for code in codes[1:]:
        if code in table:
            entry = table[code]
        elif code == top:
            entry = word + word[:1]
        else:
            return None
        out.extend(entry)
        table[top] = word + entry[:1]
        top += 1
        word = entry
    return bytes(out)


def sniff(text):
    if len(text) == 0 or len(text) % 2 != 0:
        return False
    for c in text:
        if c not in digits:
            return False
    return True


def raw(text):
    return bytes.fromhex(text)


def seek(text):
    pos = 0
    while True:
        at = text.find(magic, pos)
        if at < 0:
            return None
        start = at + len(magic)
        end = start
        while end < len(text) and (text[end] in b36):
            end += 1
        if end > start:
            return text[start:end]
        pos = start


def peel(data):
    text = data.decode("latin-1")
    payload = seek(text)
    if payload:
        if sniff(payload):
            return raw(payload), "hex blob"
        for seed in (256, 208):
            inner = lzw(payload, seed)
            if inner:
                text2 = inner.decode("latin-1")
                inner2 = seek(text2)
                if inner2 and sniff(inner2):
                    return raw(inner2), "lzw wrapper -> hex blob"
        return None, "compressed payload but no inner blob"
    best = None
    start = 0
    while True:
        at = text.find("'", start)
        if at < 0:
            break
        end = text.find("'", at + 1)
        if end < 0:
            break
        chunk = text[at + 1:end]
        ok = len(chunk) >= 1000
        if ok:
            for c in chunk:
                if c not in b36:
                    ok = False
                    break
        if ok and (best is None or len(chunk) > len(best)):
            best = chunk
        start = end + 1
    if best:
        for seed in (256, 208):
            got = lzw(best, seed)
            if got:
                return got, "lzw raw blob"
    return None, "no 77fuscator payload found"


def perms(items):
    if len(items) <= 1:
        return [list(items)]
    out = []
    for i in range(len(items)):
        rest = items[:i] + items[i + 1:]
        for tail in perms(rest):
            out.append([items[i]] + tail)
    return out


def xored(data, key):
    if key == 0:
        return data
    out = bytearray(data)
    for i in range(len(out)):
        out[i] ^= key
    return bytes(out)


class halt(Exception):
    pass


def reader(data, key):
    return {"d": data, "p": 0, "n": len(data), "key": key}


def rem(r):
    return r["n"] - r["p"]


def u8(r):
    if r["p"] >= r["n"]:
        raise halt("eof")
    v = r["d"][r["p"]]
    r["p"] += 1
    return v


def u16(r):
    if r["p"] + 2 > r["n"]:
        raise halt("eof")
    v = r["d"][r["p"]] | (r["d"][r["p"] + 1] << 8)
    r["p"] += 2
    return v


def i16(r):
    v = u16(r)
    if v >= 32768:
        v -= 65536
    return v


def i32(r):
    if r["p"] + 4 > r["n"]:
        raise halt("eof")
    v = struct.unpack_from("<i", r["d"], r["p"])[0]
    r["p"] += 4
    return v


def u24(r):
    if r["p"] + 3 > r["n"]:
        raise halt("eof")
    v = r["d"][r["p"]] | (r["d"][r["p"] + 1] << 8) | (r["d"][r["p"] + 2] << 16)
    r["p"] += 3
    return v


def f64(r):
    if r["p"] + 8 > r["n"]:
        raise halt("eof")
    v = struct.unpack_from("<d", r["d"], r["p"])[0]
    r["p"] += 8
    return v


def uleb(r):
    result = 0
    shift = 0
    for _ in range(10):
        b = u8(r)
        result |= (b & 127) << shift
        if b < 128:
            return result
        shift += 7
    raise halt("uleb")


def chunk(r, order, tags, depth):
    if depth > 32:
        raise halt("deep")
    proto = {"params": 0, "consts": [], "insts": [], "children": []}
    for section in order:
        if section == "P":
            v = u16(r) ^ r["key"]
            if v > 1024:
                raise halt("params")
            proto["params"] = v
        elif section == "C":
            count = i32(r)
            if count < 0 or count > rem(r):
                raise halt("ccount")
            for _ in range(count):
                tag = u8(r)
                if tag > 3:
                    raise halt("ctag")
                kind = tags[tag]
                item = {"kind": kind}
                if kind == 1:
                    item["value"] = u8(r) != 0
                elif kind == 2:
                    item["value"] = f64(r)
                elif kind == 3:
                    flag = u8(r)
                    if flag == 1:
                        item["tampered"] = True
                    else:
                        if flag != 0:
                            raise halt("mark")
                        length = i32(r)
                        if length < 0 or length > rem(r):
                            raise halt("slen")
                        item["value"] = r["d"][r["p"]:r["p"] + length]
                        r["p"] += length
                proto["consts"].append(item)
        elif section == "I":
            count = uleb(r)
            if count > rem(r):
                raise halt("icount")
            for i in range(count):
                d = u8(r)
                inst = {"pc": i}
                if d & 1:
                    inst["data"] = True
                else:
                    kind = (d >> 1) & 7
                    if kind > 3:
                        raise halt("itype")
                    inst["kind"] = kind
                    inst["op"] = uleb(r)
                    if inst["op"] > 4096:
                        raise halt("op")
                    inst["a"] = i16(r)
                    if kind == 0:
                        inst["b"] = u24(r)
                        inst["c"] = u24(r)
                        inst["e"] = i16(r)
                        inst["f"] = i32(r)
                    elif kind == 1:
                        inst["b"] = i32(r)
                    elif kind == 2:
                        inst["b"] = i32(r) - 65536
                    else:
                        inst["b"] = i32(r) - 65536
                        inst["c"] = u24(r)
                        inst["e"] = i16(r)
                        inst["f"] = i32(r)
                proto["insts"].append(inst)
        else:
            count = uleb(r)
            if count > rem(r):
                raise halt("fcount")
            for _ in range(count):
                proto["children"].append(chunk(r, order, tags, depth + 1))
    return proto


def score(proto):
    total = 0
    for inst in proto["insts"]:
        if not inst.get("data"):
            total += 4
    for item in proto["consts"]:
        if item["kind"] == 3 and item.get("value") is not None:
            text = item["value"]
            shown = True
            for b in text:
                if b < 32 or b > 126:
                    shown = False
                    break
            if shown:
                total += 20 + len(text)
        elif item["kind"] == 2:
            total += 2
    if proto["params"] > 32:
        total -= 50
    for child in proto["children"]:
        total += score(child)
    return total


def deserialize(blob):
    orders = perms(["P", "C", "I", "F"])
    maps = perms([0, 1, 2, 3])
    best = None
    top = -1
    for key in range(256):
        data = xored(blob, key)
        for order in orders:
            for mapping in maps:
                tags = [0, 0, 0, 0]
                for kind in range(4):
                    tags[mapping[kind]] = kind
                r = reader(data, key)
                try:
                    proto = chunk(r, order, tags, 0)
                except halt:
                    continue
                if r["p"] != r["n"]:
                    continue
                s = score(proto)
                if s > top:
                    top = s
                    best = {"key": key, "order": order, "mapping": mapping, "proto": proto}
    return best


def census(proto, acc, depth):
    acc["protos"] += 1
    acc["consts"] += len(proto["consts"])
    for inst in proto["insts"]:
        if inst.get("data"):
            acc["data"] += 1
        else:
            acc["insts"] += 1
            acc["ops"][inst["op"]] = acc["ops"].get(inst["op"], 0) + 1
    if depth > acc["depth"]:
        acc["depth"] = depth
    for child in proto["children"]:
        census(child, acc, depth + 1)
    return acc


def now(value):
    return value.decode("latin-1")


def dump(proto, out, depth):
    pad = "  " * depth
    out.append(pad + "proto params=%d consts=%d children=%d" % (
        proto["params"], len(proto["consts"]), len(proto["children"])))
    for i, item in enumerate(proto["consts"]):
        if item.get("tampered"):
            out.append(pad + "  k%d tampered" % i)
        elif item["kind"] == 3 and item.get("value") is not None:
            out.append(pad + "  k%d %r" % (i, now(item["value"])))
        elif item["kind"] == 1:
            out.append(pad + "  k%d %s" % (i, "true" if item["value"] else "false"))
        elif item["kind"] == 2:
            out.append(pad + "  k%d %s" % (i, repr(item["value"])))
        else:
            out.append(pad + "  k%d nil" % i)
    for inst in proto["insts"]:
        if inst.get("data"):
            out.append(pad + "  [%d] data" % inst["pc"])
        else:
            out.append(pad + "  [%d] op=%d kind=%d a=%s b=%s c=%s" % (
                inst["pc"], inst["op"], inst["kind"],
                inst.get("a"), inst.get("b"), inst.get("c")))
    for i, child in enumerate(proto["children"]):
        out.append(pad + "  child %d" % i)
        dump(child, out, depth + 1)


def main(argv):
    if not argv:
        print("usage: unpack.py <sample> [--out DIR] [--ops]")
        return 2
    path = argv[0]
    data = slurp(path)
    if data is None:
        print("input not found: " + path)
        return 2
    blob, how = peel(data)
    if blob is None:
        print("peel failed: " + how)
        return 1
    print("peel: %s, %d bytes" % (how, len(blob)))
    best = deserialize(blob)
    if best is None:
        print("no consistent parse")
        return 1
    print("key=%d order=%s mapping=%s" % (
        best["key"], ",".join(best["order"]), ",".join(str(m) for m in best["mapping"])))
    proto = best["proto"]
    live = sum(1 for i in proto["insts"] if not i.get("data"))
    print("root: params=%d consts=%d insts=%d children=%d" % (
        proto["params"], len(proto["consts"]), live, len(proto["children"])))
    acc = census(proto, {"protos": 0, "insts": 0, "consts": 0, "data": 0, "depth": 0, "ops": {}}, 0)
    print("total: protos=%d insts=%d consts=%d" % (acc["protos"], acc["insts"], acc["consts"]))
    shown = []
    for item in proto["consts"]:
        if item["kind"] == 3 and item.get("value") is not None and len(shown) < 8:
            shown.append(now(item["value"]))
    print("first strings: " + " | ".join(shown))
    outdir = None
    if "--out" in argv:
        outdir = argv[argv.index("--out") + 1]
    if outdir:
        out = []
        dump(proto, out, 0)
        if not os.path.isdir(outdir):
            os.makedirs(outdir)
        with open(outdir + "/chunk.lua", "wb") as f:
            f.write(("\n".join(out) + "\n").encode("latin-1"))
        print("wrote " + outdir + "/chunk.lua")
    if "--ops" in argv:
        ids = sorted(acc["ops"])
        print("distinct opcodes: %d (data slots %d, depth %d)" % (len(ids), acc["data"], acc["depth"]))
        row = []
        for i in ids:
            row.append("%d=%d" % (i, acc["ops"][i]))
            if len(row) == 12:
                print("  " + " ".join(row))
                row = []
        if row:
            print("  " + " ".join(row))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
