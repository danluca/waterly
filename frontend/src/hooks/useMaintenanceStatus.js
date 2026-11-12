import {useCallback, useEffect, useRef, useState} from 'react';

export default function useMaintenanceStatus(enabled = true) {
  const [status, setStatus] = useState(null);
  const [error, setError] = useState('');
  const latestRequest = useRef(0);

  const refresh = useCallback(async () => {
    const request = ++latestRequest.current;
    try {
      const response = await fetch('/api/maintenance');
      if (!response.ok) throw new Error('Could not load maintenance status.');
      const data = await response.json();
      if (request === latestRequest.current) {
        setStatus(data);
        setError('');
      }
      return data;
    } catch (e) {
      if (request === latestRequest.current) setError(e.message);
      throw e;
    }
  }, []);

  useEffect(() => {
    setStatus(null);
    setError('');
    if (enabled) refresh().catch(() => {});
    return () => { latestRequest.current += 1; };
  }, [enabled, refresh]);

  const purgeActive = !!status?.active;
  useEffect(() => {
    if (!enabled || !purgeActive) return;
    let alive = true;
    let timer;
    const poll = async () => {
      try {
        const data = await refresh();
        if (alive && data.active) timer = setTimeout(poll, 2000);
      } catch {
        // Keep checking a known active purge after a transient failure.
        if (alive) timer = setTimeout(poll, 2000);
      }
    };
    timer = setTimeout(poll, 2000);
    return () => { alive = false; clearTimeout(timer); };
  }, [enabled, purgeActive, refresh]);

  return {status, error, refresh};
}
