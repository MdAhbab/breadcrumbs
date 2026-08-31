/*
 * doccustody — document commitments, access grants and verification receipts.
 * Port of model/chaincode/doccustody.py. The Python version is the reference.
 *
 * Nothing here stores a document, a row, a name or a wage. Only root hashes and
 * metadata, because an append-only ledger and a deletion right cannot both hold
 * for personal data.
 */

'use strict';

const { Contract } = require('fabric-contract-api');

const RECORD = 'record:';
const GRANT = 'grant:';
const RECEIPT = 'receipt:';

const VALID_TYPES = new Set([
    'payroll_register', 'safety_inspection', 'chemical_inventory',
    'machine_maintenance', 'compliance_certificate',
]);

function stableStringify(value) {
    if (value === null || typeof value !== 'object') return JSON.stringify(value);
    if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
    const keys = Object.keys(value).sort();
    return `{${keys.map((k) => `${JSON.stringify(k)}:${stableStringify(value[k])}`).join(',')}}`;
}

class DocCustody extends Contract {
    async _get(ctx, key) {
        const raw = await ctx.stub.getState(key);
        return raw && raw.length ? JSON.parse(raw.toString()) : null;
    }

    async _put(ctx, key, value) {
        await ctx.stub.putState(key, Buffer.from(stableStringify(value)));
    }

    async commitRecord(ctx, argsJson) {
        const a = JSON.parse(argsJson);
        const msp = ctx.clientIdentity.getMSPID();
        if (await this._get(ctx, RECORD + a.record_id)) {
            throw new Error(`${a.record_id} already committed`);
        }
        if (!VALID_TYPES.has(a.record_type)) throw new Error(`unknown record type ${a.record_type}`);
        if (a.merkle_root.length !== 64) throw new Error('merkle_root must be a 64-character hash');
        if (parseInt(a.row_count, 10) <= 0) throw new Error('a record must have at least one row');

        const record = {
            record_id: a.record_id,
            owner_msp: msp,
            merkle_root: a.merkle_root,
            record_type: a.record_type,
            period: a.period,
            site: a.site,
            row_count: parseInt(a.row_count, 10),
            schema_version: a.schema_version,
            committed_at: a.timestamp,
            committed_by: ctx.clientIdentity.getID(),
            status: 'committed',
            superseded_by: null,
        };
        await this._put(ctx, RECORD + a.record_id, record);
        ctx.stub.setEvent('RecordCommitted', Buffer.from(stableStringify(record)));
        return stableStringify({ record_id: a.record_id, status: 'committed' });
    }

    async grantAccess(ctx, argsJson) {
        const a = JSON.parse(argsJson);
        const record = await this._get(ctx, RECORD + a.record_id);
        if (!record) throw new Error(`unknown record ${a.record_id}`);
        if (record.owner_msp !== ctx.clientIdentity.getMSPID()) {
            throw new Error(`${ctx.clientIdentity.getMSPID()} does not own ${a.record_id}`);
        }
        if (await this._get(ctx, GRANT + a.grant_id)) throw new Error(`${a.grant_id} already exists`);
        if (!a.field_name) throw new Error('a grant must name exactly one field');

        const grant = {
            grant_id: a.grant_id,
            record_id: a.record_id,
            owner_msp: record.owner_msp,
            requester_msp: a.requester_msp,
            purpose_code: a.purpose_code,
            field_name: a.field_name,
            granted_at: a.timestamp,
            expires_at: a.expires_at,
            status: 'active',
            revoked_reason: null,
        };
        await this._put(ctx, GRANT + a.grant_id, grant);
        return stableStringify({ grant_id: a.grant_id, status: 'active' });
    }

    async revokeAccess(ctx, grantId, reason, timestamp) {
        const grant = await this._get(ctx, GRANT + grantId);
        if (!grant) throw new Error(`unknown grant ${grantId}`);
        if (grant.owner_msp !== ctx.clientIdentity.getMSPID()) {
            throw new Error('only the record owner may revoke a grant');
        }
        if (grant.status !== 'active') throw new Error(`grant is already ${grant.status}`);
        grant.status = 'revoked';
        grant.revoked_reason = reason;
        grant.revoked_at = timestamp;
        grant.revoked_by = ctx.clientIdentity.getID();
        await this._put(ctx, GRANT + grantId, grant);
        return stableStringify({ grant_id: grantId, status: 'revoked' });
    }

    async recordVerification(ctx, argsJson) {
        const a = JSON.parse(argsJson);
        const grant = await this._get(ctx, GRANT + a.grant_id);
        if (!grant) throw new Error(`unknown grant ${a.grant_id}`);
        if (grant.requester_msp !== ctx.clientIdentity.getMSPID()) {
            throw new Error(`grant ${a.grant_id} does not belong to the caller`);
        }
        if (grant.status !== 'active') throw new Error(`grant is ${grant.status}`);
        if (grant.field_name !== a.field_name) {
            throw new Error(`grant covers ${grant.field_name}, not ${a.field_name}`);
        }
        if (a.timestamp > grant.expires_at) throw new Error(`grant expired on ${grant.expires_at}`);

        const receipt = {
            receipt_id: a.receipt_id,
            grant_id: a.grant_id,
            record_id: grant.record_id,
            verifier_msp: grant.requester_msp,
            field_name: a.field_name,
            result: a.result,
            computed_root: a.computed_root,
            verified_at: a.timestamp,
        };
        await this._put(ctx, RECEIPT + a.receipt_id, receipt);
        return stableStringify(receipt);
    }

    async getRecord(ctx, recordId) {
        return stableStringify(await this._get(ctx, RECORD + recordId));
    }

    async listByPrefix(ctx, prefix) {
        const out = [];
        const iterator = await ctx.stub.getStateByRange(prefix, prefix + '￿');
        for (let res = await iterator.next(); !res.done; res = await iterator.next()) {
            out.push(JSON.parse(res.value.value.toString()));
        }
        await iterator.close();
        return stableStringify(out);
    }

    async listRecords(ctx) { return this.listByPrefix(ctx, RECORD); }
    async listGrants(ctx) { return this.listByPrefix(ctx, GRANT); }
    async listReceipts(ctx) { return this.listByPrefix(ctx, RECEIPT); }
}

module.exports = DocCustody;
module.exports.contracts = [DocCustody];
