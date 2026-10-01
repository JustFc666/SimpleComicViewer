import os, sys
target = sys.argv[1]
budget = 45
cnt = 0
for root, dirs, files in os.walk(target, topdown=False):
    for f in files:
        p = os.path.join(root, f)
        try:
            os.remove(p)
            cnt += 1
        except Exception:
            pass
        if cnt >= budget:
            print('partial', cnt)
            sys.exit(0)
    for d in dirs:
        dp = os.path.join(root, d)
        try:
            os.rmdir(dp)
        except Exception:
            pass
print('done', cnt)
