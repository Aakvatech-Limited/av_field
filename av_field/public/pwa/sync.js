export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}
export function wire(operation) {
  const {version, id, kind, recorded_at, payload} = operation;
  return {version, id, kind, recorded_at, payload};
}
export async function drain(store, push, now = Date.now) {
  const operations = (await store.list()).filter(op => op.status === 'pending' && (!op.nextAttemptAt || op.nextAttemptAt <= now()));
  operations.sort((a, b) => a.recorded_at.localeCompare(b.recorded_at));
  for (const operation of operations) {
    try {
      const ack = await push(wire(operation));
      if (!ack || ack.id !== operation.id || !ack.name) throw new ApiError('Server acknowledgement did not match the record', 503);
      await store.save({...operation, status: 'synced', ack, error: null, nextAttemptAt: null});
    } catch (error) {
      // Authentication failures pause the queue without assigning validation failures.
      if (error.status === 401 || error.status === 403) throw error;
      const temporary = !error.status || error.status >= 500 || [408, 429].includes(error.status);
      const attempts = (operation.attempts || 0) + 1;
      await store.save({...operation, status: temporary ? 'pending' : 'rejected', attempts,
        error: error.message, nextAttemptAt: temporary ? now() + Math.min(300000, 1000 * 2 ** Math.min(attempts, 8)) : null});
      if (temporary) throw error;
    }
  }
}
export async function downloadReferences(fetchPage) {
  const snapshot = {customers: [], items: [], downloadedAt: new Date().toISOString()};
  for (const kind of ['customers', 'items']) {
    let after = '';
    const cursors = new Set();
    do {
      const page = await fetchPage(kind, after);
      if (!Array.isArray(page.rows)) throw new Error('Invalid master-data response');
      snapshot[kind].push(...page.rows);
      after = page.after;
      if (after && cursors.has(after)) throw new Error('Master-data pagination did not advance');
      if (after) cursors.add(after);
      if (cursors.size > 1000) throw new Error('Master-data download is too large; narrow User Permissions');
    } while (after);
  }
  return snapshot;
}
