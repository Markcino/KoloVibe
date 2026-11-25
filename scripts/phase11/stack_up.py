"""Keep the Phase 11 stack running for exploration; writes the ports to stack.json. Stop with Ctrl-C or SIGTERM."""
import json
import signal
import sys
import time

import os
from lib import stack

with stack(broker=not os.environ.get('P11_NO_BROKER')) as s:
    out = {"ports": s.ports, "base": str(s.base), "environments": s.environments, "video_ids": [str(v) for v in s.video_ids], "creator_id": str(s.creator_id)}
    open(sys.argv[1], "w").write(json.dumps(out))
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
