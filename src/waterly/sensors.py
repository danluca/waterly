"""Persisted sensor inventory and scheduler-owned RS485 connections.

Web requests only touch the inventory; all serial I/O runs on WateringManager.
"""
import sqlite3
import json
from datetime import datetime, UTC

from . import storage
from .dfrobot import SEN0604, SEN0605
from .dfrobot.sen0438 import SEN0438

DRIVERS = {'SEN0604': SEN0604, 'SEN0605': SEN0605, 'SEN0438': SEN0438}


class InventoryConflict(ValueError):
    pass


def inventory():
    with storage.db() as conn:
        conn.row_factory = sqlite3.Row
        sensors = [dict(r) for r in conn.execute(
            'SELECT s.*, z.name AS zone FROM sensor s LEFT JOIN zone z ON z.id=s.zone_id ORDER BY s.id')]
        zones = [dict(r) for r in conn.execute(
            "SELECT id, name, description, relay_address FROM zone WHERE relay_address IS NOT NULL OR name='ENV'")]
    for sensor in sensors:
        sensor['last_reading'] = json.loads(sensor['last_reading']) if sensor['last_reading'] else None
        sensor['enabled'] = bool(sensor['enabled'])
        sensor['test_pending'] = bool(sensor['test_pending'])
        sensor['pending'] = sensor['revision'] != sensor['applied_revision']
        sensor['status'] = sensor['status'] if sensor['enabled'] else 'disabled'
    return {'sensors': sensors, 'zones': zones, 'types': list(DRIVERS)}


def save_sensor(body, sensor_id=None):
    if not isinstance(body, dict):
        raise ValueError('Expected a JSON object.')
    name = body.get('name')
    model = body.get('type')
    enabled = body.get('enabled')
    zone_id = body.get('zone_id')
    address = body.get('address')
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
        raise ValueError('Name must contain 1 to 80 characters.')
    if not isinstance(model, str) or model not in DRIVERS:
        raise ValueError('Select a supported sensor type.')
    if type(enabled) is not bool:
        raise ValueError('Enabled must be a boolean.')
    if isinstance(address, str):
        try:
            address = int(address, 16 if address.lower().startswith('0x') else 10)
        except ValueError:
            raise ValueError('Address must be a whole number or hexadecimal value such as 0x0A.')
    if type(address) is not int or not 1 <= address <= 247:
        raise ValueError('Address must be a whole number from 1 to 247.')
    if zone_id is not None and type(zone_id) is not int:
        raise ValueError('Select a valid zone or leave the sensor unassigned.')
    with storage.db() as conn:
        conn.execute('BEGIN IMMEDIATE')
        try:
            if zone_id is not None:
                zone = conn.execute('SELECT name, relay_address FROM zone WHERE id=?', (zone_id,)).fetchone()
                if not zone or (model == 'SEN0438' and zone[0] != 'ENV') or (model != 'SEN0438' and not zone[1]):
                    raise ValueError('Air sensors require ENV; soil and NPK sensors require a garden zone.')
            values = (name.strip(), model, address, zone_id, int(enabled))
            if sensor_id is None:
                cur = conn.execute('INSERT INTO sensor(name,type,address,zone_id,enabled) VALUES(?,?,?,?,?)', values)
                sensor_id = cur.lastrowid
            else:
                revision = body.get('revision')
                if type(revision) is not int:
                    raise ValueError('A revision is required when editing a sensor.')
                cur = conn.execute(
                    "UPDATE sensor SET name=?,type=?,address=?,zone_id=?,enabled=?,revision=revision+1,"
                    "status='untested',last_seen=NULL,last_error=NULL,last_reading=NULL,test_pending=0,tested_at=NULL,test_success=NULL,test_error=NULL "
                    'WHERE id=? AND revision=?', (*values, sensor_id, revision))
                if not cur.rowcount:
                    raise InventoryConflict('This sensor changed or no longer exists. Refresh before editing again.')
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise ValueError('Address already allocated, or this zone already has a sensor of that type.') from exc
        except Exception:
            conn.rollback()
            raise
    return sensor_id


def request_test(sensor_id):
    with storage.db() as conn:
        cur = conn.execute('UPDATE sensor SET test_pending=1, tested_at=NULL WHERE id=?', (sensor_id,))
        if not cur.rowcount:
            raise KeyError(sensor_id)


def record_status(config, success, error=None, tested=False, readings=None):
    now = datetime.now(UTC).isoformat()
    with storage.db() as conn:
        conn.execute(
            'UPDATE sensor SET status=?,last_error=?,last_seen=CASE WHEN ? THEN ? ELSE last_seen END,'
            'test_pending=CASE WHEN ? THEN 0 ELSE test_pending END,'
            'tested_at=CASE WHEN ? THEN ? ELSE tested_at END,'
            'test_success=CASE WHEN ? THEN ? ELSE test_success END,'
            'test_error=CASE WHEN ? THEN ? ELSE test_error END,'
            'last_reading=COALESCE(?,last_reading) WHERE id=? AND revision=?',
            ('responding' if success else 'offline', str(error)[:300] if error else None,
             success, now, tested, tested, now, tested, success, tested,
             str(error)[:300] if error else None,
             json.dumps({getattr(k, 'value', k): v for k, v in readings.items()}) if readings else None,
             config['id'], config['revision']))


class InventorySensor:
    """Lazy driver facade: never opens serial ports in the web thread or at startup."""
    def __init__(self, config):
        self.config = config
        self.device_addr = config['address']
        self.driver = None

    @property
    def is_open(self):
        return self.driver is not None and self.driver.is_open

    @property
    def is_present(self):
        return self.driver is not None and self.driver.is_present

    @property
    def _serial(self):
        return self.driver._serial

    def open(self):
        try:
            if self.driver is None:
                self.driver = DRIVERS[self.config['type']](deviceaddr=self.device_addr)
            self.driver.open()
            if not self.driver.is_present:
                raise OSError('No response at the configured address.')
        except Exception as exc:
            self.close()
            record_status(self.config, False, exc)
            raise

    def close(self):
        if self.driver is not None:
            self.driver.close()
        self.driver = None

    def __getattr__(self, name):
        if not name.startswith('read_'):
            raise AttributeError(name)
        def read(*args, **kwargs):
            try:
                result = getattr(self.driver, name)(*args, **kwargs)
                values = result.values() if isinstance(result, dict) else [result]
                if result is None or any(value is None for value in values):
                    raise OSError('Sensor returned an incomplete reading.')
                record_status(self.config, True, readings=result if isinstance(result, dict) else None)
                return result
            except Exception as exc:
                record_status(self.config, False, exc)
                raise
        return read


def apply_inventory(patches, sensors):
    """Replace sensor bindings only; preserve relay objects and watering state."""
    for patch in patches:
        selected = {s['type']: s for s in sensors if s['enabled'] and s['zone'] == patch.zone.name}
        changed = False
        for attr, model in (('rh_sensor', 'SEN0604'), ('npk_sensor', 'SEN0605')):
            old = getattr(patch, attr)
            config = selected.get(model)
            identity = lambda s: (s['id'], s['revision']) if s else None
            if identity(old.config if old else None) != identity(config):
                if old:
                    old.close()
                setattr(patch, attr, InventorySensor(config) if config else None)
                changed = True
        if changed:
            patch._last_humidity_reading = None
    with storage.db() as conn:
        for sensor in sensors:
            if sensor['pending']:
                conn.execute('UPDATE sensor SET applied_revision=? WHERE id=? AND revision=?',
                             (sensor['revision'], sensor['id'], sensor['revision']))


def run_pending_tests(sensors):
    for config in sensors:
        if not config['test_pending']:
            continue
        sensor = InventorySensor(config)
        try:
            sensor.open()
            sensor.read_all()
            record_status(config, True, tested=True)
        except Exception as exc:
            record_status(config, False, exc, tested=True)
        finally:
            sensor.close()
