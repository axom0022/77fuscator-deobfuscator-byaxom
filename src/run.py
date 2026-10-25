import os
import sys
import tempfile

import tidy
import unpack


def stem(path):
    name = os.path.basename(path)
    for tail in (".lua.txt", ".lua", ".txt"):
        if name.endswith(tail):
            return name[:-len(tail)]
    return name


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print("usage: deobfuscate <sample.lua> [out.txt]", file=sys.stderr)
        return 2
    sample = argv[0]
    if not os.path.isfile(sample):
        print("input not found: " + sample, file=sys.stderr)
        return 2
    if len(argv) > 1:
        out = argv[1]
    else:
        out = os.path.join(os.path.dirname(sample), stem(sample) + "_deobfedbyaxom.txt")
    work = tempfile.mkdtemp(prefix="deobf.")
    code = unpack.main([sample, "--out", work])
    if code:
        return code
    lifted = os.path.join(work, "lifted.lua")
    here = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isfile(os.path.join(here, "lift.py")):
        print("stage 2 (lift to lua source) is not implemented yet; chunk recovered in " + work,
              file=sys.stderr)
        return 4
    return tidy.main([lifted, out])


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
