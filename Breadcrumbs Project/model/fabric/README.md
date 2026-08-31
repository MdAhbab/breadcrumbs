# Running Breadcrumbs on real Hyperledger Fabric

**Status: written, not run here.** These assets were authored on a machine with
no Docker, no Go and 8 GB of memory, which cannot run Fabric's test network.
They are a faithful port of `model/chaincode/*.py`, and the hashing has been
cross-checked byte for byte against the Python implementation (see below), but
nobody has yet executed them against a live peer. Say exactly that if asked.
The Python ledger in `model/ledger/` **is** tested and does run.

Requirements: Docker, Docker Compose, Node 18+, about 16 GB of memory. WSL2 is
fine and is what this was written for.

## What is here

```
fabric/
├── chaincode/
│   ├── doccustody.js    document commitments, grants, receipts
│   ├── fedmodel.js      the Continuity Gate — Algorithm 1
│   ├── index.js         contract registration
│   └── package.json
└── network/
    └── deploy.sh        brings up a network and deploys both contracts
```

`reputation` is not ported. It is the least load-bearing of the three and the
Python version is the reference; port it the same way if you need it on Fabric.

## The hashing is compatible, and that matters

A benchmark hash sealed by the Python chain must verify inside Fabric chaincode,
or the two halves of this project are separate systems that merely resemble each
other. Both sides use sorted-key JSON with tight separators, and a
length-prefixed, domain-separated SHA-256. Verified identical:

```
{"alpha":{"a":1,"b":2},"n":800,"task_id":"wage_register_inconsistency","zeta":[1,2,3]}
87e9179abfc1de2fbf1fcacc89924e344478630691231937af0d72f2f5a988e3
```

One caveat to know before you rely on it: Python's `json.dumps` uses
`ensure_ascii=True` and JavaScript's `JSON.stringify` does not, so a non-ASCII
character in a payload would hash differently on the two sides. Every field that
reaches a hash today is ASCII. If that ever stops being true, fix it by escaping
in the JS rather than by relaxing the Python.

## Run it

```bash
cd model/fabric/network
./deploy.sh up        # fetch fabric-samples, start the network, create channels
./deploy.sh deploy    # package, install, approve and commit both chaincodes
./deploy.sh demo      # commit a record, then run a gate decision
./deploy.sh down      # tear everything down
```

## Determinism, and why this code looks the way it does

Every endorsing peer runs this chaincode and their read/write sets must match
byte for byte, or the transaction fails validation. So the contracts contain:

- no `Date.now()` — every timestamp arrives as an argument from the client
- no `Math.random()`
- no floating-point arithmetic — all accuracies are integers in basis points,
  and the median of an even count floors rather than averaging to a float
- no `JSON.stringify` on anything written to state — it does not sort keys, and
  two peers building an object in a different order would write different bytes

## What the gate does and does not guarantee

The contract does not evaluate the model. It cannot: a floating-point forward
pass through a neural network is not guaranteed identical across hardware, and
the weights are deliberately kept off-chain.

Instead each endorsing organisation evaluates the candidate itself against the
benchmark whose hash was committed before the round, and signs the accuracies it
measured. The contract verifies those signatures, requires `k` distinct
organisations, checks they agree within `delta`, takes medians, and applies the
threshold rule.

State the guarantee precisely: **promotion requires a threshold of independent
organisations to have evaluated the same committed benchmark and signed
compatible results. No single participant, including whoever runs the
aggregation server, can promote a model alone.** That is slightly weaker than
"computed on-chain", and the difference is worth being the one who points it out.

## Endorsement policy

Deploy `fedmodel` with a policy requiring three organisations, so the property
above is enforced by the network and not merely by the contract body:

```
"OutOf(3, 'Org1MSP.member', 'Org2MSP.member', 'Org3MSP.member')"
```

`deploy.sh` sets this. If you drop to the stock two-organisation test network,
lower it to `OutOf(2, ...)` and say so — a 2-of-2 policy is a materially weaker
claim than 3-of-5 and a judge is entitled to know which one is running.
