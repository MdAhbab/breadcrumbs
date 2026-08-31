/*
 * fedmodel — the Continuity Gate, as real Hyperledger Fabric chaincode.
 *
 * This is a port of model/chaincode/fedmodel.py. The two must stay in step; the
 * Python one is the reference and is the one covered by tests.
 *
 * Fabric-specific constraints that shape this file:
 *
 *   Determinism. Every endorsing peer executes this and the read/write sets must
 *   match byte for byte, or the transaction fails validation with
 *   ENDORSEMENT_POLICY_FAILURE. So: no Date.now(), no Math.random(), no floating
 *   point arithmetic anywhere. All accuracies are integers in basis points, and
 *   every timestamp arrives as an argument from the client.
 *
 *   Deterministic serialisation. JSON.stringify does not sort keys, and two
 *   peers building an object in different orders would write different bytes.
 *   Everything written to state goes through stableStringify below.
 *
 *   The contract never sees model weights. They are deliberately off-chain. It
 *   compares accuracies that endorsing organisations measured themselves and
 *   signed, which is why the guarantee is "a threshold of independent
 *   organisations evaluated the same committed benchmark and signed compatible
 *   results" rather than "computed on-chain".
 */

'use strict';

const { Contract } = require('fabric-contract-api');
const crypto = require('crypto');

const BENCH = 'benchmark:';
const MODEL = 'model:';
const ROUND = 'round:';
const DECISION = 'decision:';
const CURRENT = 'current_model';

const TAG_BENCH = 'breadcrumbs:benchmark:v1';

/** Sorted-key JSON, so every peer produces identical bytes. */
function stableStringify(value) {
    if (value === null || typeof value !== 'object') return JSON.stringify(value);
    if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
    const keys = Object.keys(value).sort();
    return `{${keys.map((k) => `${JSON.stringify(k)}:${stableStringify(value[k])}`).join(',')}}`;
}

/** Length-prefixed, domain-separated SHA-256, matching ledger/crypto.py. */
function taggedHash(tag, payload) {
    const body = Buffer.from(stableStringify(payload), 'utf8');
    const length = Buffer.alloc(8);
    length.writeBigUInt64BE(BigInt(body.length));
    return crypto
        .createHash('sha256')
        .update(Buffer.from(tag, 'utf8'))
        .update(length)
        .update(body)
        .digest('hex');
}

/** Median of integers. Even counts floor the average — never a float. */
function medianBp(values) {
    const s = [...values].sort((a, b) => a - b);
    const mid = Math.floor(s.length / 2);
    if (s.length % 2 === 1) return s[mid];
    return Math.floor((s[mid - 1] + s[mid]) / 2);
}

/*
 * Verify a submission against the public key inside its certificate.
 *
 * The certificate must come first and the key must be taken out of it. Checking
 * the signature against a key the submission itself supplied would prove only
 * that somebody holds some private key — one actor could generate three
 * keypairs, label them with three organisations, and promote any model it liked.
 *
 * On Fabric the certificate is additionally checked against the channel MSP by
 * the peer before chaincode runs, and `ctx.clientIdentity` exposes the validated
 * caller. This function covers the submissions carried *inside* the transaction,
 * which the peer does not validate for us.
 */
function verifySubmission(sub, payload) {
    try {
        if (!sub.certificate_pem) return false;
        const cert = new crypto.X509Certificate(sub.certificate_pem);

        // The certificate must name the organisation it claims to speak for.
        const ou = /OU=([^,\n/]+)/.exec(cert.subject);
        if (!ou || ou[1].trim() !== sub.endorser_msp) return false;

        const now = new Date();
        if (new Date(cert.validTo) < now || new Date(cert.validFrom) > now) return false;

        return crypto.verify(
            null,
            Buffer.from(stableStringify(payload), 'utf8'),
            cert.publicKey,
            Buffer.from(sub.signature, 'hex'),
        );
    } catch (err) {
        return false;
    }
}

class FedModel extends Contract {
    async _get(ctx, key) {
        const raw = await ctx.stub.getState(key);
        return raw && raw.length ? JSON.parse(raw.toString()) : null;
    }

    async _put(ctx, key, value) {
        await ctx.stub.putState(key, Buffer.from(stableStringify(value)));
    }

    // -- benchmarks -------------------------------------------------------
    async commitBenchmark(ctx, taskId, benchmarkHash, contributorsJson, size, timestamp) {
        if (await this._get(ctx, BENCH + taskId)) {
            throw new Error(`benchmark for ${taskId} already committed`);
        }
        if (benchmarkHash.length !== 64) throw new Error('benchmark_hash must be 64 chars');

        const entry = {
            task_id: taskId,
            benchmark_hash: benchmarkHash,
            committed_at: timestamp,
            committed_by: ctx.clientIdentity.getMSPID(),
            contributors: JSON.parse(contributorsJson).sort(),
            size: parseInt(size, 10),
            revealed: false,
            revealed_at: null,
        };
        await this._put(ctx, BENCH + taskId, entry);
        return stableStringify({ task_id: taskId, sealed: true });
    }

    async revealBenchmark(ctx, taskId, contentsJson, timestamp) {
        const entry = await this._get(ctx, BENCH + taskId);
        if (!entry) throw new Error(`unknown benchmark ${taskId}`);
        if (entry.revealed) throw new Error('benchmark already revealed');

        const recomputed = taggedHash(TAG_BENCH, JSON.parse(contentsJson));
        if (recomputed !== entry.benchmark_hash) {
            throw new Error(
                `revealed contents hash to ${recomputed.slice(0, 12)}, ` +
                `but ${entry.benchmark_hash.slice(0, 12)} was committed`,
            );
        }
        entry.revealed = true;
        entry.revealed_at = timestamp;
        await this._put(ctx, BENCH + taskId, entry);
        return stableStringify({ task_id: taskId, revealed: true, verified: true });
    }

    async openRound(ctx, roundId, tasksJson, contributorsJson, memoryBankHash, timestamp) {
        if (await this._get(ctx, ROUND + roundId)) throw new Error(`round ${roundId} exists`);
        const tasks = JSON.parse(tasksJson);
        for (const taskId of tasks) {
            if (!(await this._get(ctx, BENCH + taskId))) {
                throw new Error(`no benchmark committed for task ${taskId}`);
            }
        }
        const entry = {
            round_id: roundId,
            tasks,
            opened_at: timestamp,
            opened_by: ctx.clientIdentity.getMSPID(),
            contributors: JSON.parse(contributorsJson).sort(),
            memory_bank_hash: memoryBankHash,
            status: 'open',
        };
        await this._put(ctx, ROUND + roundId, entry);
        return stableStringify({ round_id: roundId, status: 'open' });
    }

    // -- the gate ---------------------------------------------------------
    async evaluateGate(ctx, argsJson) {
        const args = JSON.parse(argsJson);
        const round = await this._get(ctx, ROUND + args.round_id);
        if (!round) throw new Error(`unknown round ${args.round_id}`);
        if (round.status !== 'open') throw new Error(`round is ${round.status}`);

        const tasks = round.tasks;
        const newTask = args.new_task;
        if (!tasks.includes(newTask)) throw new Error(`${newTask} is not a task in this round`);

        const gamma = parseInt(args.gamma_bp, 10);
        const tau = parseInt(args.tau_bp, 10);
        const k = parseInt(args.k, 10);
        const delta = parseInt(args.delta_bp, 10);

        for (const taskId of tasks) {
            if (!(await this._get(ctx, BENCH + taskId))) {
                throw new Error(`no benchmark committed for ${taskId}`);
            }
        }

        // Step 2: accept only verified signatures, one vote per organisation.
        const accepted = {};
        const rejected = [];
        for (const sub of args.submissions) {
            const mspId = sub.endorser_msp;
            if (accepted[mspId]) {
                rejected.push({ endorser_msp: mspId, reason: 'duplicate submission' });
                continue;
            }
            const payload = {
                round_id: args.round_id,
                candidate_id: args.candidate_id,
                candidate_hash: args.candidate_hash,
                accuracies: sub.accuracies,
            };
            if (!verifySubmission(sub, payload)) {
                rejected.push({ endorser_msp: mspId, reason: 'certificate or signature did not validate' });
                continue;
            }
            const missing = tasks.filter((t) => !(t in sub.accuracies));
            if (missing.length) {
                rejected.push({ endorser_msp: mspId, reason: `did not evaluate ${missing.join(', ')}` });
                continue;
            }
            accepted[mspId] = sub.accuracies;
        }

        const endorsers = Object.keys(accepted).sort();
        const decision = {
            round_id: args.round_id,
            candidate_id: args.candidate_id,
            candidate_hash: args.candidate_hash,
            parent_id: args.parent_id,
            memory_bank_hash: round.memory_bank_hash,
            contributors: round.contributors,
            endorsers,
            rejected_submissions: rejected,
            parameters: { gamma_bp: gamma, tau_bp: tau, k, delta_bp: delta },
            decided_at: args.timestamp,
            per_task: [],
        };

        // Step 3: enough independent organisations?
        if (endorsers.length < k) {
            decision.outcome = 'reject';
            decision.reason_code = 'INSUFFICIENT_ENDORSEMENTS';
            decision.reason = `${endorsers.length} organisations submitted valid results, ${k} required`;
            return this._finalise(ctx, decision, false);
        }

        // Step 4: do they agree?
        for (const taskId of tasks) {
            const cand = endorsers.map((m) => accepted[m][taskId].candidate_bp);
            const prev = endorsers.map((m) => accepted[m][taskId].previous_bp);
            const spread = Math.max(
                Math.max(...cand) - Math.min(...cand),
                Math.max(...prev) - Math.min(...prev),
            );
            if (spread > delta) {
                decision.outcome = 'reject';
                decision.reason_code = 'NO_AGREEMENT';
                decision.reason = `endorsers disagree on ${taskId} by ${spread} bp, tolerance is ${delta} bp`;
                return this._finalise(ctx, decision, false);
            }
        }

        // Step 5: medians.
        const medians = {};
        for (const taskId of tasks) {
            medians[taskId] = {
                candidate_bp: medianBp(endorsers.map((m) => accepted[m][taskId].candidate_bp)),
                previous_bp: medianBp(endorsers.map((m) => accepted[m][taskId].previous_bp)),
            };
        }

        for (const taskId of tasks) {
            const bench = await this._get(ctx, BENCH + taskId);
            const c = medians[taskId].candidate_bp;
            const p = medians[taskId].previous_bp;
            const isNew = taskId === newTask;
            decision.per_task.push({
                task_id: taskId,
                benchmark_hash: bench.benchmark_hash,
                candidate_bp: c,
                previous_bp: p,
                change_bp: c - p,
                is_new_task: isNew,
                threshold_bp: isNew ? gamma : -tau,
                pass: isNew ? c - p >= gamma : p - c <= tau,
            });
        }

        // Step 6: real improvement on the new task?
        const gain = medians[newTask].candidate_bp - medians[newTask].previous_bp;
        if (gain < gamma) {
            decision.outcome = 'reject';
            decision.reason_code = 'NO_IMPROVEMENT';
            decision.reason = `gain on ${newTask} is ${gain} bp, at least ${gamma} bp required`;
            return this._finalise(ctx, decision, false);
        }

        // Step 7: has it forgotten anything?
        for (const taskId of tasks.filter((t) => t !== newTask)) {
            const loss = medians[taskId].previous_bp - medians[taskId].candidate_bp;
            if (loss > tau) {
                decision.outcome = 'reject';
                decision.reason_code = 'REGRESSION';
                decision.reason = `accuracy on ${taskId} fell by ${loss} bp, tolerance is ${tau} bp`;
                return this._finalise(ctx, decision, false);
            }
        }

        decision.outcome = 'promote';
        decision.reason_code = 'OK';
        decision.reason = `gained ${gain} bp on ${newTask} and lost no more than ${tau} bp on any earlier task`;
        return this._finalise(ctx, decision, true);
    }

    async _finalise(ctx, decision, promote) {
        await this._put(ctx, DECISION + decision.candidate_id, decision);

        const model = {
            model_id: decision.candidate_id,
            model_hash: decision.candidate_hash,
            parent_id: decision.parent_id,
            round_id: decision.round_id,
            memory_bank_hash: decision.memory_bank_hash,
            contributors: decision.contributors,
            endorsers: decision.endorsers,
            status: promote ? 'promoted' : 'rejected',
            outcome_reason: decision.reason,
            per_task: decision.per_task,
            decided_at: decision.decided_at,
        };
        await this._put(ctx, MODEL + decision.candidate_id, model);

        if (promote) {
            const previous = await this._get(ctx, CURRENT);
            if (previous) {
                const superseded = await this._get(ctx, MODEL + previous);
                if (superseded) {
                    superseded.status = 'superseded';
                    await this._put(ctx, MODEL + previous, superseded);
                }
            }
            await this._put(ctx, CURRENT, decision.candidate_id);
        }

        const round = await this._get(ctx, ROUND + decision.round_id);
        round.status = 'decided';
        round.decision = decision.outcome;
        await this._put(ctx, ROUND + decision.round_id, round);

        // A rejection is recorded as permanently as a promotion. Any member can
        // later ask what was submitted, who evaluated it, and why it was refused.
        ctx.stub.setEvent('GateDecision', Buffer.from(stableStringify(decision)));
        return stableStringify(decision);
    }

    // -- read-only --------------------------------------------------------
    async getCurrentModel(ctx) {
        const current = await this._get(ctx, CURRENT);
        return stableStringify(current ? await this._get(ctx, MODEL + current) : null);
    }

    async getDecision(ctx, candidateId) {
        return stableStringify(await this._get(ctx, DECISION + candidateId));
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

    async listModels(ctx) { return this.listByPrefix(ctx, MODEL); }
    async listBenchmarks(ctx) { return this.listByPrefix(ctx, BENCH); }
    async listRounds(ctx) { return this.listByPrefix(ctx, ROUND); }
}

module.exports = FedModel;
module.exports.contracts = [FedModel];
