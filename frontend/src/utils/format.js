/*
 * MIT License
 *
 * Copyright (c) 2025 by Dan Luca. All rights reserved.
 *
 */

export const fmt = (v, decimals = 2) => (typeof v === 'number' ? v.toLocaleString(undefined, { maximumFractionDigits: decimals }) : v);
