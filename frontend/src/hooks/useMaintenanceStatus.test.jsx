import React, {act} from 'react';
import {createRoot} from 'react-dom/client';
import useMaintenanceStatus from './useMaintenanceStatus';

global.IS_REACT_ACT_ENVIRONMENT = true;

describe('maintenance status requests', () => {
  let container, root, status, refresh;
  const response = data => ({ok: true, json: async () => data});
  function Consumer({enabled}) {
    const result = useMaintenanceStatus(enabled);
    refresh = result.refresh;
    return <span>{result.status?.active ? 'purging' : 'idle'}</span>;
  }
  const render = async enabled => {
    await act(async () => root.render(<Consumer enabled={enabled} />));
  };
  const advance = async ms => {
    await act(async () => jest.advanceTimersByTime(ms));
  };

  beforeEach(() => {
    jest.useFakeTimers();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
    status = {active: null};
    global.fetch = jest.fn(async () => response(status));
  });
  afterEach(async () => {
    await act(async () => root.unmount());
    container.remove();
    jest.useRealTimers();
    delete global.fetch;
  });

  it('fetches once on open, stays idle without polling, and refreshes on reopen', async () => {
    await render(false);
    expect(fetch).not.toHaveBeenCalled();
    await render(true);
    expect(fetch).toHaveBeenCalledTimes(1);
    await advance(10000);
    expect(fetch).toHaveBeenCalledTimes(1);
    await render(false);
    await render(true);
    expect(fetch).toHaveBeenCalledTimes(2);
  });

  it('polls every two seconds during a purge and stops when it completes', async () => {
    status = {active: {zone: 'Z1'}};
    await render(true);
    await advance(1999);
    expect(fetch).toHaveBeenCalledTimes(1);
    await advance(1);
    expect(fetch).toHaveBeenCalledTimes(2);
    status = {active: null};
    await advance(2000);
    expect(fetch).toHaveBeenCalledTimes(3);
    await advance(10000);
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it('starts and stops polling when an action refresh changes purge status', async () => {
    await render(true);
    status = {active: {zone: 'Z1'}};
    await act(async () => refresh());
    await advance(2000);
    expect(fetch).toHaveBeenCalledTimes(3);
    status = {active: null};
    await act(async () => refresh());
    await advance(10000);
    expect(fetch).toHaveBeenCalledTimes(4);
  });

  it('cancels active polling when the dialog closes', async () => {
    status = {active: {zone: 'Z1'}};
    await render(true);
    await render(false);
    await advance(10000);
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('retries a failed poll while the last known purge is active', async () => {
    status = {active: {zone: 'Z1'}};
    await render(true);
    fetch.mockRejectedValueOnce(new Error('Network unavailable'));
    await advance(2000);
    status = {active: null};
    await advance(2000);
    expect(fetch).toHaveBeenCalledTimes(3);
    expect(container.textContent).toBe('idle');
    await advance(10000);
    expect(fetch).toHaveBeenCalledTimes(3);
  });

  it('ignores an older response arriving after the action refresh', async () => {
    let resolveFirst;
    fetch.mockImplementationOnce(() => new Promise(resolve => { resolveFirst = resolve; }));
    await render(true);
    await act(async () => refresh());
    await act(async () => resolveFirst(response({active: {zone: 'Z1'}})));
    expect(container.textContent).toBe('idle');
    await advance(10000);
    expect(fetch).toHaveBeenCalledTimes(2);
  });
});
