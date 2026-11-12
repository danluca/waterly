"""Manual air purging and the interlock shared by all valve operations."""
import logging
import threading
import time

from .config import CONFIG, Settings
from .storage import start_purge_record, finish_purge_record, save_config_item


class OperationConflict(Exception):
    pass


class MaintenanceController:
    MAX_PURGE_SECONDS = 600

    def __init__(self):
        self.lock = threading.RLock()
        self.watering = False
        self.generation = 0
        self.active = None
        self._timer = None
        self._reset_pulses = lambda: None
        self._patches = []

    def configure(self, patches, reset_pulses):
        self._patches = patches
        self._reset_pulses = reset_pulses

    def status(self):
        with self.lock:
            active = None
            if self.active:
                active = {k: self.active[k] for k in ('id', 'zone', 'seconds', 'error')}
                active['remaining_seconds'] = max(0, self.active['seconds'] - int(time.monotonic() - self.active['start']))
            return {'winterized': CONFIG[Settings.WINTERIZED], 'watering': self.watering,
                    'active': active, 'max_seconds': self.MAX_PURGE_SECONDS}

    def watering_token(self):
        with self.lock:
            if CONFIG[Settings.WINTERIZED] or self.active:
                raise OperationConflict('Watering is blocked while winterized or purging.')
            return self.generation

    def begin_watering(self, generation=None):
        with self.lock:
            if (self.watering or self.active or CONFIG[Settings.WINTERIZED]
                    or any(p.water_state for p in self._patches)
                    or (generation is not None and generation != self.generation)):
                return False
            self.watering = True
            return True

    def end_watering(self):
        with self.lock:
            self.watering = False

    def set_winterized(self, value):
        if type(value) is not bool:
            raise ValueError('winterized must be a boolean.')
        with self.lock:
            if self.watering or self.active or any(p.water_state for p in self._patches):
                raise OperationConflict('Stop watering or purging before changing winterized mode.')
            # Persist explicitly: AppConfig's normal callback suppresses persistence errors.
            save_config_item(Settings.WINTERIZED, value)
            CONFIG.set_transient(Settings.WINTERIZED, value)
            self.generation += 1
            try:
                CONFIG.save_to_file()
            except Exception:
                logging.getLogger(__name__).exception('Winterized mode saved to database; settings file update failed')

    def start(self, patch, seconds):
        if type(seconds) is not int or not 1 <= seconds <= self.MAX_PURGE_SECONDS:
            raise ValueError(f'Duration must be a whole number from 1 to {self.MAX_PURGE_SECONDS} seconds.')
        with self.lock:
            if self.watering or self.active or any(p.water_state for p in self._patches):
                raise OperationConflict('Stop the current watering or purge before starting another purge.')
            record_id = start_purge_record(patch.zone.name, seconds)
            self.generation += 1  # Invalidate queued watering requests from before this purge.
            self.active = {'id': record_id, 'zone': patch.zone.name, 'patch': patch,
                           'seconds': seconds, 'start': time.monotonic(), 'error': None}
            try:
                self._reset_pulses()
                patch.start_watering()
                self._schedule(seconds, record_id, 'completed')
            except Exception:
                self._finish(record_id, 'failed')
                raise
            return self.status()

    def _schedule(self, seconds, record_id, outcome):
        self._timer = threading.Timer(seconds, self._finish, args=(record_id, outcome))
        self._timer.daemon = True
        self._timer.start()

    def _finish(self, record_id, outcome):
        with self.lock:
            if not self.active or self.active['id'] != record_id:
                return
            if self._timer:
                self._timer.cancel()
            try:
                self.active['patch'].stop_watering()
                self.active.setdefault('stopped_at', time.monotonic())
                self._reset_pulses()  # Air pulses must not appear as water usage or leakage.
                finish_purge_record(record_id, self.active['stopped_at'] - self.active['start'], outcome)
            except Exception as error:
                # Retain the interlock and retry if valve closure or history persistence fails.
                self.active['error'] = str(error)
                logging.getLogger(__name__).exception('Failed to finish purge; retrying')
                self._schedule(1, record_id, outcome)
                return
            self.active = None
            self._timer = None

    def stop(self, outcome='stopped'):
        with self.lock:
            if self.active:
                self._finish(self.active['id'], outcome)
            return self.status()


MAINTENANCE = MaintenanceController()
