"""Pomiar treningu RL na runnerze bez GPU (#40). Jednorazowe narzędzie pomiarowe, wynik w JSON.

    python tools/rl_measure.py --train-seconds 900 --out rl-out/result.json
"""
import argparse
import json
import os
import pickle
import random
import statistics
import sys
import time

sys.path.insert(0, os.getcwd())

import numpy as np
import torch

from agent import Agent, BATCH_SIZE
from game import Game
from policies import ModelPolicy
from benchmark import run_set, fixed_seeds, load_config


def clock():
    return time.perf_counter()


def sim_only(n_games=200):
    """Sam symulator: losowe ruchy z game.available_actions, bez agenta i sieci."""
    rng = random.Random(0)
    steps, t0 = 0, clock()
    for s in range(n_games):
        g = Game(seed=s)
        while not g.done:
            acts = g.available_actions()
            if not acts:
                break
            g.step(rng.choice(acts))
            steps += 1
    dt = clock() - t0
    return {"games": n_games, "steps": steps, "seconds": round(dt, 2), "steps_per_s": round(steps / dt, 1)}


def evaluate(agent, seeds, cap):
    agent.model.eval()
    res = run_set(ModelPolicy(agent, "rl"), seeds, cap)
    agent.model.train()
    return {k: res[k] for k in ("mean", "median", "p10", "survival_mean", "capped_pct")}


def train(agent, seconds, eval_every, eval_seeds, cap):
    """Ta sama pętla co agent.train(): get_state -> get_action -> step -> get_state -> short -> remember -> long przy done.
    Różnica: seedy partii są różne (oryginał zawsze 42) i pętla jest ograniczona czasem."""
    T = {"get_state": 0.0, "get_action": 0.0, "game_step": 0.0, "train_short": 0.0, "train_long": 0.0}
    steps = games = long_steps = 0
    curve = []
    train_time = 0.0
    next_eval = eval_every
    rng = random.Random(1)
    game = Game(seed=rng.randrange(2**31))
    state_new = agent.get_state(game)
    while train_time < seconds:
        t_iter = clock()
        state_old = state_new
        t = clock()
        move = agent.get_action(state_old[:3])  # train() z agent.py przekazuje 4 elementy i wywraca się na gałęzi sieci
        T["get_action"] += clock() - t
        t = clock()
        reward, score, done, _ = game.step(move)
        T["game_step"] += clock() - t
        t = clock()
        state_new = agent.get_state(game)
        T["get_state"] += clock() - t
        t = clock()
        agent.train_short_term(state_old, move, reward, state_new, done)
        T["train_short"] += clock() - t
        agent.remember(state_old, move, reward, state_new, done)
        steps += 1
        if done:
            games += 1
            agent.n_games += 1
            t = clock()
            agent.train_long_term()
            T["train_long"] += clock() - t
            long_steps += 1
            game.reset(seed=rng.randrange(2**31))
            state_new = agent.get_state(game)
        train_time += clock() - t_iter
        if train_time >= next_eval:
            ev = evaluate(agent, eval_seeds, cap)
            ev.update(train_seconds=round(train_time), steps=steps, games=games, epsilon=round(agent.epsilon, 3))
            curve.append(ev)
            print("EVAL", json.dumps(ev), flush=True)
            next_eval += eval_every
    total = sum(T.values())
    return {
        "steps": steps, "games": games, "train_seconds": round(train_time, 1),
        "steps_per_s": round(steps / train_time, 2),
        "share_pct": {k: round(100 * v / total, 1) for k, v in T.items()},
        "ms_per_step": {k: round(1000 * v / steps, 3) for k, v in T.items()},
        "curve": curve,
    }


def checkpoint_cost(agent, path="ckpt.pkl"):
    payload = {
        "model": agent.model.state_dict(),
        "target": agent.trainer.target_model.state_dict(),
        "optim": agent.trainer.optimizer.state_dict(),
        "steps": agent.trainer.steps,
        "memory": list(agent.memory),
    }
    t = clock()
    torch.save(payload, path)
    save_s = clock() - t
    size = os.path.getsize(path)
    t = clock()
    torch.load(path, weights_only=False)
    load_s = clock() - t
    t = clock()
    torch.save(agent.model.state_dict(), "w.pth")
    w_s = clock() - t
    return {"replay_len": len(agent.memory), "full_save_s": round(save_s, 2), "full_load_s": round(load_s, 2),
            "full_size_mb": round(size / 1e6, 1), "weights_only_save_s": round(w_s, 3),
            "weights_only_size_mb": round(os.path.getsize("w.pth") / 1e6, 2)}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--train-seconds", type=int, default=900)
    p.add_argument("--eval-every", type=int, default=300)
    p.add_argument("--eval-seeds", type=int, default=50)
    p.add_argument("--out", default="result.json")
    a = p.parse_args()

    cfg = load_config()
    seeds = fixed_seeds(cfg)[: a.eval_seeds]
    out = {"cpus": os.cpu_count(), "torch": torch.__version__, "threads": torch.get_num_threads()}
    torch.manual_seed(0)
    random.seed(0)
    np.random.seed(0)

    out["sim_only"] = sim_only()
    print("SIM", out["sim_only"], flush=True)
    agent = Agent()
    out["train"] = train(agent, a.train_seconds, a.eval_every, seeds, cfg["move_cap"])
    print("TRAIN", json.dumps({k: v for k, v in out["train"].items() if k != "curve"}), flush=True)
    out["checkpoint"] = checkpoint_cost(agent)
    print("CKPT", out["checkpoint"], flush=True)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    with open(a.out, "w") as fh:
        json.dump(out, fh, indent=1)


if __name__ == "__main__":
    main()
