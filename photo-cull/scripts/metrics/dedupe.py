"""连拍分组。

用感知哈希加拍摄时间双重条件。只用哈希会把同一场景的不同构图错误合并，
只用时间会把连续但内容不同的片子归到一起。两个条件都满足才算一组。

哈希用dHash而不是aHash。dHash比较的是相邻像素的大小关系，对整体明暗
变化免疫，而连拍中曝光波动很常见。
"""

import cv2


def dhash(bgr, size=8):
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    small = cv2.resize(gray, (size + 1, size), interpolation=cv2.INTER_AREA)
    diff = small[:, 1:] > small[:, :-1]
    bits = 0
    for b in diff.ravel():
        bits = (bits << 1) | int(b)
    return bits


def hamming(a, b):
    return bin(a ^ b).count("1")


def group(records, max_distance=10, max_gap_sec=3.0, require_time=False):
    """按连拍关系分组。

    records需含hash与timestamp。返回每条记录的组号，独立成片的自成一组。

    时间条件在缺少EXIF时自动放宽，否则JPEG导出件、截图这类没有时间戳的
    文件会全部退化成独立片，失去去重意义。
    """
    n = len(records)
    parent = list(range(n))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    def union(i, j):
        ri, rj = find(i), find(j)
        if ri != rj:
            parent[max(ri, rj)] = min(ri, rj)

    order = sorted(
        range(n),
        key=lambda i: (records[i].get("timestamp") or 0, records[i].get("name", "")),
    )
    # 只与邻近若干张比较。连拍必然在时间上相邻，全量两两比较是O(n^2)，
    # 两千张就是两百万次，没有必要
    window = 12
    for a in range(n):
        for b in range(a + 1, min(a + 1 + window, n)):
            i, j = order[a], order[b]
            hi, hj = records[i].get("hash"), records[j].get("hash")
            if hi is None or hj is None:
                continue
            if hamming(hi, hj) > max_distance:
                continue
            ti, tj = records[i].get("timestamp"), records[j].get("timestamp")
            if ti is not None and tj is not None:
                if abs(ti - tj) > max_gap_sec:
                    continue
            elif require_time:
                continue
            union(i, j)

    roots = {}
    groups = []
    for i in range(n):
        r = find(i)
        if r not in roots:
            roots[r] = len(roots)
        groups.append(roots[r])
    return groups


def summarize(groups):
    counts = {}
    for g in groups:
        counts[g] = counts.get(g, 0) + 1
    bursts = {g: c for g, c in counts.items() if c > 1}
    return {
        "group_count": len(counts),
        "burst_groups": len(bursts),
        "images_in_bursts": int(sum(bursts.values())),
    }
