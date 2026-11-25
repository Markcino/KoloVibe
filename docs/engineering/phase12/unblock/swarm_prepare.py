import sys, yaml
src, dst = sys.argv[1], sys.argv[2]
d = yaml.safe_load(open(src))
for name, svc in d["services"].items():
    svc["image"] = "kolovibe/services:local"
    svc["deploy"]["replicas"] = 1
    svc["deploy"]["placement"] = {"constraints": ["node.role==manager"]}
yaml.safe_dump(d, open(dst, "w"), sort_keys=False)
print(" ".join(d["secrets"]))
print(" ".join(v["name"] for v in d["networks"].values()))
