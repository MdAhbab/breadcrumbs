# Breadcrumbs Project

The working system behind the report in the repository root. The report describes it;
this directory runs it.

The ledger is the product here; the machine learning is a tool the ledger governs, not the
other way round.

**What this system does that the alternatives do not.** Every notarisation service proves a
document is genuine. None proves that the set you were shown is the whole set — and the
fraud that actually happens is not a forged register but a second one and a decision about
which to disclose. A *period seal* fixes the membership of a reporting period on-chain, so a
factory handing over four of its five payroll registers is caught by arithmetic while all
four of them verify perfectly. Around that sit three mechanisms sharing one RSA group:
constant-size verifier state, proofs that a record was *never* committed, constant-time
verification of an entire epoch, and a delay function that stops history being manufactured
faster than it can be lived. Each record is also counter-signed by an organisation that is
assigned rather than chosen, and that loses reputation if the record is later found false.

Run `make demo` and watch Act 6.

```
Breadcrumbs Project/
├── model/            The system's core. Ledger, chaincode, Merkle, federated learning.
│   ├── ledger/       Permissioned chain: MSP identity, ordering, endorsement, blocks, world state.
│   ├── chaincode/    Deterministic contracts: doccustody, fedmodel (Continuity Gate), reputation.
│   ├── merkle/       Merkle tree, proofs, single-line selective disclosure.
│   ├── accumulator/  RSA group, hash-to-prime, membership and absence proofs, VDF.
│   ├── bench/        Every measured number in the report. Writes ../results/*.json.
│   ├── ai/           Federated continual learning (PyTorch + Flower).
│   ├── datagen/      ~50,000 invented labelled documents with planted anomalies.
│   ├── fabric/       Real Hyperledger Fabric chaincode + docker-compose. See the note below.
│   └── experiments/  The original NumPy simulation. Provenance for every number in the report.
├── backend/          FastAPI + SQLite. Serves the frontend; wraps model/, never reimplements it.
├── frontend/         React + TypeScript client, and the design specifications.
├── deck/             Presentation prompt and assets.
├── AUDIT.md          Security review: findings, fixes, and what is still open.
└── SETUP.md          Getting this running on a fresh machine.
```

## Start here

```bash
make setup    # venv + all dependencies + frontend node modules
make demo     # the twelve-act end-to-end cycle
make test     # 206 tests
make attacks  # only the tests that attack the system
make bench    # measure everything, regenerate the report's numbers
```

`SETUP.md` covers a fresh machine. `AUDIT.md` is the security review: five
serious findings, all fixed, plus what is still open and why.
`docs/using-the-app.md` is the written guide to the product itself: what every
screen is called, what each role can do, and the difference between reading a
figure and proving one. The in-product walkthrough covers the same ground by
driving the real screens.

**Three attacks in the test suite succeed**, deliberately and on the record: a model
poisoned just inside the Continuity Gate's tolerance is promoted, a colluding assigned
witness is not stopped, and whoever holds the factorisation of the accumulator modulus can
forge a membership witness against the accumulator alone (though not against the ledger and
the anchored index, which is why the accumulator is an accelerator rather than an
authority). `make attacks` runs them all.

## Two ledgers, on purpose

`model/ledger/` is a permissioned blockchain written in Python: X.509 MSP identities,
endorsement policies, an ordering service, deterministic chaincode, hash-chained blocks
and a versioned world state. It is modelled on Hyperledger Fabric's architecture and it
genuinely runs — no Docker, no 16 GB requirement, any laptop.

`model/fabric/` is the same three chaincodes written as real Fabric contracts with a
`docker-compose` network. Requires Docker and about 16 GB.

Say it accurately: the Python chain is *Fabric-modelled*, not Fabric. Where a number or a
demo comes from the Python chain, that is what to claim.

## Reproducing the report's numbers

The simulation moved here from `prototype/` but did not change, and still reproduces
bit-identically:

```bash
cd model/experiments
python3 fcl_sim.py           # Table 4 and Figure 3
python3 sweep_difficulty.py  # Table 5
python3 probe_sufficiency.py # the test in Section 7.3 that we failed
```

NumPy only. Under a minute.
