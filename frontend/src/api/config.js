/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

// Massage config values:
// - If a value is a plain object with a single property named 'value',
//   collapse it to that property's value.
// - Otherwise, leave as-is.
function massage(obj) {
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return obj;
    const out = {};
    for (const [k, v] of Object.entries(obj)) {
      if (v && typeof v === 'object' && !Array.isArray(v)) {
        const keys = Object.keys(v);
        if (keys.length === 1 && keys[0] === 'value') {
          out[k] = v.value;
        } else {
          out[k] = v;
        }
      } else {
        out[k] = v;
      }
    }
    return out;
}

export async function getConfig() {
  let res, data;
  try {
    res = await fetch('/api/config', {headers: {'Accept': 'application/json'}});
    data = await res.json();
  } catch (e) {
    // In dev, CRA serves public/api/config at the same path; try again as plain fetch
    const fallback = await fetch('/api/config');
    data = await fallback.json();
    res = fallback;
  }
  if (typeof data === 'string') {
    try { data = JSON.parse(data); } catch (_) {}
  }

  const massaged = massage(data);
  return {ok: res.ok, data: massaged};
}

export async function postConfig(payload) {
  const res = await fetch('/api/config', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify(payload)
  });
  let out;
  try { out = await res.json(); } catch (_) { out = {}; }
  if (typeof out === 'string') {
    try { out = JSON.parse(out); } catch (_) {}
  }

  if (out.config) {
      out.config = massage(out.config);
  }
  return {ok: res.ok, status: res.status, data: out};
}
