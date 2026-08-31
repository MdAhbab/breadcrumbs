"""
The network: channels, peers, and the transaction lifecycle.

This file is where the pieces meet. One transaction goes through five stages and
each one can reject it:

  1. propose   the client sends a proposal to the endorsing peers named by the
               chaincode's policy.
  2. simulate  each endorser runs the chaincode against its own world state
               *without committing*, producing a read set and a write set.
  3. endorse   each endorser signs the outcome. Divergent results are caught
               here: if two endorsers produce different write sets, the
               chaincode was not deterministic and the transaction is abandoned.
  4. order     the ordering service sequences the transaction into a block.
               It never inspects the contents.
  5. validate  every peer re-checks the endorsement policy and the read set
               versions before applying the write set. A transaction that
               passes 1-4 can still be invalidated here, and is marked as such
               in the block rather than dropped.

Stage 5 keeping invalid transactions in the block is not an oversight. The
ledger is a record of what was attempted, not only what succeeded. An auditor
asking "did anyone try to overwrite this?" deserves an answer.

Channels give confidentiality. A document channel is shared by exactly one
factory and one buyer, so a second buyer holds no copy of that data at all —
it is not encrypted-but-present, it is absent. The model channel is shared by
everyone, because a model version is a consortium-wide fact.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from .block import Block, Endorsement, ReadKey, Transaction, WriteKey, genesis_block
from .crypto import canonical, hash_object, new_salt, public_bytes, sign
from .crypto import TAG_BLOCK
from .endorsement import EndorsementValidator, Policy
from .identity import Identity, MSP
from .orderer import OrderingService
from .state import WorldState


class ChaincodeError(Exception):
    """Raised by a contract to reject a proposal with a reason."""


class Context:
    """
    What a chaincode is allowed to touch.

    Deliberately narrow: get, put, delete, range and the caller's identity.
    There is no clock, no randomness and no network access, because a contract
    that reads any of those cannot be deterministic and two endorsers would
    disagree. Where a timestamp is genuinely needed it arrives as an argument,
    signed by the client, so every endorser sees the same value.
    """

    def __init__(self, state: WorldState, channel: str, caller: Identity, msp: MSP):
        self._state = state
        self._channel = channel
        self.caller = caller
        self.msp = msp
        self.reads: dict[str, int] = {}
        self.writes: dict[str, Any] = {}

    @property
    def caller_msp(self) -> str:
        return self.caller.msp_id

    @property
    def caller_role(self) -> str | None:
        return self.msp.role_of(self.caller)

    def get(self, key: str) -> Any:
        """Read a key, recording the version seen so validation can re-check it."""
        if key in self.writes:  # read-your-own-writes within one transaction
            return self.writes[key]
        value, version = self._state.get(self._channel, key)
        self.reads.setdefault(key, version)
        return value

    def put(self, key: str, value: Any) -> None:
        self.writes[key] = value

    def delete(self, key: str) -> None:
        self.writes[key] = None

    def range(self, prefix: str) -> list[tuple[str, Any]]:
        out = list(self._state.range(self._channel, prefix))
        for key, _ in out:
            self.reads.setdefault(key, self._state.version(self._channel, key))
        return out

    def require(self, condition: bool, message: str) -> None:
        if not condition:
            raise ChaincodeError(message)


Chaincode = Callable[[Context, str, dict[str, Any]], Any]


@dataclass
class ChaincodeDef:
    name: str
    handler: Chaincode
    policy: Policy
    endorsers: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    tx_id: str
    valid: bool
    code: str
    reason: str = ""


class Channel:
    """One channel: its own chain, its own slice of world state."""

    def __init__(self, name: str, config: dict[str, Any], state: WorldState, timestamp: str):
        self.name = name
        self.config = config
        self.state = state
        self.blocks: list[Block] = []
        self.validation: dict[str, ValidationResult] = {}
        gb = genesis_block(name, config, timestamp)
        self._append(gb)
        for w in gb.transactions[0].write_set:
            self.state.apply(name, w.key, w.value)
        self.state.commit()

    def _append(self, block: Block) -> None:
        self.blocks.append(block)
        self.state.store_block(self.name, block.number, block.block_hash, block.to_dict())
        self.state.commit()

    @property
    def height(self) -> int:
        return len(self.blocks)

    @property
    def head(self) -> Block:
        return self.blocks[-1]

    def verify_chain(self) -> tuple[bool, str]:
        """
        Walk the whole chain and check every link against what was persisted.

        Comparing the in-memory blocks only against each other is not enough, and
        the difference matters. Block hashes are computed from the transactions
        they carry, so if an attacker edits a transaction and we then recompute
        everything from those same edited objects, the chain agrees with itself
        perfectly. Tampering with the *most recent* block would be invisible,
        because no later block back-links to it yet.

        So each block is checked against the hash recorded when it was committed.
        Three things must hold: the block still hashes to what was stored, its
        previous_hash matches the stored hash of the block before it, and block
        numbers are contiguous.
        """
        for i, block in enumerate(self.blocks):
            if block.number != i:
                return False, f"block {i} claims number {block.number}"

            stored = self.state.load_block(self.name, i)
            if stored is None:
                return False, f"block {i} is missing from persistent storage"

            recomputed = hash_object(TAG_BLOCK, block.header())
            if recomputed != stored["block_hash"]:
                return False, (
                    f"block {i} does not match its committed hash: recomputed "
                    f"{recomputed[:12]}…, ledger recorded {stored['block_hash'][:12]}…"
                )

            expected_prev = "0" * 64 if i == 0 else self.state.load_block(self.name, i - 1)["block_hash"]
            if block.previous_hash != expected_prev:
                return False, (
                    f"block {i} previous_hash {block.previous_hash[:12]}… does not match "
                    f"block {i - 1} hash {expected_prev[:12]}…"
                )
        return True, ""


class Network:
    """A consortium: MSP, ordering service, channels and installed chaincode."""

    def __init__(self, msp: MSP, orderer: OrderingService, state: WorldState | None = None):
        self.msp = msp
        self.orderer = orderer
        self.state = state or WorldState()
        self.validator = EndorsementValidator(msp)
        self.channels: dict[str, Channel] = {}
        self.chaincodes: dict[str, ChaincodeDef] = {}

    # -- setup ------------------------------------------------------------
    def create_channel(self, name: str, members: list[str], timestamp: str) -> Channel:
        config = {
            "channel": name,
            "members": sorted(members),
            "created": timestamp,
        }
        ch = Channel(name, config, self.state, timestamp)
        self.channels[name] = ch
        return ch

    def install(self, name: str, handler: Chaincode, policy: Policy, endorsers: list[str]) -> None:
        self.chaincodes[name] = ChaincodeDef(name, handler, policy, endorsers)

    # -- lifecycle --------------------------------------------------------
    def simulate(
        self,
        channel: str,
        chaincode: str,
        function: str,
        args: dict[str, Any],
        caller: Identity,
    ) -> tuple[Context, Any]:
        """Run a chaincode against current state without committing anything."""
        cc = self.chaincodes[chaincode]
        ctx = Context(self.state, channel, caller, self.msp)
        response = cc.handler(ctx, function, args)
        return ctx, response

    def propose(
        self,
        channel: str,
        chaincode: str,
        function: str,
        args: dict[str, Any],
        submitter: Identity,
        endorsers: list[Identity],
        timestamp: str,
    ) -> Transaction:
        """
        Stages 1 to 3. Every endorser simulates independently and signs.

        The determinism check is the interesting part: we compare the write sets
        every endorser produced. If a contract used a clock or a random number,
        they diverge here and we refuse to go any further, which is exactly what
        should happen. Fabric surfaces the same condition as ENDORSEMENT_MISMATCH.
        """
        ok, why = self.msp.validate(submitter)
        if not ok:
            raise ChaincodeError(f"submitter rejected: {why}")

        results: list[tuple[Identity, Context, Any]] = []
        for e in endorsers:
            valid, why = self.msp.validate(e)
            if not valid:
                raise ChaincodeError(f"endorser {e.id} rejected: {why}")
            ctx, response = self.simulate(channel, chaincode, function, args, submitter)
            results.append((e, ctx, response))

        first_ctx, first_response = results[0][1], results[0][2]
        baseline = canonical({"w": first_ctx.writes, "r": first_ctx.reads, "resp": first_response})
        for ident, ctx, response in results[1:]:
            if canonical({"w": ctx.writes, "r": ctx.reads, "resp": response}) != baseline:
                raise ChaincodeError(
                    f"endorsement mismatch: {ident.id} simulated a different result. "
                    "The chaincode is not deterministic."
                )

        tx = Transaction(
            channel=channel,
            chaincode=chaincode,
            function=function,
            args=args,
            submitter=submitter.id,
            timestamp=timestamp,
            nonce=new_salt(),
            read_set=[ReadKey(k, v) for k, v in sorted(first_ctx.reads.items())],
            write_set=[WriteKey(k, v) for k, v in sorted(first_ctx.writes.items())],
            response=first_response,
        )
        payload = tx.payload()
        for ident, _, _ in results:
            tx.endorsements.append(
                Endorsement(
                    msp_id=ident.msp_id,
                    identity_id=ident.id,
                    public_key=public_bytes(ident.public_key),
                    signature=sign(ident.private_key, payload),
                )
            )
        return tx

    def submit(self, tx: Transaction) -> tuple[bool, str]:
        """Stage 4. Hand to the ordering service."""
        return self.orderer.submit(tx)

    def commit(self, timestamp: str) -> Block | None:
        """
        Stage 5. Cut a block, validate every transaction in it, apply what passes.

        Two independent checks per transaction, and both must pass:
          - the endorsement policy, re-evaluated from the signatures themselves
          - the read set, re-checked against current versions (MVCC)
        """
        ch_name = self.orderer._pending[0].channel if self.orderer._pending else None
        if ch_name is None:
            return None
        channel = self.channels[ch_name]
        block = self.orderer.cut(channel.height, channel.head.block_hash, timestamp)
        if block is None:
            return None

        for tx in block.transactions:
            cc = self.chaincodes.get(tx.chaincode)
            if cc is None:
                channel.validation[tx.tx_id] = ValidationResult(
                    tx.tx_id, False, "UNKNOWN_CHAINCODE", tx.chaincode
                )
                continue

            ok, why = self.validator.check(tx.payload(), tx.endorsements, cc.policy)
            if not ok:
                channel.validation[tx.tx_id] = ValidationResult(
                    tx.tx_id, False, "ENDORSEMENT_POLICY_FAILURE", why
                )
                continue

            stale = [
                r.key
                for r in tx.read_set
                if self.state.version(tx.channel, r.key) != r.version
            ]
            if stale:
                channel.validation[tx.tx_id] = ValidationResult(
                    tx.tx_id,
                    False,
                    "MVCC_READ_CONFLICT",
                    f"keys changed since simulation: {', '.join(stale)}",
                )
                continue

            for w in tx.write_set:
                self.state.apply(tx.channel, w.key, w.value)
            channel.validation[tx.tx_id] = ValidationResult(tx.tx_id, True, "VALID")

        channel._append(block)
        self.state.commit()
        return block

    # -- convenience ------------------------------------------------------
    def invoke(
        self,
        channel: str,
        chaincode: str,
        function: str,
        args: dict[str, Any],
        submitter: Identity,
        endorsers: list[Identity],
        timestamp: str,
    ) -> tuple[Block | None, ValidationResult, Any]:
        """Propose, submit and commit in one call. Returns (block, result, response)."""
        tx = self.propose(channel, chaincode, function, args, submitter, endorsers, timestamp)
        ok, why = self.submit(tx)
        if not ok:
            return None, ValidationResult(tx.tx_id, False, "ORDERING_FAILURE", why), None
        block = self.commit(timestamp)
        result = self.channels[channel].validation[tx.tx_id]
        return block, result, tx.response

    def query(
        self, channel: str, chaincode: str, function: str, args: dict[str, Any], caller: Identity
    ) -> Any:
        """Read-only. Simulated and discarded; nothing is ordered or committed."""
        _, response = self.simulate(channel, chaincode, function, args, caller)
        return response
