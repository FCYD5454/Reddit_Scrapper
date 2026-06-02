# extract_from_wrapped_patch.py
# Usage: python extract_from_wrapped_patch.py provider-adapters-gemini-deepseek.patch
import sys
import os

if len(sys.argv) < 2:
    print("Usage: python extract_from_wrapped_patch.py <patchfile>")
    sys.exit(1)

patchfile = sys.argv[1]
with open(patchfile, 'r', encoding='utf-8', errors='replace') as f:
    lines = f.readlines()

i = 0
total = len(lines)
while i < total:
    line = lines[i]
    if line.startswith('*** Add File:'):
        path = line[len('*** Add File:'):].strip()
        # skip potential following lines until we hit + content or End Patch
        i += 1
        content = []
        while i < total:
            l = lines[i]
            # stop when next block marker appears
            if l.startswith('*** Add File:') or l.startswith('*** End Patch') or l.startswith('*** Begin Patch'):
                break
            # lines that are part of file content typically start with '+'
            if l.startswith('+'):
                content.append(l[1:])  # drop leading '+'
            # ignore other lines (e.g., context lines in wrapper)
            i += 1
        # ensure directory exists
        dirname = os.path.dirname(path)
        if dirname:
            os.makedirs(dirname, exist_ok=True)
        # write file (overwrite if exists) with utf-8
        with open(path, 'w', encoding='utf-8') as out:
            out.writelines(content)
        print(f"WROTE: {path} ({len(content)} lines)")
    else:
        i += 1

print("Done.")