# -*- coding: utf-8 -*-
"""W1 / Phase 0：实测本机显存上限（找真实边界，而不是"不 OOM 就算过"）。

为什么不能只看 OOM：
    第一版探测发现 512px / batch 192 的 `max_memory_allocated()` 达到 10835 MiB，
    而这块 GPU 的物理显存只有 8187 MiB —— 也就是说 Windows 驱动允许显存**静默溢出**
    到主机内存（shared GPU memory）。这种情况下不会抛 OOM，但时延会被拖垮。
    因此判据必须是两条：
        安全上限 = 峰值 <= 80% 物理显存
        溢出警戒 = 峰值 > 100% 物理显存（已在用主机内存）
    只有落在安全区内的 batch 才能用于后续 latency / 内存结论。

方法：wide_resnet50_2(weights=None)（与 PatchCore 骨干同架构，不需下载权重），
      每个配置前清缓存并重置峰值统计；跑两轮核对可复现性。
      这是**冻结骨干单次前向**的峰值，不含编码器常驻之外的库内存与特征缓存。
"""
import json
import time

import torch
import torchvision

RESOLUTIONS = (256, 384, 512)
BATCHES = (256, 192, 160, 128, 112, 96, 80, 64, 48, 32, 16)
SAFE_FRACTION = 0.80
OUT = r"F:\research\logs\w1_vram_limit.json"


def try_batch(backbone, res, bs):
    """返回 (peak_MiB 或 None, 状态)。状态: ok / oom。"""
    x = None
    try:
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        x = torch.randn(bs, 3, res, res, device="cuda")
        with torch.no_grad():
            _ = backbone(x)
        torch.cuda.synchronize()
        peak = torch.cuda.max_memory_allocated() / 2 ** 20
        del x
        torch.cuda.empty_cache()
        return peak, "ok"
    except RuntimeError as e:
        if x is not None:
            try:
                del x
            except Exception:
                pass
        torch.cuda.empty_cache()
        if "out of memory" in str(e).lower():
            return None, "oom"
        raise


def sweep(backbone, res, total_mib):
    """从大 batch 往小试：OOM 就继续往下，一旦落到安全区就停（更小的没有信息量）。"""
    rows = []
    safe = None
    for bs in BATCHES:
        t0 = time.perf_counter()
        peak, status = try_batch(backbone, res, bs)
        dt = time.perf_counter() - t0
        rows.append((bs, peak, status, dt))
        if status == "ok" and peak <= SAFE_FRACTION * total_mib:
            safe = bs
            break
    ok_rows = [(bs, peak) for bs, peak, st, _ in rows if st == "ok"]
    oom_rows = [bs for bs, _, st, _ in rows if st == "oom"]
    return {
        "rows": rows,
        "safe_batch": safe,
        "spill_batch": max([bs for bs, peak in ok_rows if peak > total_mib], default=None),
        "largest_ok_batch": max([bs for bs, _ in ok_rows], default=None),
        "first_oom_batch": max(oom_rows, default=None),
    }


def main():
    print("=" * 78)
    print("本机显存上限实测（冻结 wide_resnet50_2，单次前向）")
    print("=" * 78)
    props = torch.cuda.get_device_properties(0)
    free_b, total_b = torch.cuda.mem_get_info()
    total_mib = props.total_memory / 2 ** 20
    print("device        : %s  sm_%d%d" % (props.name, *torch.cuda.get_device_capability(0)))
    print("物理显存      : %.1f MiB" % total_mib)
    print("探测开始时空闲: %.1f MiB" % (free_b / 2 ** 20))
    print("torch         : %s (cuda %s)" % (torch.__version__, torch.version.cuda))
    print("判据          : 安全上限 = 峰值 <= %.0f%% 物理显存；峰值 > 100%% 记为已溢出到主机内存"
          % (SAFE_FRACTION * 100))
    print("-" * 78)

    backbone = torchvision.models.wide_resnet50_2(weights=None).eval().cuda()
    resident = torch.cuda.memory_allocated() / 2 ** 20
    print("骨干权重常驻显存: %.1f MiB" % resident)
    print("-" * 78)

    results = {}
    for res in RESOLUTIONS:
        print("\n[%dpx]" % res)
        r = sweep(backbone, res, total_mib)
        for bs, peak, status, dt in r["rows"]:
            if status == "ok":
                flag = ""
                if peak > total_mib:
                    flag = "  <== 已溢出到主机内存（不可用于时延结论）"
                elif peak > SAFE_FRACTION * total_mib:
                    flag = "  <== 超出安全区"
                print("   batch %-5d 峰值 %8.1f MiB (%5.1f%%)  %.1fs%s"
                      % (bs, peak, 100.0 * peak / total_mib, dt, flag))
            else:
                print("   batch %-5d OOM" % bs)
                break
        print("   -> 物理显存内安全上限 batch = %s ；首次 OOM = %s ；最大侥幸成功 = %s"
              % (r["safe_batch"], r["first_oom_batch"], r["largest_ok_batch"]))
        if r["spill_batch"]:
            print("   -> 注意：batch %d 起峰值已超过物理显存，说明驱动在偷偷用主机内存。"
                  % r["spill_batch"])
        results[str(res)] = {
            "safe_batch": r["safe_batch"], "first_oom_batch": r["first_oom_batch"],
            "largest_ok_batch": r["largest_ok_batch"], "spill_from_batch": r["spill_batch"],
            "rows": [{"batch": bs, "peak_MiB": peak, "status": st}
                     for bs, peak, st, _ in r["rows"]],
        }

    print("\n" + "=" * 78)
    print("第二轮（可复现性核对，只比安全上限）")
    repro = True
    for res in RESOLUTIONS:
        r = sweep(backbone, res, total_mib)
        same = (r["safe_batch"] == results[str(res)]["safe_batch"])
        repro = repro and same
        print("  %3dpx -> 安全上限 batch = %-5s  %s"
              % (res, r["safe_batch"], "一致" if same else "不一致！"))
    print("可复现性: %s" % ("一致" if repro else "不一致"))

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"device": props.name, "total_MiB": total_mib,
                   "free_MiB_at_start": free_b / 2 ** 20,
                   "backbone_resident_MiB": resident,
                   "safe_fraction": SAFE_FRACTION,
                   "results": results, "reproducible": repro},
                  f, ensure_ascii=False, indent=2)
    print("已写入: %s" % OUT)


if __name__ == "__main__":
    main()
