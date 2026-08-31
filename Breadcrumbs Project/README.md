# Breadcrumbs Project

The working system behind the report in the repository root. The report describes it;
this directory runs it.

The report's §12 opens by conceding that the Continuity Gate — its main contribution — is
"specified but not built". **That is what this directory exists to fix.** The ledger is the
product here; the machine learning is a tool the ledger governs, not the other way round.

```
Breadcrumbs Project/
├── model/            The system's core. Ledger, chaincode, Merkle, federated learning.
│   ├── ledger/       Permissioned chain: MSP identity, ordering, endorsement, blocks, world state.
│   ├── chaincode/    Deterministic contracts: doccustody, fedmodel (Continuity Gate), reputation.
│   ├── merkle/       Merkle tree, proofs, single-line selective disclosure.
│   ├── ai/           Federated continual learning (PyTorch + Flower).
│   ├── datagen/      ~50,000 invented labelled documents with planted anomalies.
│   ├── fabric/       Real Hyperledger Fabric chaincode + docker-compose. See the note below.
│   └── experiments/  The original NumPy simulation. Provenance for every number in the report.
├── backend/          FastAPI + SQLite. Serves the frontend; wraps model/, never reimplements it.
├── frontend/         React + TypeScript client, and the design specifications.
└── deck/             Presentation prompt and assets.
```

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
