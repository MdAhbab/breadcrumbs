"""
Transactions and blocks.

A transaction here follows Fabric's execute-order-validate model rather than
Ethereum's order-execute. The distinction matters and is worth stating because
judges ask about it:

  order-execute      every node runs every transaction, so the contract must be
                     deterministic *and* every node pays the full cost.
  execute-order-validate
                     a subset of peers (the endorsers) simulate the transaction
                     first and produce a read/write set. The orderer never runs
                     the contract at all; it only sequences the results. Every
                     peer then validates the read set against its own state
                     before committing.

The second is why a permissioned chain can be fast and why the Continuity Gate
can rely on off-chain evaluation: endorsers do the expensive work, the ledger
records what they agreed on.

The read/write set is what makes this safe. A transaction declares which keys it
read (with the versions it saw) and which it writes. At commit time, if any key
it read has changed version since, the transaction is invalidated rather than
applied. That is multi-version concurrency control, and it is the reason two
factories committing at once cannot silently overwrite each other.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .crypto import TAG_BLOCK, TAG_NODE, TAG_TX, h, hash_object


@dataclass
class ReadKey:
    """A key that was read during simulation, and the version it had then."""

    key: str
    version: int

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "version": self.version}


@dataclass
class WriteKey:
    """A key the transaction wants to set. value None means delete."""

    key: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return {"key": self.key, "value": self.value}


@dataclass
class Endorsement:
    """
    One organisation's signature over a proposal's outcome.

    It carries the endorser's *certificate*, not a bare public key. That
    distinction is the whole security property: a signature proves someone holds
    a private key, and only a certificate issued by the organisation's CA proves
    which someone. Carrying a raw key would let anyone generate a keypair, claim
    any MSP, and have the signature counted toward the policy.
    """

    msp_id: str
    identity_id: str
    certificate_pem: str
    signature: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "msp_id": self.msp_id,
            "identity_id": self.identity_id,
            "certificate_pem": self.certificate_pem,
            "signature": self.signature,
        }


@dataclass
class Transaction:
    """A proposal that has been simulated and endorsed, awaiting ordering."""

    channel: str
    chaincode: str
    function: str
    args: dict[str, Any]
    submitter: str
    timestamp: str
    read_set: list[ReadKey] = field(default_factory=list)
    write_set: list[WriteKey] = field(default_factory=list)
    endorsements: list[Endorsement] = field(default_factory=list)
    response: Any = None
    nonce: str = ""

    def payload(self) -> dict[str, Any]:
        """
        The bytes the endorsers sign.

        Note what is included: the read and write sets, not just the arguments.
        Signing only the arguments would let a malicious peer return a different
        result than it simulated and still produce a valid-looking signature.
        """
        return {
            "channel": self.channel,
            "chaincode": self.chaincode,
            "function": self.function,
            "args": self.args,
            "submitter": self.submitter,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "read_set": [r.to_dict() for r in self.read_set],
            "write_set": [w.to_dict() for w in self.write_set],
            "response": self.response,
        }

    @property
    def tx_id(self) -> str:
        return hash_object(TAG_TX, self.payload())

    def to_dict(self) -> dict[str, Any]:
        d = self.payload()
        d["tx_id"] = self.tx_id
        d["endorsements"] = [e.to_dict() for e in self.endorsements]
        return d


def _merkle_root(hashes: list[str]) -> str:
    """
    Root over the transaction hashes in a block.

    An odd node is promoted rather than duplicated. Duplicating the last hash is
    the CVE-2012-2459 bug in Bitcoin: two different transaction lists can then
    produce the same root.
    """
    if not hashes:
        return h(TAG_NODE, b"")
    level = list(hashes)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level) - 1, 2):
            nxt.append(h(TAG_NODE, bytes.fromhex(level[i]), bytes.fromhex(level[i + 1])))
        if len(level) % 2 == 1:
            nxt.append(level[-1])
        level = nxt
    return level[0]


@dataclass
class Block:
    """One block. The hash chain is what makes history expensive to rewrite."""

    number: int
    previous_hash: str
    transactions: list[Transaction]
    proposer: str
    timestamp: str

    @property
    def data_hash(self) -> str:
        return _merkle_root([t.tx_id for t in self.transactions])

    def header(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "previous_hash": self.previous_hash,
            "data_hash": self.data_hash,
            "proposer": self.proposer,
            "timestamp": self.timestamp,
        }

    @property
    def block_hash(self) -> str:
        return hash_object(TAG_BLOCK, self.header())

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.header(),
            "block_hash": self.block_hash,
            "transactions": [t.to_dict() for t in self.transactions],
        }


def genesis_block(channel: str, config: dict[str, Any], timestamp: str) -> Block:
    """
    Block 0 carries the channel configuration: which MSPs exist, which
    endorsement policies apply. Everything downstream is validated against it.
    """
    tx = Transaction(
        channel=channel,
        chaincode="_lifecycle",
        function="init_channel",
        args=config,
        submitter="genesis",
        timestamp=timestamp,
        write_set=[WriteKey(key="__config__", value=config)],
        response={"status": "initialised"},
    )
    return Block(
        number=0,
        previous_hash="0" * 64,
        transactions=[tx],
        proposer="genesis",
        timestamp=timestamp,
    )
