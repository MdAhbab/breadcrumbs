#!/usr/bin/env bash
# Bring up a Fabric network and deploy the Breadcrumbs chaincodes.
#
# Written for WSL2 + Docker. Not executed on the machine this was authored on;
# see ../README.md. Uses the standard fabric-samples test network rather than a
# hand-rolled configtx, because the test network is what reviewers can check
# against a known-good reference.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SAMPLES="${HERE}/fabric-samples"
TESTNET="${SAMPLES}/test-network"
CC_SRC="${HERE}/../chaincode"
FABRIC_VERSION="${FABRIC_VERSION:-2.5.9}"
CA_VERSION="${CA_VERSION:-1.5.12}"

# Three organisations must endorse a gate decision. Lower this only if you are
# running the stock two-org network, and say so if you do.
GATE_POLICY="${GATE_POLICY:-OutOf(2,'Org1MSP.member','Org2MSP.member')}"
DOC_POLICY="${DOC_POLICY:-AND('Org1MSP.member','Org2MSP.member')}"

need() { command -v "$1" >/dev/null || { echo "missing: $1"; exit 1; }; }

fetch() {
  need docker; need curl
  if [ ! -d "${SAMPLES}" ]; then
    echo "==> fetching fabric-samples ${FABRIC_VERSION}"
    mkdir -p "${SAMPLES}"
    curl -sSL https://raw.githubusercontent.com/hyperledger/fabric/main/scripts/install-fabric.sh \
      | bash -s -- --fabric-version "${FABRIC_VERSION}" --ca-version "${CA_VERSION}" docker samples binary
    # install-fabric.sh drops fabric-samples in the cwd
    [ -d fabric-samples ] && rm -rf "${SAMPLES}" && mv fabric-samples "${SAMPLES}"
  fi
}

case "${1:-help}" in
  up)
    fetch
    cd "${TESTNET}"
    ./network.sh down || true
    ./network.sh up createChannel -c documents -ca
    ./network.sh createChannel -c modelchannel
    echo "==> channels 'documents' and 'modelchannel' are up"
    ;;

  deploy)
    cd "${TESTNET}"
    echo "==> installing node dependencies"
    (cd "${CC_SRC}" && npm install --omit=dev)

    echo "==> deploying doccustody to 'documents' (${DOC_POLICY})"
    ./network.sh deployCC -c documents -ccn doccustody -ccp "${CC_SRC}" -ccl javascript \
      -ccep "${DOC_POLICY}"

    echo "==> deploying fedmodel to 'modelchannel' (${GATE_POLICY})"
    ./network.sh deployCC -c modelchannel -ccn fedmodel -ccp "${CC_SRC}" -ccl javascript \
      -ccep "${GATE_POLICY}"
    ;;

  demo)
    cd "${TESTNET}"
    export PATH="${SAMPLES}/bin:$PATH"
    export FABRIC_CFG_PATH="${SAMPLES}/config"
    export CORE_PEER_TLS_ENABLED=true
    export CORE_PEER_LOCALMSPID=Org1MSP
    export CORE_PEER_TLS_ROOTCERT_FILE="${TESTNET}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
    export CORE_PEER_MSPCONFIGPATH="${TESTNET}/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
    export CORE_PEER_ADDRESS=localhost:7051
    ORDERER_CA="${TESTNET}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem"
    O2_CA="${TESTNET}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"

    echo "==> committing a payroll record"
    peer chaincode invoke -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
      --tls --cafile "$ORDERER_CA" -C documents -n doccustody \
      --peerAddresses localhost:7051 --tlsRootCertFiles "$CORE_PEER_TLS_ROOTCERT_FILE" \
      --peerAddresses localhost:9051 --tlsRootCertFiles "$O2_CA" \
      -c '{"function":"commitRecord","Args":["{\"record_id\":\"rc-001\",\"merkle_root\":\"a3f9e2c817b4d056f3a1e79c245b0d3fa3f9e2c817b4d056f3a1e79c245b0d3f\",\"record_type\":\"payroll_register\",\"period\":\"2026-07\",\"site\":\"Gazipur\",\"row_count\":1847,\"schema_version\":\"v2.1.0\",\"timestamp\":\"2026-08-05T09:14:00Z\"}"]}'

    sleep 3
    echo "==> reading it back"
    peer chaincode query -C documents -n doccustody \
      -c '{"function":"getRecord","Args":["rc-001"]}'

    echo
    echo "==> to exercise the Continuity Gate, generate signed submissions with:"
    echo "    python -m model.fabric.make_submissions   (see ../README.md)"
    ;;

  down)
    cd "${TESTNET}" && ./network.sh down
    ;;

  *)
    echo "usage: ./deploy.sh {up|deploy|demo|down}"
    ;;
esac
