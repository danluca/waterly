"""Sensor migration, API validation and scheduler I/O against an isolated database."""
import copy
import re
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

for module in ('gpiozero', 'modbus_tk', 'modbus_tk.defines', 'modbus_tk.modbus_rtu', 'serial'):
    sys.modules.setdefault(module, MagicMock())

from waterly import sensors, storage, web, scheduler
from waterly.config import CONFIG
from waterly.patch import Patch
from waterly.model.zone import Zone
from waterly.model.trend import TrendName
from waterly.dfrobot import SEN0605


class SensorInventoryTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        path = str(Path(temp.name) / 'sensors.sqlite')

        @contextmanager
        def database():
            conn = sqlite3.connect(path, isolation_level=None)
            try:
                yield conn
            finally:
                conn.close()

        self.db = database
        original_settings = copy.deepcopy(CONFIG.settings)
        original_callback = CONFIG._persist_callback
        self.addCleanup(setattr, CONFIG, 'settings', original_settings)
        self.addCleanup(setattr, CONFIG, '_persist_callback', original_callback)
        mock_db = patch.object(storage, 'db', database)
        mock_db.start()
        self.addCleanup(mock_db.stop)
        storage.init_db()
        self.client = web.app.test_client()

    def entries(self):
        return sensors.inventory()['sensors']

    def create_body(self, **changes):
        return dict(name='Spare', type='SEN0604', address=42, zone_id=None, enabled=True, **changes)

    def test_migration_copies_configuration_and_preserves_ids_and_history(self):
        entries = self.entries()
        self.assertEqual({(s['zone'], s['type'], s['address']) for s in entries}, {
            ('Z1', 'SEN0604', 10), ('Z2', 'SEN0604', 11), ('Z3', 'SEN0604', 12),
            ('Z2', 'SEN0605', 32), ('ENV', 'SEN0438', 48)})
        with self.db() as conn:
            conn.execute("INSERT INTO measurement(zone_id,name,unit,ts_utc,reading) VALUES(1,'humidity','%',1000,55)")
            zones = conn.execute('SELECT * FROM zone').fetchall()
        storage.init_db()
        self.assertEqual(len(self.entries()), 5)
        with self.db() as conn:
            self.assertEqual(conn.execute('SELECT * FROM zone').fetchall(), zones)
            self.assertEqual(conn.execute('SELECT zone_id,reading FROM measurement').fetchone(), (1, 55))

    def test_tools_page_serves_the_built_application(self):
        response = self.client.get('/tools')
        self.assertEqual(response.status_code, 200)
        script = re.search(r'src="(/static/js/[^"]+)"', response.get_data(as_text=True))
        self.assertIsNotNone(script)
        bundle = self.client.get(script.group(1))
        self.assertEqual(bundle.status_code, 200)
        self.assertIn('/api/sensors', bundle.get_data(as_text=True))
        response.close()
        bundle.close()

    def test_previous_sensor_page_redirects_to_tools(self):
        response = self.client.get('/sensors')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers['Location'], '/tools#sensors')

    def test_migration_uses_custom_existing_addresses_and_missing_sensors(self):
        with self.db() as conn:
            conn.execute('DROP TABLE sensor')
            conn.execute("DELETE FROM migration_history WHERE version='1.0.8'")
            conn.execute("UPDATE zone SET rh_sensor_address=73 WHERE name='Z1'")
            conn.execute("UPDATE zone SET npk_sensor_address=NULL WHERE name='Z2'")
        storage.init_db()
        self.assertEqual(len(self.entries()), 4)
        self.assertEqual(next(s for s in self.entries() if s['zone'] == 'Z1')['address'], 73)

    def test_api_manual_entry_hex_and_strict_validation(self):
        body = self.create_body()
        body['address'] = '0x2A'
        result = self.client.post('/api/sensors', json=body)
        self.assertEqual(result.status_code, 201)
        self.assertEqual(self.entries()[-1]['address'], 42)
        for field, value in [('address', 0), ('address', 248), ('address', True), ('address', 1.5),
                             ('type', []), ('enabled', 'yes'), ('zone_id', True), ('name', ' '),
                             ('zone_id', 999)]:
            with self.subTest(field=field, value=value):
                invalid = self.create_body()
                invalid[field] = value
                self.assertEqual(self.client.post('/api/sensors', json=invalid).status_code, 400)
        self.assertEqual(self.client.post('/api/sensors', json=[]).status_code, 400)

    def test_new_year_carries_inventory_forward_without_copying_status_or_measurements(self):
        with tempfile.TemporaryDirectory() as directory:
            for year in (2026, 2027):
                target = sqlite3.connect(str(Path(directory) / f'waterly-{year}.sqlite'), isolation_level=None)
                with self.db() as source:
                    source.backup(target)
                if year == 2026:
                    target.execute("UPDATE sensor SET name='Moved probe',address=79,enabled=0,status='offline',test_pending=1 WHERE id=1")
                    target.execute("INSERT INTO measurement(zone_id,name,unit,ts_utc,reading) VALUES(1,'humidity','%',1000,55)")
                else:
                    storage.carry_forward_sensor_inventory(target)
                    row = target.execute('SELECT name,address,enabled,status,test_pending,applied_revision FROM sensor WHERE id=1').fetchone()
                    self.assertEqual(row, ('Moved probe', 79, 0, 'untested', 0, 0))
                    self.assertEqual(target.execute('SELECT count(*) FROM measurement').fetchone()[0], 0)
                target.close()

    def test_duplicates_type_compatibility_and_optimistic_edit(self):
        original = self.entries()[0]
        body = self.create_body()
        body['address'] = original['address']
        self.assertEqual(self.client.post('/api/sensors', json=body).status_code, 400)
        body['address'] = 42
        body['zone_id'] = original['zone_id']
        self.assertEqual(self.client.post('/api/sensors', json=body).status_code, 400)
        body['type'] = 'SEN0438'
        self.assertEqual(self.client.post('/api/sensors', json=body).status_code, 400)
        original['enabled'] = False
        self.assertEqual(self.client.put(f"/api/sensors/{original['id']}", json=original).status_code, 200)
        self.assertEqual(self.entries()[0]['status'], 'disabled')
        self.assertEqual(self.client.put(f"/api/sensors/{original['id']}", json=original).status_code, 409)

    def test_test_is_queued_by_api_and_executed_by_scheduler(self):
        config = self.entries()[0]
        driver = MagicMock(is_present=True)
        driver.read_all.return_value = {'moisture': 55}
        with patch.dict(sensors.DRIVERS, {'SEN0604': MagicMock(return_value=driver)}):
            result = self.client.post(f"/api/sensors/{config['id']}/test")
            self.assertEqual(result.status_code, 202)
            driver.open.assert_not_called()
            self.assertTrue(self.entries()[0]['test_pending'])
            sensors.run_pending_tests(self.entries())
        latest = self.entries()[0]
        self.assertFalse(latest['test_pending'])
        self.assertEqual(latest['status'], 'responding')
        self.assertTrue(latest['test_success'])
        self.assertIsNotNone(latest['last_seen'])
        self.assertEqual(latest['last_reading'], {'moisture': 55})
        driver.close.assert_called_once()
        self.assertEqual(self.client.post('/api/sensors/999/test').status_code, 404)

    def test_disabled_unassigned_sensor_can_be_tested_and_failure_closes_port(self):
        body = self.create_body()
        body['enabled'] = False
        sensor_id = sensors.save_sensor(body)
        sensors.request_test(sensor_id)
        driver = MagicMock(is_present=True)
        driver.read_all.side_effect = TimeoutError('No reply')
        with patch.dict(sensors.DRIVERS, {'SEN0604': MagicMock(return_value=driver)}):
            sensors.run_pending_tests(self.entries())
        latest = self.entries()[-1]
        self.assertEqual(latest['status'], 'disabled')
        self.assertFalse(latest['test_success'])
        self.assertIn('No reply', latest['test_error'])
        self.assertFalse(latest['test_pending'])
        driver.close.assert_called_once()

    def test_stale_test_results_cannot_overwrite_edited_configuration(self):
        old = self.entries()[0]
        updated = dict(old, address=79)
        sensors.save_sensor(updated, old['id'])
        sensors.record_status(old, True, tested=True)
        latest = self.entries()[0]
        self.assertEqual(latest['status'], 'untested')
        self.assertIsNone(latest['tested_at'])

    def test_rebinding_clears_moisture_and_preserves_relay_and_history(self):
        relay = object()
        garden = SimpleNamespace(zone=SimpleNamespace(name='Z1'), rh_sensor=None, npk_sensor=None,
                                 relay_device=relay, _last_humidity_reading=55)
        sensors.apply_inventory([garden], self.entries())
        self.assertIsNone(garden._last_humidity_reading)
        self.assertIs(garden.relay_device, relay)
        old = garden.rh_sensor
        garden._last_humidity_reading = 60
        sensors.apply_inventory([garden], self.entries())
        self.assertIs(garden.rh_sensor, old)
        self.assertEqual(garden._last_humidity_reading, 60)
        config = self.entries()[0]
        config['enabled'] = False
        sensors.save_sensor(config, config['id'])
        sensors.apply_inventory([garden], self.entries())
        self.assertIsNone(garden.rh_sensor)
        self.assertIsNone(garden._last_humidity_reading)

    def test_scheduler_defers_changes_and_tests_while_watering_or_purging(self):
        manager = scheduler.WateringManager.__new__(scheduler.WateringManager)
        manager._manual_mode = {}
        manager.patches = [SimpleNamespace(water_state=False)]
        with patch.object(scheduler, 'MAINTENANCE') as maintenance, \
                patch.object(scheduler, 'apply_inventory') as apply, \
                patch.object(scheduler, 'run_pending_tests') as tests:
            maintenance.watering = True
            maintenance.active = None
            manager._handle_sensor_inventory()
            apply.assert_not_called()
            tests.assert_not_called()
            maintenance.watering = False
            maintenance.active = {'purging': True}
            manager._handle_sensor_inventory()
            apply.assert_not_called()
            maintenance.active = None
            manager._handle_sensor_inventory()
            apply.assert_called_once()
            tests.assert_called_once()

    def test_failed_soil_sensor_does_not_prevent_npk_polling(self):
        soil = MagicMock(is_present=True)
        soil.open.side_effect = OSError('Soil disconnected')
        npk = MagicMock(is_present=True, is_open=True)
        npk.read_all.return_value = {SEN0605.ReadingType.NITROGEN: 10,
                                     SEN0605.ReadingType.PHOSPHORUS: 20,
                                     SEN0605.ReadingType.POTASSIUM: 30}
        with patch.dict(sensors.DRIVERS, {'SEN0604': MagicMock(return_value=soil),
                                        'SEN0605': MagicMock(return_value=npk)}):
            garden = Patch(Zone('Z2', relay_address=16))
            garden._logger = MagicMock()
            sensors.apply_inventory([garden], self.entries())
            soil.open.assert_not_called()
            garden.open_sensor_bus()
            readings = garden.measurements()
            garden.close_sensor_bus()
        self.assertEqual(readings[TrendName.NITROGEN].value, 10)
        self.assertNotIn(TrendName.HUMIDITY, readings)
        npk.close.assert_called_once()
        latest = {s['type']: s for s in self.entries() if s['zone'] == 'Z2'}
        self.assertEqual(latest['SEN0604']['status'], 'offline')
        self.assertEqual(latest['SEN0605']['status'], 'responding')


if __name__ == '__main__':
    unittest.main()
