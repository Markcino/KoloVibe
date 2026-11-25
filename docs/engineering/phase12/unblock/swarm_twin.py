import sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
pc = d["services"]["points-consumer"]
out = {"version": "3.8", "services": {}, "networks": d["networks"], "secrets": d["secrets"]}
# Same image, user, read-only fs, caps, secrets, deploy block as points-consumer; only the process differs.
hog = dict(pc); hog["entrypoint"] = ["python", "-c", "import time; time.sleep(5); b=bytearray(400*1024*1024); time.sleep(600)"]; hog.pop("command", None)
idle = dict(pc); idle["entrypoint"] = ["python", "-c", "import time, signal, sys; signal.signal(signal.SIGTERM, lambda *a: sys.exit(0)); time.sleep(10**6)"]; idle.pop("command", None)
out["services"]["hog"] = hog; out["services"]["idle"] = idle
yaml.safe_dump(out, open(sys.argv[2], "w"), sort_keys=False)
