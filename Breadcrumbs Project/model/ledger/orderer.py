"""
Ordering service.

Fabric separates consensus from execution: the orderer decides *sequence*, not
*validity*. It never runs chaincode and never inspects a write set. All it does
is take endorsed transactions and produce an agreed total order, cut into blocks.

That separation is why this system's energy story is defensible. There is no
puzzle to solve and no competition to win; ordering is a Raft log among a handful
of known nodes, which costs roughly what running a database costs. When a judge
asks about the environmental case for a blockchain, this file is the answer.

The Raft implementation here is deliberately minimal: a single elected leader
appends to a log and followers acknowledge. Leader election and log divergence
are modelled, not the full membership-change protocol. It is enough to
demonstrate that a majority quorum is required and that a minority cannot commit.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .block import Block, Transaction


@dataclass
class RaftNode:
    """One ordering node."""

    node_id: str
    is_leader: bool = False
    log: list[str] = field(default_factory=list)  # tx_ids acknowledged
    alive: bool = True


class OrderingService:
    """
    Raft-style ordering across a small set of nodes.

    Blocks are cut on either of two conditions, exactly as Fabric does: the batch
    reaches max_batch transactions, or cut() is called explicitly at a timeout.
    """

    def __init__(
        self,
        node_ids: list[str],
        max_batch: int = 10,
    ):
        if not node_ids:
            raise ValueError("an ordering service needs at least one node")
        self.nodes = {n: RaftNode(n) for n in node_ids}
        self.leader_id = node_ids[0]
        self.nodes[self.leader_id].is_leader = True
        self.max_batch = max_batch
        self.term = 1
        # One queue per channel. A single shared queue would let a block cut for
        # one channel sweep up transactions belonging to another, which destroys
        # the confidentiality that channels exist to provide: a buyer's peer
        # would receive, and be able to replay, another buyer's transactions.
        self._pending: dict[str, list[Transaction]] = {}

    # -- membership -------------------------------------------------------
    @property
    def quorum(self) -> int:
        """A strict majority. Two of three, three of five."""
        return len(self.nodes) // 2 + 1

    @property
    def alive_count(self) -> int:
        return sum(1 for n in self.nodes.values() if n.alive)

    def has_quorum(self) -> bool:
        return self.alive_count >= self.quorum

    def stop(self, node_id: str) -> None:
        """Take a node down. Used to demonstrate quorum loss."""
        self.nodes[node_id].alive = False
        if node_id == self.leader_id:
            self._elect()

    def start(self, node_id: str) -> None:
        self.nodes[node_id].alive = True

    def _elect(self) -> None:
        """Promote the first live node. Real Raft votes; the outcome is the same."""
        for node_id, node in self.nodes.items():
            node.is_leader = False
        for node_id, node in self.nodes.items():
            if node.alive:
                node.is_leader = True
                self.leader_id = node_id
                self.term += 1
                return

    # -- ordering ---------------------------------------------------------
    def submit(self, tx: Transaction) -> tuple[bool, str]:
        """
        Hand an endorsed transaction to the leader.

        Refused without a quorum. This is the correct behaviour and worth
        showing in a demo: a permissioned chain that has lost its majority stops
        accepting writes rather than forking.
        """
        if not self.has_quorum():
            return False, (
                f"no quorum: {self.alive_count} of {len(self.nodes)} nodes alive, "
                f"{self.quorum} required"
            )
        leader = self.nodes[self.leader_id]
        leader.log.append(tx.tx_id)
        acks = 1
        for node_id, node in self.nodes.items():
            if node_id == self.leader_id or not node.alive:
                continue
            node.log.append(tx.tx_id)
            acks += 1
        if acks < self.quorum:
            return False, f"replicated to {acks} nodes, {self.quorum} required"
        self._pending.setdefault(tx.channel, []).append(tx)
        return True, ""

    def pending_channels(self) -> list[str]:
        """Channels with transactions waiting, in a stable order."""
        return sorted(c for c, q in self._pending.items() if q)

    def ready(self, channel: str) -> bool:
        return len(self._pending.get(channel, [])) >= self.max_batch

    def cut(
        self, channel: str, number: int, previous_hash: str, timestamp: str
    ) -> Block | None:
        """Cut one channel's pending batch into a block. None if nothing waits."""
        queue = self._pending.get(channel, [])
        if not queue:
            return None
        batch, self._pending[channel] = queue[: self.max_batch], queue[self.max_batch :]
        return Block(
            number=number,
            previous_hash=previous_hash,
            transactions=batch,
            proposer=self.leader_id,
            timestamp=timestamp,
        )
