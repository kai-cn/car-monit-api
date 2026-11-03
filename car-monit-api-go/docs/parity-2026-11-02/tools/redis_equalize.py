# -*- coding: utf-8 -*-
"""把双端 Redis 缓存状态拉平，让差异归因到代码而不是环境。

做的四件事（全部先备份到 raw/redis-backup-<时间戳>.json，可回滚）：
  1. 清掉历史探针会话留下的合成键（PARITY_UP_* / AUDIT-SYNTHETIC-*）
  2. 把 car_list_jc 里的合成车牌摘掉，并复制到 Go 的 db1（Java 只读不写这个键，
     分库后 Go 永远读不到 → carTrackQueryByTime 恒空）
  3. 把 sys_config:data_query 复制进 Java 的 db0（分库后 Java 读不到 → 走 JiAnDong
     受限分支，与 Go 的 queryall 分支不可比）
  4. 顺带同步 db1 已有而 db0 缺失的其余 sys_config:*（不改值，只补 Java 侧的缺）

值格式原样搬运，不做转换：Java 用 fastjson2（字符串带 JSON 引号、对象带 @type），
Go 的 encoding/json 会忽略未知字段，所以同一份值两端都能读。
"""
from __future__ import annotations

import datetime
import json
import os
import socket
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "raw")
HOST, PORT = "127.0.0.1", 6379

SYS_CONFIG_KEYS = ["sys_config:data_query"]
EXTRA_SYS_CONFIG = True          # 把 db1 其余 sys_config:* 也补进 db0
MARKERS = ("PARITY_UP", "AUDIT-SYNTHETIC")


class R:
    def __init__(self, db):
        self.s = socket.create_connection((HOST, PORT), 6)
        self.s.settimeout(20)
        self.send("SELECT", db)
        self.read()

    def send(self, *args):
        out = b"*%d\r\n" % len(args)
        for a in args:
            a = a if isinstance(a, bytes) else str(a).encode("utf-8")
            out += b"$%d\r\n%s\r\n" % (len(a), a)
        self.s.sendall(out)

    def read(self):
        line = self._rl()
        t, rest = line[:1], line[1:]
        if t == "+":
            return rest
        if t == "-":
            return {"ERR": rest}
        if t == ":":
            return int(rest)
        if t == "$":
            n = int(rest)
            if n == -1:
                return None
            data = self._readn(n + 2)[:-2]
            return data
        if t == "*":
            n = int(rest)
            if n == -1:
                return None
            return [self.read() for _ in range(n)]
        raise ValueError("bad reply " + repr(line))

    def _rl(self):
        buf = b""
        while not buf.endswith(b"\r\n"):
            b = self.s.recv(1)
            if not b:
                break
            buf += b
        return buf[:-2].decode("utf-8", "replace")

    def _readn(self, n):
        buf = b""
        while len(buf) < n:
            buf += self.s.recv(n - len(buf))
        return buf

    def cmd(self, *a):
        self.send(*a)
        return self.read()

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass


def main():
    os.makedirs(RAW, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = {"ts": ts, "note": "拉平双端 Redis 状态前的原值"}

    d0, d1 = R(0), R(1)

    # ── 1. 备份 + 收集合成键 ──
    for label, db, key in [("db0_car_list_jc", d0, "car_list_jc"),
                           ("db1_data_query", d1, "sys_config:data_query")]:
        backup[label] = db.cmd("GET", key)
    synth = {"db0": [], "db1": []}
    for label, db in (("db0", d0), ("db1", d1)):
        for pat in ("*PARITY_UP*", "*AUDIT-SYNTHETIC*"):
            keys = db.cmd("KEYS", pat) or []
            for k in keys:
                k = k.decode() if isinstance(k, bytes) else k
                t = db.cmd("TYPE", k)
                t = t if isinstance(t, str) else t.decode()
                val = db.cmd("GET", k) if t == "string" else None
                synth[label].append({"key": k, "type": t, "value": val})
    backup["synthetic"] = synth
    print(f"合成键：db0 {len(synth['db0'])} 个，db1 {len(synth['db1'])} 个")
    for label, db in (("db0", d0), ("db1", d1)):
        for e in synth[label]:
            print(f"  DEL {label} {e['key']}")
            db.cmd("DEL", e["key"])

    # ── 2. car_list_jc 摘掉合成车牌，并补进 db1 ──
    raw = d0.cmd("GET", "car_list_jc")
    if raw is None:
        print("db0 没有 car_list_jc，跳过")
    else:
        # 原样保留 fastjson2 的 @type（那是 Java 反序列化回 List<CarVO> 的依据），
        # 只从数组里摘掉合成项。解析失败就整段放弃，绝不写回一个 Java 读不懂的值。
        try:
            data = json.loads(raw.decode("utf-8"))
            assert isinstance(data, list)
        except Exception as e:
            print(f"!! car_list_jc 解析失败，不改动: {e}")
            data = None
        if data is not None:
            cleaned = [it for it in data
                       if not any(m in json.dumps(it, ensure_ascii=False) for m in MARKERS)]
            print(f"car_list_jc {len(data)} 项 → 摘掉合成 {len(data)-len(cleaned)} 项 → {len(cleaned)} 项")
            newtxt = json.dumps(cleaned, ensure_ascii=False, separators=(",", ":"))
            d0.cmd("SET", "car_list_jc", newtxt)          # Java 侧也去掉脏数据
            d1.cmd("SET", "car_list_jc", newtxt)          # Go 侧补上（否则恒空）
            backup["car_list_jc_after"] = newtxt[:2000]
            # db1 里 Go 自己写的值留档，便于回滚
            backup["db1_car_list_jc_before"] = d1.cmd("GET", "car_list_jc")

    # ── 3/4. sys_config 补齐到 db0 ──
    for k in SYS_CONFIG_KEYS:
        v = d1.cmd("GET", k)
        if v is None:
            print(f"db1 没有 {k}")
            continue
        d0.cmd("SET", k, v)
        print(f"SET db0 {k} = {v[:40] if isinstance(v,(bytes,str)) else v}")
        backup.setdefault("sys_config_copied", {})[k] = v
    if EXTRA_SYS_CONFIG:
        ks = d1.cmd("KEYS", "sys_config*") or []
        n = 0
        for kk in ks:
            kk = kk.decode() if isinstance(kk, bytes) else kk
            if d0.cmd("EXISTS", kk):
                continue
            v = d1.cmd("GET", kk)
            if v is None:
                continue
            d0.cmd("SET", kk, v)
            backup.setdefault("sys_config_extra", {})[kk] = v
            n += 1
        print(f"补入 db0 其余 sys_config 键 {n} 个")

    with open(os.path.join(RAW, f"redis-backup-{ts}.json"), "w", encoding="utf-8") as f:
        json.dump(backup, f, ensure_ascii=False, indent=1, default=str)
    print(f"\n备份 → raw/redis-backup-{ts}.json")
    print("回滚：读该文件，对每个键 SET 回原值 / DEL 新增键即可")

    d0.close(); d1.close()
    return ts


if __name__ == "__main__":
    main()
