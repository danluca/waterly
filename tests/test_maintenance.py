"""Exercise maintenance against an isolated database and simulated valves."""
import copy
import sqlite3
import sys
import tempfile
import threading
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.modules.setdefault('gpiozero', MagicMock())
sys.modules.setdefault('modbus_tk', MagicMock())
sys.modules.setdefault('modbus_tk.defines', MagicMock())
sys.modules.setdefault('modbus_tk.modbus_rtu', MagicMock())
sys.modules.setdefault('serial', MagicMock())

from waterly import storage, web, scheduler
from waterly.config import CONFIG, Settings
from waterly.maintenance import MaintenanceController, OperationConflict
from waterly.queues import Action, QueueMessage


class FakeValve:
    def __init__(self, name='Z1'):
        self.zone = SimpleNamespace(name=name)
        self.water_state = False
        self.closed = threading.Event()
        self.close_failures = 0

    def start_watering(self):
        self.water_state = True

    def stop_watering(self):
        if self.close_failures:
            self.close_failures -= 1
            raise OSError('Simulated valve-close failure')
        self.water_state = False
        self.closed.set()

    def close_sensor_bus(self):
        pass


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        db_path = str(Path(self.temp.name) / 'test.sqlite')

        @contextmanager
        def isolated_db():
            conn = sqlite3.connect(db_path, isolation_level=None)
            try:
                yield conn
            finally:
                conn.close()

        self.db = isolated_db
        self.saved_settings = copy.deepcopy(CONFIG.settings)
        self.saved_callback = CONFIG._persist_callback
        self.saved_file = CONFIG._settings_file
        CONFIG._settings_file = str(Path(self.temp.name) / 'settings.json')
        self.addCleanup(self.restore_config)
        self.db_patch = patch.object(storage, 'db', isolated_db)
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        storage.init_db()
        CONFIG.set_transient(Settings.WINTERIZED, False)
        self.controller = MaintenanceController()
        self.valve = FakeValve()
        self.pulses = MagicMock()
        self.controller.configure([self.valve], self.pulses.reset_count)
        self.addCleanup(self.controller.stop)
        self.controller_patches = [patch.object(web, 'MAINTENANCE', self.controller),
                                   patch.object(scheduler, 'MAINTENANCE', self.controller),
                                   patch.object(web, 'PATCHES', [self.valve])]
        for item in self.controller_patches:
            item.start()
            self.addCleanup(item.stop)
        self.client = web.app.test_client()

    def restore_config(self):
        CONFIG.settings = self.saved_settings
        CONFIG._persist_callback = self.saved_callback
        CONFIG._settings_file = self.saved_file

    def manager(self):
        return scheduler.WateringManager([self.valve], MagicMock(), self.pulses)

    def test_start_stop_and_separate_history(self):
        self.controller.start(self.valve, 60)
        self.assertTrue(self.valve.water_state)
        self.assertFalse(self.controller.begin_watering())
        self.controller.stop()
        self.assertFalse(self.valve.water_state)
        record = storage.get_purge_history()[0]
        self.assertEqual((record['zone'], record['requested_seconds'], record['outcome']), ('Z1', 60, 'stopped'))
        self.assertGreaterEqual(record['duration_seconds'], 0)
        self.assertEqual(self.pulses.reset_count.call_count, 2)
        with self.db() as conn:
            self.assertEqual(conn.execute('SELECT count(*) FROM measurement').fetchone()[0], 0)
            self.assertEqual(conn.execute('SELECT count(*) FROM watering_record').fetchone()[0], 0)

    def test_timer_closes_without_scheduler(self):
        self.controller.start(self.valve, 1)
        self.assertTrue(self.valve.closed.wait(3))
        # Synchronize with the timer's history update.
        with self.controller.lock:
            self.assertIsNone(self.controller.active)
        self.assertEqual(storage.get_purge_history()[0]['outcome'], 'completed')

    def test_rejects_overlapping_operations(self):
        self.assertTrue(self.controller.begin_watering())
        with self.assertRaises(OperationConflict):
            self.controller.start(self.valve, 10)
        with self.assertRaises(OperationConflict):
            self.controller.set_winterized(True)
        self.controller.end_watering()
        self.controller.start(self.valve, 10)
        with self.assertRaises(OperationConflict):
            self.controller.start(FakeValve('Z2'), 10)
        with self.assertRaises(OperationConflict):
            self.controller.set_winterized(True)

    def test_rejects_open_valve_even_without_watering_lease(self):
        self.valve.water_state = True
        with self.assertRaises(OperationConflict):
            self.controller.start(self.valve, 10)
        self.valve.water_state = False

    def test_winterized_persists_and_allows_purging(self):
        self.controller.set_winterized(True)
        CONFIG.set_transient(Settings.WINTERIZED, False)
        storage.get_config_from_db()
        self.assertTrue(CONFIG[Settings.WINTERIZED])
        self.assertFalse(self.controller.begin_watering())
        self.assertEqual(self.client.post('/api/water/Z1/start').status_code, 409)
        self.controller.start(self.valve, 10)
        self.controller.stop()
        self.controller.set_winterized(False)
        self.assertTrue(self.controller.begin_watering())

    def test_persistence_failure_does_not_change_state(self):
        with patch('waterly.maintenance.save_config_item', side_effect=OSError('disk full')):
            with self.assertRaises(OSError):
                self.controller.set_winterized(True)
        self.assertFalse(CONFIG[Settings.WINTERIZED])

    def test_new_year_database_keeps_file_winterized_setting(self):
        self.controller.set_winterized(True)
        with self.db() as conn:
            conn.execute("DELETE FROM config WHERE type='WINTERIZED'")
        CONFIG.set_transient(Settings.WINTERIZED, False)
        CONFIG.read_from_file()
        storage.get_config_from_db()
        self.assertTrue(CONFIG[Settings.WINTERIZED])

    def test_start_failure_closes_valve_and_records_failed_purge(self):
        with patch.object(self.valve, 'start_watering', side_effect=OSError('relay failed')):
            with self.assertRaises(OSError):
                self.controller.start(self.valve, 10)
        self.assertFalse(self.valve.water_state)
        self.assertIsNone(self.controller.active)
        self.assertEqual(storage.get_purge_history()[0]['outcome'], 'failed')

    def test_history_write_failure_blocks_watering_until_retry(self):
        self.controller.start(self.valve, 60)
        with patch('waterly.maintenance.finish_purge_record', side_effect=OSError('disk full')):
            with self.assertLogs('waterly.maintenance', level='ERROR'):
                self.controller.stop()
        self.assertFalse(self.valve.water_state)
        self.assertFalse(self.controller.begin_watering())
        self.controller.stop()
        self.assertIsNone(self.controller.active)

    def test_stale_watering_request_cannot_start_after_purge(self):
        token = self.controller.watering_token()
        self.controller.start(self.valve, 10)
        self.controller.stop()
        self.assertFalse(self.controller.begin_watering(token))
        self.assertTrue(self.controller.begin_watering(self.controller.watering_token()))

    def test_invalid_durations_and_unknown_zone(self):
        for value in (None, True, 0, -1, 601, 1.5, '60'):
            with self.subTest(value=value):
                self.assertEqual(self.client.post('/api/purge/Z1/start', json={'seconds': value}).status_code, 400)
        self.assertEqual(self.client.post('/api/purge/unknown/start', json={'seconds': 10}).status_code, 404)
        for value in ('true', 1, None):
            self.assertEqual(self.client.post('/api/maintenance/winterized', json={'winterized': value}).status_code, 400)

    def test_api_status_start_stop_and_idempotent_stop(self):
        self.assertEqual(self.client.post('/api/purge/Z1/start', json={'seconds': 20}).status_code, 200)
        status = self.client.get('/api/maintenance').get_json()
        self.assertEqual(status['active']['zone'], 'Z1')
        self.assertEqual(len(status['history']), 1)
        self.assertEqual(self.client.post('/api/purge/Z1/start', json={'seconds': 10}).status_code, 409)
        self.assertEqual(self.client.post('/api/purge/stop').status_code, 200)
        self.assertEqual(self.client.post('/api/purge/stop').status_code, 200)

    def test_close_failure_keeps_interlock_until_retry(self):
        self.controller.start(self.valve, 60)
        self.valve.close_failures = 1
        with self.assertLogs('waterly.maintenance', level='ERROR'):
            result = self.controller.stop()
        self.assertIn('failure', result['active']['error'])
        self.assertFalse(self.controller.begin_watering())
        self.controller.stop()
        self.assertIsNone(self.controller.active)
        self.assertFalse(self.valve.water_state)

    def test_stale_timer_cannot_stop_new_purge(self):
        self.controller.start(self.valve, 60)
        first = self.controller.active['id']
        self.controller.stop()
        self.controller.start(self.valve, 60)
        self.controller._finish(first, 'completed')
        self.assertTrue(self.valve.water_state)

    def test_restart_marks_unfinished_record_interrupted(self):
        record = storage.start_purge_record('Z1', 30)
        storage.interrupt_purge_records()
        self.assertEqual(storage.get_purge_history()[0]['id'], record)
        self.assertEqual(storage.get_purge_history()[0]['outcome'], 'interrupted')
        self.assertIsNone(self.controller.active)

    def test_scheduler_skips_auto_and_manual_while_purging(self):
        manager = self.manager()
        self.controller.start(self.valve, 60)
        with patch.object(manager, '_assess_auto_watering') as assess:
            manager._handle_auto_watering()
            assess.assert_not_called()
        message = QueueMessage(Action.START_WATERING, {'zone': 'Z1', 'generation': self.controller.generation})
        with patch.object(scheduler, 'receive_scheduler_message', return_value=message):
            manager._handle_thread_messages()
        self.assertEqual(manager._manual_mode, {})

    def test_manual_request_holds_interlock_until_cancelled(self):
        manager = self.manager()
        message = QueueMessage(Action.START_WATERING, {'zone': 'Z1', 'minutes': 1})
        with patch.object(scheduler, 'receive_scheduler_message', return_value=message):
            manager._handle_thread_messages()
        self.assertTrue(self.controller.watering)
        with self.assertRaises(OperationConflict):
            self.controller.start(self.valve, 10)
        with patch.object(scheduler, 'receive_scheduler_message', return_value=QueueMessage(Action.STOP_WATERING, {'zone': 'Z1'})):
            manager._handle_thread_messages()
        self.assertFalse(self.controller.watering)

    def test_auto_stop_does_not_release_interlock_during_cycle(self):
        manager = self.manager()
        self.controller.begin_watering()
        with patch.object(scheduler, 'receive_scheduler_message', return_value=QueueMessage(Action.STOP_WATERING, {'zone': 'Z1'})):
            manager._handle_thread_messages()
        self.assertTrue(manager._auto_cancelled)
        self.assertTrue(self.controller.watering)

    def test_queued_water_stop_cannot_close_purge_valve(self):
        manager = self.manager()
        self.controller.start(self.valve, 10)
        with patch.object(scheduler, 'receive_scheduler_message', return_value=QueueMessage(Action.STOP_WATERING, {'zone': 'Z1'})):
            manager._handle_thread_messages()
        self.assertTrue(self.valve.water_state)


if __name__ == '__main__':
    unittest.main()
