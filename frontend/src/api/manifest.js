/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

export async function fetchManifest() {
  const response = await fetch('/api/manifest');
  if (!response.ok) throw new Error(`HTTP ${response.status}`);
  return response.json();
}
