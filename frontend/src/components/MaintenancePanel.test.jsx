import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import MaintenancePanel from './MaintenancePanel';

global.IS_REACT_ACT_ENVIRONMENT = true;

describe('manual air purge controls', () => {
  let container, root, status, changed;
  const sensorData = {Z1: {name: 'Z1', desc: 'Zone 1', water_state: 0}};
  const button = label => [...container.querySelectorAll('button')].find(b => b.textContent === label);
  const response = data => Promise.resolve({ok: true, json: async () => data});
  const render = async () => {
    await act(async () => root.render(<MaintenancePanel sensorData={sensorData} onStatusChange={changed} />));
  };

  beforeEach(() => {
    jest.useFakeTimers();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    status = {winterized: false, watering: false, active: null, history: [], max_seconds: 600};
    changed = jest.fn();
    global.fetch = jest.fn(() => response(status));
  });

  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    jest.useRealTimers();
    delete global.fetch;
  });

  it('starts the selected zone with a bounded duration in seconds', async () => {
    await render();
    await act(async () => button('Start purge').click());
    expect(fetch).toHaveBeenCalledWith('/api/purge/Z1/start', expect.objectContaining({
      method: 'POST', body: JSON.stringify({seconds: 60}),
    }));
    expect(fetch.mock.calls.filter(([url]) => url === '/api/maintenance')).toHaveLength(2);
  });

  it('fetches once when opened and makes no idle polling requests', async () => {
    await render();
    await act(async () => jest.advanceTimersByTime(10000));
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('blocks overlapping starts and offers stop after a reload', async () => {
    status.active = {zone: 'Z1', remaining_seconds: 15};
    await render();
    expect(button('Start purge').disabled).toBe(true);
    expect(button('Mark system winterized').disabled).toBe(true);
    expect(container.textContent).toContain('15s remaining');
    await act(async () => button('Stop purge').click());
    expect(fetch).toHaveBeenCalledWith('/api/purge/stop', expect.objectContaining({method: 'POST'}));
  });

  it('keeps purge available while winterized and explicitly re-enables watering', async () => {
    status.winterized = true;
    await render();
    expect(button('Start purge').disabled).toBe(false);
    expect(container.textContent).toContain('manual and scheduled watering are blocked');
    await act(async () => button('Re-enable watering').click());
    expect(fetch).toHaveBeenCalledWith('/api/maintenance/winterized', expect.objectContaining({
      body: JSON.stringify({winterized: false}),
    }));
  });

  it('polls live completion and displays separate purge history', async () => {
    status.active = {zone: 'Z1', remaining_seconds: 1};
    await render();
    status = {...status, active: null, history: [{id: 1, zone: 'Z1', started_at: '2026-11-11T12:00:00Z',
      requested_seconds: 60, duration_seconds: 60, outcome: 'completed'}]};
    await act(async () => jest.advanceTimersByTime(2000));
    expect(button('Start purge').disabled).toBe(false);
    expect(button('Stop purge').disabled).toBe(true);
    expect(container.textContent).toContain('Recent purges');
    expect(container.textContent).toContain('completed');
    expect(changed).toHaveBeenLastCalledWith(status);
  });

  it('shows API conflicts and leaves controls usable', async () => {
    await render();
    fetch.mockImplementationOnce(() => Promise.resolve({ok: false, json: async () => ({message: 'Watering is active.'})}));
    await act(async () => button('Start purge').click());
    expect(container.textContent).toContain('Watering is active.');
    expect(button('Start purge').disabled).toBe(false);
  });

  it('blocks purge and winterized changes while watering', async () => {
    status.watering = true;
    await render();
    expect(button('Start purge').disabled).toBe(true);
    expect(button('Mark system winterized').disabled).toBe(true);
  });
});
