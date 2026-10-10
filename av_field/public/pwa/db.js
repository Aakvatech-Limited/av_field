const request = req => new Promise((resolve, reject) => {
  req.onsuccess = () => resolve(req.result);
  req.onerror = () => reject(req.error);
});
export async function openStore(user) {
  const req = indexedDB.open(`av-field-v1:${user}`, 1);
  req.onupgradeneeded = () => {
    req.result.createObjectStore('operations', {keyPath: 'id'});
    req.result.createObjectStore('meta');
  };
  const db = await request(req);
  const transact = async (stores, mode, callback) => {
    const tx = db.transaction(stores, mode);
    const done = new Promise((resolve, reject) => {
      tx.oncomplete = resolve;
      tx.onerror = () => reject(tx.error);
      tx.onabort = () => reject(tx.error || new Error('Local save was aborted'));
    });
    let result;
    try { result = await callback(tx); } catch (error) { tx.abort(); await done.catch(() => {}); throw error; }
    await done;
    return result;
  };
  return {
    user,
    list: () => transact(['operations'], 'readonly', tx => request(tx.objectStore('operations').getAll())),
    save: operation => transact(['operations'], 'readwrite', tx => request(tx.objectStore('operations').put(operation))),
    remove: id => transact(['operations'], 'readwrite', tx => request(tx.objectStore('operations').delete(id))),
    getMeta: key => transact(['meta'], 'readonly', tx => request(tx.objectStore('meta').get(key))),
    setMeta: (key, value) => transact(['meta'], 'readwrite', tx => request(tx.objectStore('meta').put(value, key))),
    replaceReferences: snapshot => transact(['meta'], 'readwrite', tx => request(tx.objectStore('meta').put(snapshot, 'references'))),
    close: () => db.close(),
    clear: () => transact(['operations', 'meta'], 'readwrite', tx => {
      tx.objectStore('operations').clear(); tx.objectStore('meta').clear();
    })
  };
}
