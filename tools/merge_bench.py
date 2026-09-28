"""
Składa kawałki `benchmark.py --shard K/N` w jeden plik wyniku (#167).

    python3 benchmark.py --candidate <spec> --record <spec> --issue N --shard 1/4 --out bench/N-x-shard1.json
    ...
    python3 benchmark.py --candidate <spec> --record <spec> --issue N --shard 4/4 --out bench/N-x-shard4.json
    python3 tools/merge_bench.py --out bench/N-x.json bench/N-x-shard1.json bench/N-x-shard2.json bench/N-x-shard3.json bench/N-x-shard4.json

Wynik ma dokładnie ten kształt co przebieg `benchmark.py` bez `--shard` na tej
samej puli seedów: te same `arms` i `deltas` (agregaty są niezależne od
kolejności seedów), `duration_s` = suma kawałków.

Odmawia (kod wyjścia != 0), gdy kawałki nie dają się bezpiecznie złożyć: różny
`sha`, `issue`, `config`, specyfikacja ramienia (nazwa polityki albo
`weights_hash`), brakujący albo zdublowany kawałek `K/N`.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from benchmark import STATUS_OK, aggregate_set, paired_delta, parse_shard, strip_scores


class MergeError(Exception):
    """Kawałki nie dają się złożyć (#167: niezerowy kod wyjścia, komunikat)."""


def load_shards(paths):
    shards = []
    for path in paths:
        with open(path, encoding="utf-8") as fh:
            shards.append((path, json.load(fh)))
    return shards


def check_consistent(shards):
    """Sprawdza sha/issue/config/status/specyfikacje ramion i komplet K/N.

    Zwraca (n, ordered) — liczbę kawałków oczekiwaną z `K/N` i kawałki
    posortowane po `K`.
    """
    if not shards:
        raise MergeError("brak plików kawałków do złożenia")

    first_path, first = shards[0]
    if "shard" not in first:
        raise MergeError(first_path + ": brak pola `shard` — to nie jest kawałek")

    parsed = []
    for path, data in shards:
        if "shard" not in data:
            raise MergeError(path + ": brak pola `shard` — to nie jest kawałek")
        try:
            k, n = parse_shard(data["shard"])
        except ValueError as exc:
            raise MergeError(path + ": " + str(exc)) from exc
        parsed.append((k, n, path, data))

    n_values = {n for _, n, _, _ in parsed}
    if len(n_values) > 1:
        raise MergeError("kawałki mają różne N w `shard`: " + str(sorted(n_values)))
    n = n_values.pop()

    seen = {}
    for k, _, path, data in parsed:
        if k in seen:
            raise MergeError(
                "zdublowany kawałek {0}/{1}: {2} i {3}".format(k, n, seen[k], path)
            )
        seen[k] = path
    missing = sorted(set(range(1, n + 1)) - set(seen))
    if missing:
        raise MergeError(
            "brakuje kawałków {0} (z {1}/{2})".format(
                ", ".join(str(m) + "/" + str(n) for m in missing), n, n
            )
        )

    for path, data in shards:
        if data.get("status") != STATUS_OK:
            raise MergeError(
                path + ": status `" + str(data.get("status")) + "` — złóż tylko kawałki `ok`"
            )
        if data.get("sha") != first.get("sha"):
            raise MergeError(
                "różny `sha`: " + first_path + "=" + str(first.get("sha"))
                + " vs " + path + "=" + str(data.get("sha"))
            )
        if data.get("issue") != first.get("issue"):
            raise MergeError(
                "różny `issue`: " + first_path + "=" + str(first.get("issue"))
                + " vs " + path + "=" + str(data.get("issue"))
            )
        if data.get("config") != first.get("config"):
            raise MergeError("różny `config` między " + first_path + " i " + path)
        if set(data.get("arms", {})) != set(first.get("arms", {})):
            raise MergeError("różny zestaw ramion między " + first_path + " i " + path)
        for arm_name, arm in data.get("arms", {}).items():
            first_arm = first["arms"][arm_name]
            if arm.get("policy") != first_arm.get("policy"):
                raise MergeError(
                    "ramię `" + arm_name + "`: różna polityka między "
                    + first_path + " i " + path
                )
            if arm.get("weights_hash") != first_arm.get("weights_hash"):
                raise MergeError(
                    "ramię `" + arm_name + "`: różny `weights_hash` między "
                    + first_path + " i " + path
                )

    ordered = [data for _, data in sorted(
        ((k, data) for k, _, _, data in parsed), key=lambda item: item[0]
    )]
    return n, ordered


def merge_arm(shard_arms):
    """Scala jedno ramię ze wszystkich kawałków (już posortowanych po `K`)."""
    merged = {"policy": shard_arms[0]["policy"]}
    if "weights_hash" in shard_arms[0]:
        merged["weights_hash"] = shard_arms[0]["weights_hash"]

    sets = {}
    for key in ("fixed", "rotated"):
        scores, survivals, capped_flags = [], [], []
        for arm in shard_arms:
            scores += arm[key]["scores"]
            survivals += arm[key]["survivals"]
            capped_flags += arm[key]["capped_flags"]
        summary = aggregate_set(scores, survivals, capped_flags)
        summary["scores"] = scores
        merged[key] = summary
        sets[key] = summary

    base = sets["fixed"]["mean"]
    merged["overfit_gap_pct"] = (
        round(100.0 * (base - sets["rotated"]["mean"]) / base, 2) if base else 0.0
    )
    return merged


def merge(shards):
    """`shards` już zweryfikowane i posortowane po `K` przez `check_consistent`."""
    first = shards[0]
    record = {
        "sha": first["sha"],
        "dirty": first["dirty"],
        "issue": first["issue"],
        "status": STATUS_OK,
        "blocked_reason": None,
        "config": first["config"],
        "source_hashes": first["source_hashes"],
        "arms": {},
        "deltas": {},
        "duration_s": round(sum(data["duration_s"] for data in shards), 1),
    }

    for arm_name in first["arms"]:
        record["arms"][arm_name] = merge_arm([data["arms"][arm_name] for data in shards])

    if "candidate" in record["arms"]:
        cand_scores = record["arms"]["candidate"]["fixed"]["scores"]
        for name in ("previous", "record"):
            if name in record["arms"]:
                record["deltas"]["kandydat vs " + name] = paired_delta(
                    cand_scores,
                    record["arms"][name]["fixed"]["scores"],
                    record["config"]["threshold_pct"],
                )

    strip_scores(record)
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description="Składa kawałki benchmark.py --shard K/N")
    parser.add_argument("--out", required=True, help="ścieżka scalonego rekordu")
    parser.add_argument("shards", nargs="+", help="pliki kawałków (bench/*-shard*.json)")
    args = parser.parse_args(argv)

    try:
        shards = load_shards(args.shards)
        _, ordered = check_consistent(shards)
        record = merge(ordered)
    except MergeError as exc:
        print("merge_bench: " + str(exc), file=sys.stderr)
        return 1

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, ensure_ascii=False)
    print("Złożono " + str(len(shards)) + " kawałków -> " + args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
