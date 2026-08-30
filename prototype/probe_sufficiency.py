"""
probe_sufficiency.py -- a test we ran against our own claim.

THE QUESTION
    Our method shares noised cluster summaries (centres, variances, counts) and
    rehearses on synthetic records drawn from them. If those summaries are a
    good enough description of the data, then someone could skip the federated
    training entirely, generate synthetic records from the summaries, and train
    one model centrally. If that works as well as our system, then our result is
    telling us about the synthetic data, not about the method.

WHAT THIS DOES
    Builds the memory bank exactly as the system does, then throws away the
    federated learning: it draws 4,000 synthetic records per class from the
    bank and trains a fresh model centrally on those alone. No rounds, no
    clients, no continual learning, no ledger.

    It runs this in both data settings:
      HARD_DATA = False  Gaussian blobs
      HARD_DATA = True   correlated, skewed, heavy-tailed features, where a
                         diagonal-Gaussian summary is not a sufficient statistic

RESULT (reported honestly in the paper)
    The probe scores about the same as our full federated system in both
    settings. That is a real limitation of this benchmark, not a strength: where
    document categories differ mainly in their average feature values, a compact
    summary of those averages carries most of the signal. It does not show the
    method is worthless; it shows this synthetic benchmark cannot separate
    "prototype replay works" from "this data is easy to summarise". Settling
    that needs real documents.

Run: python3 probe_sufficiency.py
"""
import importlib.util
import json
import numpy as np

spec = importlib.util.spec_from_file_location("m", "fcl_sim.py")
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

SYNTH_PER_CLASS = 4000
EPOCHS = 40


def build_bank_and_tests(seed):
    rng = np.random.default_rng(seed)
    stages, tests = [], []
    for t in range(m.N_STAGES):
        x, y = m.make_stage(seed, t, m.N_TRAIN_PER_CLASS,
                            np.random.default_rng(seed * 100 + t))
        stages.append(m.split_non_iid(rng, x, y, m.N_CLIENTS))
        tests.append(m.make_stage(seed, t, m.N_TEST_PER_CLASS,
                                  np.random.default_rng(seed * 100 + t + 55_000)))
    bank = {}
    for t in range(m.N_STAGES):
        for c in range(m.N_CLIENTS):
            for cls, v in m.build_prototypes(*stages[t][c], rng).items():
                if cls not in bank:
                    bank[cls] = v
                else:
                    oc, ov, ocnt = bank[cls]
                    bank[cls] = (np.vstack([oc, v[0]])[:m.K_PROTO * 2],
                                 (ov + v[1]) / 2.0,
                                 np.concatenate([ocnt, v[2]])[:m.K_PROTO * 2])
    return bank, tests, rng


def central_on_synthetic(seed):
    bank, tests, rng = build_bank_and_tests(seed)
    saved = m.REPLAY_PER_CLASS
    m.REPLAY_PER_CLASS = SYNTH_PER_CLASS
    X, Y = m.sample_replay(bank, rng)
    m.REPLAY_PER_CLASS = saved

    p = m.init_params(rng)
    for _e in range(EPOCHS):
        order = rng.permutation(len(Y))
        for s in range(0, len(Y), m.BATCH):
            b = order[s:s + m.BATCH]
            g = m.clip(m.grads(p, X[b], Y[b]))
            for k in p:
                p[k] -= m.LR * g[k]
    return [m.accuracy(p, *tests[j]) for j in range(m.N_STAGES)]


if __name__ == "__main__":
    out = {}
    for hard in (False, True):
        m.HARD_DATA = hard
        a = np.array([central_on_synthetic(s) for s in m.SEEDS])
        fed = [m.metrics(x)[0] for x in (m.run_method("replay", s) for s in m.SEEDS)]
        key = "hard_data" if hard else "gaussian_data"
        out[key] = {
            "central_on_synthetic_only_ACC": round(float(a.mean()) * 100, 1),
            "federated_prototype_replay_ACC": round(float(np.mean(fed)) * 100, 1),
            "chance_ACC": 50.0,
            "per_stage_central": [round(float(x) * 100, 1) for x in a.mean(axis=0)],
        }
        print(f"HARD_DATA={hard}")
        print(f"  central model trained on synthetic replay data only: "
              f"ACC {a.mean()*100:.1f}")
        print(f"  federated prototype replay (our system):             "
              f"ACC {np.mean(fed)*100:.1f}")
        print("  chance accuracy on each stage is 50 percent "
              "(each stage's test set has two classes)\n")

    json.dump({"seeds": m.SEEDS, "synthetic_records_per_class": SYNTH_PER_CLASS,
               "results": out}, open("probe_results.json", "w"), indent=2)
    print("Wrote probe_results.json")
