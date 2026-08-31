"""
The Breadcrumbs consortium, assembled.

Building the network is fiddly and every demo, test and API call needs the same
one, so it lives here once. The membership matches the report and the frontend
designs exactly: three factories, one buyer, one auditor, the industry body and
the regulator.

Two channels, because confidentiality is structural rather than a permission
flag. A document channel is shared by one factory and one buyer, so a second
buyer holds no copy of that data at all. The model channel is shared by everyone,
because a promoted model version is a consortium-wide fact.

Endorsement policies are the important part of this file. Note in particular that
fedmodel requires three organisations including the consortium: no single
participant, and no pair of factories, can promote a model.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .chaincode import doccustody, fedmodel, reputation
from .ledger import (
    AND,
    MSP,
    CertificateAuthority,
    Identity,
    Network,
    NOutOf,
    OrderingService,
    WorldState,
)

DOCUMENT_CHANNEL = "documents-apex-primark"
MODEL_CHANNEL = "model-channel"

ORGS: list[tuple[str, str, str, str]] = [
    # msp_id,                 legal name,                     kind,         country
    ("ApexTextileMSP", "Apex Textile Ltd", "factory", "BD"),
    ("NoorGarmentsMSP", "Noor Garments Ltd", "factory", "BD"),
    ("CrescentFashionMSP", "Crescent Fashion Ltd", "factory", "BD"),
    ("PrimarkSourcingMSP", "Primark Sourcing Ltd", "buyer", "IE"),
    ("BVCertificationMSP", "BV Certification", "auditor", "FR"),
    ("BGMEAConsortiumMSP", "BGMEA Consortium", "consortium", "BD"),
    ("DOLBangladeshMSP", "Dept. of Labour, Bangladesh", "regulator", "BD"),
]

# The people who appear in the interface.
MEMBERS: list[tuple[str, str, str]] = [
    ("ApexTextileMSP", "fatema.begum", "operator"),
    ("ApexTextileMSP", "apex.admin", "admin"),
    ("NoorGarmentsMSP", "noor.operator", "operator"),
    ("CrescentFashionMSP", "crescent.operator", "operator"),
    ("PrimarkSourcingMSP", "james.holloway", "operator"),
    ("BVCertificationMSP", "meera.nair", "operator"),
    ("BGMEAConsortiumMSP", "rafiqul.islam", "admin"),
    ("DOLBangladeshMSP", "aziz", "reader"),
]

FACTORIES = [o[0] for o in ORGS if o[2] == "factory"]
GATE_ORGS = FACTORIES + ["BVCertificationMSP", "BGMEAConsortiumMSP"]


@dataclass
class Consortium:
    """A fully wired network plus a directory of identities."""

    network: Network
    msp: MSP
    authorities: dict[str, CertificateAuthority]
    identities: dict[str, Identity] = field(default_factory=dict)

    def who(self, name: str) -> Identity:
        """Look up an identity by its common name, e.g. 'fatema.begum'."""
        return self.identities[name]

    def org_identity(self, msp_id: str) -> Identity:
        """The first identity belonging to an organisation. Used as an endorser."""
        for ident in self.identities.values():
            if ident.msp_id == msp_id:
                return ident
        raise KeyError(msp_id)

    def endorsers(self, msp_ids: list[str]) -> list[Identity]:
        return [self.org_identity(m) for m in msp_ids]


def build(db_path: str = ":memory:", timestamp: str = "2026-03-01T00:00:00Z") -> Consortium:
    """Stand up the whole consortium: CAs, identities, channels, chaincode."""
    msp = MSP()
    authorities: dict[str, CertificateAuthority] = {}
    for msp_id, name, kind, country in ORGS:
        ca = CertificateAuthority(msp_id, name, kind, country)  # type: ignore[arg-type]
        authorities[msp_id] = ca
        msp.register(ca)

    identities: dict[str, Identity] = {}
    for msp_id, common_name, role in MEMBERS:
        identities[common_name] = authorities[msp_id].issue(common_name, role)  # type: ignore[arg-type]

    # Five ordering nodes: a majority of three is needed to accept a write.
    orderer = OrderingService(
        ["orderer0.bgmea", "orderer1.bgmea", "orderer2.apex", "orderer3.noor", "orderer4.bv"],
        max_batch=1,
    )
    network = Network(msp, orderer, WorldState(db_path))

    network.create_channel(
        DOCUMENT_CHANNEL, ["ApexTextileMSP", "PrimarkSourcingMSP", "BVCertificationMSP"], timestamp
    )
    network.create_channel(MODEL_CHANNEL, [o[0] for o in ORGS], timestamp)

    # doccustody: the owning factory and one counterparty must both endorse, so a
    # factory cannot unilaterally rewrite what a buyer relies on.
    network.install(
        "doccustody",
        doccustody,
        AND("ApexTextileMSP", "BVCertificationMSP"),
        ["ApexTextileMSP", "BVCertificationMSP"],
    )

    # fedmodel: three of the five model-channel organisations. This is the policy
    # that makes "no single participant can promote a model" true.
    network.install("fedmodel", fedmodel, NOutOf(3, GATE_ORGS), GATE_ORGS)

    # reputation: the consortium writes, but a factory must co-sign, so BGMEA
    # cannot quietly downgrade a member on its own.
    network.install(
        "reputation",
        reputation,
        AND("BGMEAConsortiumMSP", "ApexTextileMSP"),
        ["BGMEAConsortiumMSP", "ApexTextileMSP"],
    )

    return Consortium(network=network, msp=msp, authorities=authorities, identities=identities)
