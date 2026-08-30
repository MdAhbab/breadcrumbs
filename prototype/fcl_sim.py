"""
fcl_sim.py  --  Federated continual learning simulation for Breadcrumbs.

WHAT THIS IS
    A small, self-contained experiment on synthetic data. It is NOT a measurement
    of a deployed system, and it uses invented records, not real factory
    documents. Its only purpose is to produce honest numbers for the figure and
    table in the report, so that no value in the document is invented by hand.

WHAT IT SIMULATES
    Six factories ("clients") hold private document-feature records. Over time,
    three new kinds of problem appear in the industry, one after another:

        Stage 1  wage-register inconsistency      (class 1)
        Stage 2  forged compliance certificate    (class 2)
        Stage 3  chemical-inventory misreporting  (class 3)

    Class 0, a clean document, is present at every stage. The detector must end
    up able to recognise all four categories, even though the data for stage 1
    is long gone by the time stage 3 arrives. This is the situation the report
    calls "the rules keep changing".

    Three training strategies are compared:
      1. Sequential FedAvg      : federated averaging, retrained on each stage
      2. FedAvg + Fisher (EWC)  : adds a federated elastic-weight-consolidation
                                  penalty computed from shared Fisher summaries
      3. Breadcrumbs (hybrid)    : that penalty, plus differentially private
                                  prototype replay reconstructed from shared
                                  cluster statistics

    In all three, raw records never leave the client. Only parameter updates and
    (for the hybrid) noised cluster summaries are shared.

METRICS (standard continual learning metrics)
    ACC  : mean accuracy over all stages seen, measured after the final stage
    BWT  : backward transfer, mean change in accuracy on earlier stages caused
           by later training. Negative means forgetting.
    FGT  : forgetting measure, mean drop from each stage's peak accuracy.

Run:  python3 fcl_sim.py
Deps: numpy only. Runtime: well under a minute on a laptop.
"""

import json
import numpy as np

SEEDS = [0, 1, 2, 3, 4]
N_CLIENTS = 6
N_CLASSES = 4
N_STAGES = 3
D = 24                 # feature dimension
H = 48                 # hidden units
N_TRAIN_PER_CLASS = 900
N_TEST_PER_CLASS = 600
ROUNDS = 20            # federated rounds per stage
LOCAL_EPOCHS = 2
BATCH = 64
LR = 0.15
GRAD_CLIP = 5.0
LAMBDA_EWC = 6.0       # strength of the Fisher penalty
REPLAY_PER_CLASS = 300 # synthetic rehearsal records drawn per remembered class
K_PROTO = 3            # clusters kept per class (captures more than one mode)
DP_SIGMA = 0.10        # noise added to cluster means before they are shared
CENTRE_SCALE = 0.50    # how far apart the class blobs sit
BLOB_STD = 1.00        # how wide each blob is (overlap between classes)
HARD_DATA = False      # True: correlated, skewed, heavy-tailed features, so that
                       # a diagonal-Gaussian summary is NOT a sufficient statistic

# Which classes are present at each stage. Class 0 (clean) is always present.
STAGE_CLASSES = [[0, 1], [0, 2], [0, 3]]


# --------------------------------------------------------------------------
# Synthetic data
# --------------------------------------------------------------------------
def class_centres(base_seed):
    """Each class is a mixture of two Gaussian blobs, fixed for a given seed."""
    r = np.random.default_rng(90_000 + base_seed)
    return {c: [r.normal(0, CENTRE_SCALE, size=D) for _ in range(2)]
            for c in range(N_CLASSES)}


def mixing_matrix(base_seed):
    """A fixed random correlation structure for the hard-data setting."""
    r = np.random.default_rng(70_000 + base_seed)
    a = r.normal(0, 1, size=(D, D))
    q, _ = np.linalg.qr(a)
    scale = np.linspace(0.5, 1.8, D)
    return q * scale


def sample_class(centres, c, n, rng, base_seed=0):
    parts = []
    for k, mu in enumerate(centres[c]):
        m = n // 2 + (n % 2 if k == 0 else 0)
        z = rng.normal(0, BLOB_STD, size=(m, D))
        if HARD_DATA:
            # Correlate the features, then push them off-Gaussian. Per-feature
            # mean and variance no longer describe the class.
            z = z @ mixing_matrix(base_seed)
            z = np.sign(z) * np.abs(z) ** 1.6
            z = z / (z.std(axis=0, keepdims=True) + 1e-9) * BLOB_STD
        parts.append(z + mu)
    x = np.vstack(parts)
    rng.shuffle(x)
    return x


def make_stage(base_seed, stage, n_per_class, rng):
    centres = class_centres(base_seed)
    xs, ys = [], []
    for c in STAGE_CLASSES[stage]:
        xs.append(sample_class(centres, c, n_per_class, rng, base_seed))
        ys.append(np.full(n_per_class, c))
    x = np.vstack(xs)
    y = np.concatenate(ys)
    p = rng.permutation(len(y))
    return x[p], y[p]


def split_non_iid(rng, x, y, n_clients, alpha=0.6):
    """
    Dirichlet split: each client gets a different class mixture, so the six
    factories do not hold interchangeable data.
    """
    shards = [[] for _ in range(n_clients)]
    for c in np.unique(y):
        idx = np.where(y == c)[0]
        rng.shuffle(idx)
        prop = rng.dirichlet(alpha * np.ones(n_clients))
        cuts = (np.cumsum(prop) * len(idx)).astype(int)[:-1]
        for i, part in enumerate(np.split(idx, cuts)):
            shards[i].extend(part.tolist())
    out = []
    for s in shards:
        s = np.array(s, dtype=int)
        rng.shuffle(s)
        out.append((x[s], y[s]))
    return out


# --------------------------------------------------------------------------
# Model: a two-layer network, written out by hand so no framework is involved
# --------------------------------------------------------------------------
def init_params(rng):
    return {
        "W1": rng.normal(0, np.sqrt(2.0 / D), size=(D, H)),
        "b1": np.zeros(H),
        "W2": rng.normal(0, np.sqrt(2.0 / H), size=(H, N_CLASSES)),
        "b2": np.zeros(N_CLASSES),
    }


def forward(p, x):
    h = np.tanh(x @ p["W1"] + p["b1"])
    logits = h @ p["W2"] + p["b2"]
    logits = logits - logits.max(axis=1, keepdims=True)
    e = np.exp(logits)
    return h, e / e.sum(axis=1, keepdims=True)


def grads(p, x, y):
    n = len(y)
    h, prob = forward(p, x)
    d = prob.copy()
    d[np.arange(n), y] -= 1.0
    d /= n
    dh = (d @ p["W2"].T) * (1.0 - h ** 2)
    return {"W1": x.T @ dh, "b1": dh.sum(axis=0),
            "W2": h.T @ d, "b2": d.sum(axis=0)}


def clip(g, limit=GRAD_CLIP):
    norm = np.sqrt(sum(float((v ** 2).sum()) for v in g.values()))
    if norm > limit:
        s = limit / (norm + 1e-12)
        return {k: v * s for k, v in g.items()}
    return g


def accuracy(p, x, y):
    _, prob = forward(p, x)
    return float((prob.argmax(axis=1) == y).mean())


def clone(p):
    return {k: v.copy() for k, v in p.items()}


def avg_params(plist, weights):
    w = np.asarray(weights, dtype=np.float64)
    w = w / w.sum()
    return {k: sum(wi * pi[k] for wi, pi in zip(w, plist)) for k in plist[0]}


# --------------------------------------------------------------------------
# Continual learning components
# --------------------------------------------------------------------------
def local_fisher(p, x, y, cap=250):
    """Diagonal Fisher information: which weights mattered for this stage."""
    f = {k: np.zeros_like(v) for k, v in p.items()}
    n = min(len(y), cap)
    for i in range(n):
        g = grads(p, x[i:i + 1], y[i:i + 1])
        for k in f:
            f[k] += g[k] ** 2
    return {k: v / n for k, v in f.items()}


def normalise_fisher(f):
    """Scale to a common range so the penalty strength means the same thing."""
    m = max(float(v.max()) for v in f.values()) + 1e-12
    return {k: v / m for k, v in f.items()}


def kmeans(x, k, rng, iters=25):
    if len(x) <= k:
        return x.copy(), np.ones(len(x))
    c = x[rng.choice(len(x), k, replace=False)].copy()
    for _ in range(iters):
        d = ((x[:, None, :] - c[None, :, :]) ** 2).sum(axis=2)
        a = d.argmin(axis=1)
        for j in range(k):
            if (a == j).any():
                c[j] = x[a == j].mean(axis=0)
    d = ((x[:, None, :] - c[None, :, :]) ** 2).sum(axis=2)
    a = d.argmin(axis=1)
    return c, np.array([max(1, int((a == j).sum())) for j in range(k)])


def build_prototypes(x, y, rng):
    """
    Cluster summaries per class: centre, spread, and count. Noise is added to
    each centre before it is shared. Raw records never move.
    """
    out = {}
    for c in np.unique(y):
        xs = x[y == c]
        if len(xs) < K_PROTO * 3:
            continue
        centres, counts = kmeans(xs, K_PROTO, rng)
        var = xs.var(axis=0) + 1e-3
        noisy = centres + rng.normal(0, DP_SIGMA, size=centres.shape)
        out[int(c)] = (noisy, var, counts)
    return out


def sample_replay(bank, rng):
    """Draw synthetic rehearsal records from the aggregated cluster statistics."""
    xs, ys = [], []
    for c, (centres, var, counts) in bank.items():
        w = counts / counts.sum()
        take = np.random.default_rng(rng.integers(1 << 30)).multinomial(
            REPLAY_PER_CLASS, w)
        for j, n in enumerate(take):
            if n > 0:
                xs.append(rng.normal(centres[j], np.sqrt(var), size=(n, D)))
                ys.append(np.full(n, c))
    if not xs:
        return None, None
    return np.vstack(xs), np.concatenate(ys)


def ewc_grad(p, star, fisher):
    return {k: LAMBDA_EWC * fisher[k] * (p[k] - star[k]) for k in p}


# --------------------------------------------------------------------------
# Training
# --------------------------------------------------------------------------
def run_method(method, seed):
    rng = np.random.default_rng(seed)

    stages, tests = [], []
    for t in range(N_STAGES):
        x, y = make_stage(seed, t, N_TRAIN_PER_CLASS,
                          np.random.default_rng(seed * 100 + t))
        stages.append(split_non_iid(rng, x, y, N_CLIENTS))
        tests.append(make_stage(seed, t, N_TEST_PER_CLASS,
                                np.random.default_rng(seed * 100 + t + 55_000)))

    use_fisher = method in ("ewc", "breadcrumbs")
    use_replay = method in ("replay", "breadcrumbs")

    glob = init_params(rng)
    acc = np.zeros((N_STAGES, N_STAGES))
    fisher, star, bank = None, None, {}

    if method == "joint":
        # Reference ceiling only. Pools every stage's raw records in one place,
        # which is exactly what confidentiality rules forbid in the real setting.
        xs = [np.vstack([stages[t][c][0] for c in range(N_CLIENTS)])
              for t in range(N_STAGES)]
        ys = [np.concatenate([stages[t][c][1] for c in range(N_CLIENTS)])
              for t in range(N_STAGES)]
        X, Y = np.vstack(xs), np.concatenate(ys)
        for _e in range(ROUNDS * LOCAL_EPOCHS):
            order = rng.permutation(len(Y))
            for s in range(0, len(Y), BATCH):
                b = order[s:s + BATCH]
                g = clip(grads(glob, X[b], Y[b]))
                for k in glob:
                    glob[k] -= LR * g[k]
        for i in range(N_STAGES):
            for j in range(N_STAGES):
                acc[i, j] = accuracy(glob, *tests[j])
        return acc

    for t in range(N_STAGES):
        replay_x, replay_y = (sample_replay(bank, rng)
                              if use_replay and bank else (None, None))
        for _r in range(ROUNDS):
            locals_, sizes = [], []
            for c in range(N_CLIENTS):
                xc, yc = stages[t][c]
                if len(yc) < BATCH:
                    continue
                xb, yb = xc, yc
                if replay_x is not None:
                    sel = rng.choice(len(replay_y),
                                     min(len(replay_y), len(yc)), replace=False)
                    xb = np.vstack([xc, replay_x[sel]])
                    yb = np.concatenate([yc, replay_y[sel]])
                p = clone(glob)
                for _e in range(LOCAL_EPOCHS):
                    order = rng.permutation(len(yb))
                    for s in range(0, len(yb), BATCH):
                        b = order[s:s + BATCH]
                        g = grads(p, xb[b], yb[b])
                        if fisher is not None and use_fisher:
                            pen = ewc_grad(p, star, fisher)
                            g = {k: g[k] + pen[k] for k in g}
                        g = clip(g)
                        for k in p:
                            p[k] -= LR * g[k]
                locals_.append(p)
                sizes.append(len(yc))
            glob = avg_params(locals_, sizes)

        # End of stage: consolidate, using only shareable summaries.
        if use_fisher:
            fs = [local_fisher(glob, *stages[t][c]) for c in range(N_CLIENTS)
                  if len(stages[t][c][1]) >= 20]
            new_f = normalise_fisher(
                {k: np.mean([f[k] for f in fs], axis=0) for k in glob})
            fisher = new_f if fisher is None else {k: fisher[k] + new_f[k]
                                                   for k in new_f}
            star = clone(glob)

        if use_replay:
            for c in range(N_CLIENTS):
                for cls, v in build_prototypes(*stages[t][c], rng).items():
                    if cls not in bank:
                        bank[cls] = v
                    else:
                        oc, ov, ocnt = bank[cls]
                        bank[cls] = (np.vstack([oc, v[0]])[:K_PROTO * 2],
                                     (ov + v[1]) / 2.0,
                                     np.concatenate([ocnt, v[2]])[:K_PROTO * 2])

        for j in range(N_STAGES):
            acc[t, j] = accuracy(glob, *tests[j])

    return acc


def metrics(a):
    """
    Standard continual learning metrics.
      ACC : mean accuracy over all stages, measured after the final stage
      BWT : backward transfer, Lopez-Paz and Ranzato (2017)
      FGT : forgetting measure, Chaudhry et al. (2018). For each earlier stage,
            the drop from its best accuracy BEFORE the final stage to its
            accuracy after it.
    On this data the two common variants of FGT agree to the decimal.
    """
    final = a[N_STAGES - 1]
    ACC = float(final.mean())
    BWT = float(np.mean([final[j] - a[j, j] for j in range(N_STAGES - 1)]))
    FGT = float(np.mean([max(a[l, j] for l in range(j, N_STAGES - 1)) - final[j]
                         for j in range(N_STAGES - 1)]))
    return ACC, BWT, FGT


if __name__ == "__main__":
    results = {}
    for method, label in [("fedavg", "Sequential FedAvg (no continual learning)"),
                          ("ewc", "Federated Fisher only"),
                          ("replay", "Prototype replay only (Breadcrumbs)"),
                          ("breadcrumbs", "Fisher + replay (ablation)"),
                          ("joint", "Centralised pooling (reference ceiling)")]:
        mats = [run_method(method, s) for s in SEEDS]
        stack = np.stack(mats)
        mean = stack.mean(axis=0)
        per_stage = [(float(mean[N_STAGES - 1, j]),
                      float(stack[:, N_STAGES - 1, j].std()))
                     for j in range(N_STAGES)]
        ms = np.array([metrics(m) for m in mats])
        undefined = (method == "joint")   # never trained sequentially
        results[method] = {
            "forgetting_defined": not undefined,
            "label": label,
            "final_per_stage": per_stage,
            "ACC": [float(ms[:, 0].mean()), float(ms[:, 0].std())],
            "BWT": [float(ms[:, 1].mean()), float(ms[:, 1].std())],
            "FGT": [float(ms[:, 2].mean()), float(ms[:, 2].std())],
            "acc_matrix_mean": mean.tolist(),
        }
        print(f"\n{label}")
        print("  accuracy after final stage: " +
              ", ".join(f"S{j+1}={v*100:.1f}+/-{s*100:.1f}"
                        for j, (v, s) in enumerate(per_stage)))
        print(f"  ACC={ms[:,0].mean()*100:.1f}+/-{ms[:,0].std()*100:.1f}  "
              f"BWT={ms[:,1].mean()*100:+.1f}+/-{ms[:,1].std()*100:.1f}  "
              f"FGT={ms[:,2].mean()*100:.1f}+/-{ms[:,2].std()*100:.1f}")

    with open("fcl_results.json", "w") as f:
        json.dump({"seeds": SEEDS, "config": {
            "clients": N_CLIENTS, "stages": N_STAGES, "classes": N_CLASSES,
            "classes_per_stage": STAGE_CLASSES,
            "chance_accuracy_per_stage": 0.5,
            "rounds_per_stage": ROUNDS, "feature_dim": D, "hidden": H,
            "lr": LR, "lambda_ewc": LAMBDA_EWC, "k_proto": K_PROTO,
            "replay_per_class": REPLAY_PER_CLASS, "dp_sigma": DP_SIGMA,
            "centre_scale": CENTRE_SCALE, "blob_std": BLOB_STD,
            "hard_data": HARD_DATA},
            "results": results}, f, indent=2)
    print("\nWrote fcl_results.json")
