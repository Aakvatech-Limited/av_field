/* Route plans are cached for offline use. Outcome events enter the same durable outbox. */
const make = (tag, text, cls) => {
  const el = document.createElement(tag);
  if (text !== undefined) el.textContent = text;
  if (cls) el.className = cls;
  return el;
};
const format = (s) => s ? String(s).slice(0, 10) : '';
const statusChoices = ['Done', 'Skipped', 'Not Done', 'Postponed'];

export function routeUI({getStore, notify, sync}) {
  const root = document.querySelector('#route-list');
  let routes = [], outlets = [];
  async function load() {
    const store = getStore();
    if (!store) return;
    routes = (await store.getMeta('routes')) || [];
    outlets = (await store.getMeta('outlets')) || [];
    await render();
  }
  async function render() {
    if (!root) return;
    root.replaceChildren();
    const store = getStore();
    if (!store) return;
    const operations = (await store.list()).filter(x => x.kind === 'route_outcome' && x.status !== 'rejected');
    const staged = new Map(operations.map(x => [x.payload.stop, x]));
    const localOutlet = new Map(outlets.map(x => [x.name, x]));
    const current = routes.slice().sort((a, b) => a.route_date.localeCompare(b.route_date));
    if (!current.length) {
      root.append(make('p', 'No published route has been downloaded. Sync online after your manager publishes a plan.', 'hint'));
      return;
    }
    for (const plan of current) {
      const section = make('section', undefined, 'route-plan');
      section.append(make('h3', 'Route · ' + plan.route_date));
      if (plan.zone) section.append(make('p', 'Zone: ' + plan.zone, 'hint'));
      const stops = plan.stops.slice().sort((a,b) => a.sequence - b.sequence);
      const locations = stops.map(stop => localOutlet.get(stop.outlet))
        .filter(outlet => outlet && Number.isFinite(Number(outlet.latitude)) &&
          Number.isFinite(Number(outlet.longitude)) && outlet.latitude != null && outlet.longitude != null);
      if (locations.length >= 2) {
        // Google Maps URL waypoints have device-dependent limits; use consecutive
        // ordered groups, never silently drop a scheduled stop.
        for (let i = 0; i < locations.length - 1; i += 8) {
          const segment = locations.slice(i, Math.min(i + 9, locations.length));
          if (segment.length < 2) continue;
          const point = p => p.latitude + ',' + p.longitude;
          const params = new URLSearchParams({api: '1', origin: point(segment[0]),
            destination: point(segment[segment.length - 1]), travelmode: 'driving'});
          if (segment.length > 2) params.set('waypoints', segment.slice(1, -1).map(point).join('|'));
          const link = make('a', 'Open ordered directions ' + (Math.floor(i/8) + 1), 'secondary');
          link.href = 'https://www.google.com/maps/dir/?' + params;
          link.target = '_blank'; link.rel = 'noopener noreferrer';
          section.append(link);
        }
      }

      for (const stop of stops) {
        const outlet = localOutlet.get(stop.outlet) || {};
        const stagedEvent = staged.get(stop.name);
        const status = stagedEvent?.payload.outcome || stop.status || 'Pending';
        const article = make('article', undefined, 'activity route-stop');
        article.append(make('strong', stop.sequence + '. ' + (outlet.outlet_name || stop.outlet)));
        article.append(make('span', status + (stagedEvent?.status === 'pending' ? ' · awaiting sync' : ''), 'status'));
        article.append(make('p', [stop.customer, stop.planned_time, stop.purpose].filter(Boolean).join(' · ')));
        if (outlet.visit_instructions) article.append(make('p', outlet.visit_instructions, 'hint'));
        if (status !== 'Pending') {
          const detail = stagedEvent?.payload || stop;
          article.append(make('p', [detail.reason || detail.status_reason, detail.action_taken, detail.next_action].filter(Boolean).join(' · '), 'hint'));
        }
        if (outlet.latitude !== null && outlet.latitude !== undefined &&
            outlet.longitude !== null && outlet.longitude !== undefined) {
          const link = make('a', 'Navigate to outlet', 'secondary');
          link.href = 'https://www.google.com/maps/dir/?api=1&destination=' +
            encodeURIComponent(outlet.latitude + ',' + outlet.longitude);
          link.target = '_blank'; link.rel = 'noopener noreferrer';
          article.append(link);
        }
        if (status === 'Pending') {
          const button = make('button', 'Record outcome', 'secondary');
          button.type = 'button';
          button.onclick = () => showForm(article, plan, stop, button);
          article.append(button);
        }
        section.append(article);
      }
      root.append(section);
    }
  }
  function showForm(article, plan, stop, button) {
    button.remove();
    const form = make('form', undefined, 'route-outcome');
    const field = (label, element) => {
      const wrapper = make('label', label);
      wrapper.append(element); form.append(wrapper); return element;
    };
    const choice = make('select');
    for (const status of statusChoices) {
      const option = make('option', status); option.value = status; choice.append(option);
    }
    field('Visit outcome', choice);
    const reason = field('Reason (required unless done)', make('textarea'));
    reason.rows = 2; reason.maxLength = 5000;
    const action = field('Action taken / discussion', make('textarea'));
    action.rows = 2; action.maxLength = 5000;
    const next = field('Next action', make('textarea'));
    next.rows = 2; next.maxLength = 5000;
    const nextDate = field('Next action date', make('input')); nextDate.type = 'date';
    const postpone = field('Postponed to', make('input')); postpone.type = 'date';
    const gps = make('button', 'Capture GPS (optional)', 'secondary'); gps.type = 'button';
    const gpsLabel = make('p', 'No location captured', 'hint');
    let geo = {};
    gps.onclick = () => {
      if (!navigator.geolocation) { notify('This device does not support GPS.', true); return; }
      gps.disabled = true;
      navigator.geolocation.getCurrentPosition(pos => {
        geo = {latitude: pos.coords.latitude, longitude: pos.coords.longitude, accuracy: pos.coords.accuracy};
        gpsLabel.textContent = 'GPS captured ±' + Math.round(pos.coords.accuracy) + ' m';
        gps.disabled = false;
      }, err => { gps.disabled = false; notify('GPS unavailable: ' + err.message, true); },
      {enableHighAccuracy: true, maximumAge: 0, timeout: 15000});
    };
    form.append(gps, gpsLabel);
    const submit = make('button', 'Save outcome offline', 'button'); submit.type = 'submit';
    form.append(submit);
    form.onsubmit = async event => {
      event.preventDefault();
      const outcome = choice.value;
      if (outcome !== 'Done' && !reason.value.trim()) { notify('A reason is required.', true); return; }
      if (outcome === 'Postponed' && !postpone.value) { notify('Select the postponed date.', true); return; }
      submit.disabled = true;
      try {
        const operation = {
          version: 1, kind: 'route_outcome', id: crypto.randomUUID(),
          recorded_at: new Date().toISOString(), status: 'pending',
          payload: {
            plan: plan.name, stop: stop.name, outcome, reason: reason.value.trim(),
            action_taken: action.value.trim(), next_action: next.value.trim(),
            next_action_date: nextDate.value, postponed_to: postpone.value, ...geo
          }
        };
        await getStore().save(operation);
        notify('Route outcome saved on this device. It will sync when connected.');
        await render();
        if (navigator.onLine) void sync();
      } catch (error) { submit.disabled = false; notify(error.message, true); }
    };
    article.append(form);
  }
  return {load, render};
}
