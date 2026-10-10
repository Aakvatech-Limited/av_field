import test from 'node:test';
import assert from 'node:assert/strict';
import {ApiError, drain, downloadReferences, wire} from '../av_field/public/pwa/sync.js';
const record = (id = 'one') => ({id, version: 1, kind: 'visit', payload: {customer: 'C1'}, recorded_at: '2026-10-10T11:00:00Z', status: 'pending'});
function memory(records) { const rows = new Map(records.map(r => [r.id, {...r}])); return {list: async () => [...rows.values()], save: async r => rows.set(r.id, r), rows}; }
test('lost acknowledgement retries the exact operation ID', async () => {
  const store = memory([record()]); let calls = [];
  await assert.rejects(drain(store, async op => { calls.push(op); throw new TypeError('Network lost'); }, () => 100));
  assert.equal(store.rows.get('one').status, 'pending');
  await drain(store, async op => { calls.push(op); return {id: op.id, name: 'FIELD-1', duplicate: true}; }, () => 100000);
  assert.equal(calls[0].id, calls[1].id); assert.equal(store.rows.get('one').status, 'synced');
});
test('validation rejection does not block the next record', async () => {
  const store = memory([record('bad'), record('good')]);
  await drain(store, async op => { if (op.id === 'bad') throw new ApiError('Disabled customer', 417); return {id: op.id, name: 'FIELD-2'}; });
  assert.equal(store.rows.get('bad').status, 'rejected'); assert.equal(store.rows.get('good').status, 'synced');
});
test('authentication expiry pauses queue without discarding records', async () => {
  const store = memory([record(), record('two')]);
  await assert.rejects(drain(store, async () => {throw new ApiError('Login required', 403)}));
  assert.deepEqual((await store.list()).map(r => r.status), ['pending', 'pending']);
});
test('retry backoff is respected and server 429 is transient', async () => {
  const store = memory([{...record(), nextAttemptAt: 1000}]); let calls = 0;
  await drain(store, async () => calls++, () => 900); assert.equal(calls, 0);
  await assert.rejects(drain(store, async () => {throw new ApiError('Rate limit', 429)}, () => 1000));
  assert.equal(store.rows.get('one').status, 'pending'); assert.ok(store.rows.get('one').nextAttemptAt > 1000);
});
test('mismatched acknowledgement never marks a record synced', async () => {
  const store = memory([record()]); await assert.rejects(drain(store, async () => ({id:'other',name:'FIELD-2'})));
  assert.equal(store.rows.get('one').status, 'pending');
});
test('only wire contract fields leave device', () => { assert.deepEqual(Object.keys(wire({...record(), error:'local', attempts:2})).sort(), ['id','kind','payload','recorded_at','version']); });
test('complete replacement snapshot follows every permission-filtered page', async () => {
  const snapshot = await downloadReferences(async (kind, after) => kind === 'customers' ? after ? {rows:[{name:'C2'}],after:null} : {rows:[{name:'C1'}],after:'C1'} : {rows:[{name:'I1'}],after:null});
  assert.deepEqual(snapshot.customers.map(r=>r.name), ['C1','C2']);
});
test('partial master-data download cannot return an incomplete snapshot', async () => { await assert.rejects(downloadReferences(async kind => {if(kind === 'items') throw new Error('offline'); return {rows:[],after:null}})); });
test('broken pagination fails rather than looping forever', async () => { await assert.rejects(downloadReferences(async () => ({rows:[{name:'C1'}],after:'C1'})), /did not advance/); });
