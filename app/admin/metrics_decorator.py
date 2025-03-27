import functools
import json
import time
import os
import threading
from datetime import datetime
from flask import request, g, current_app
from pathlib import Path


class FunctionMetrics:
    def __init__(self, metrics_file=None):
        if metrics_file is None:
            base_dir = Path(current_app.instance_path if current_app else "instance")
            self.metrics_file = str(base_dir / "metrics.json")
        else:
            self.metrics_file = metrics_file
        self.metrics = self._load_metrics()
        self.lock = threading.Lock()

    def _load_metrics(self):
        os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
        try:
            with open(self.metrics_file, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_metrics(self):
        with self.lock:
            os.makedirs(os.path.dirname(self.metrics_file), exist_ok=True)
            with open(self.metrics_file, "w") as f:
                json.dump(self.metrics, f, indent=2)

    def track(self, track_args=False, track_user=True):
        def decorator(func):
            func_name = func.__qualname__

            if func_name not in self.metrics:
                self.metrics[func_name] = {
                    "calls": 0,
                    "errors": 0,
                    "total_time": 0,
                    "last_called": None,
                    "args_data": {},
                    "user_data": {},
                }

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                result = None
                error = None

                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    error = str(e)
                    raise
                finally:
                    end_time = time.time()
                    exec_time = end_time - start_time

                    with self.lock:
                        self.metrics[func_name]["calls"] += 1
                        self.metrics[func_name]["total_time"] += exec_time
                        self.metrics[func_name][
                            "last_called"
                        ] = datetime.now().isoformat()

                        if error:
                            self.metrics[func_name]["errors"] += 1

                        if track_args:
                            # Handle only hashable arguments
                            try:
                                args_key = str(args) + str(sorted(kwargs.items()))
                                if args_key not in self.metrics[func_name]["args_data"]:
                                    self.metrics[func_name]["args_data"][args_key] = 0
                                self.metrics[func_name]["args_data"][args_key] += 1
                            except:
                                pass

                        if track_user and hasattr(g, "user") and g.user and g.user.id:
                            user_id = str(g.user.id)
                            if user_id not in self.metrics[func_name]["user_data"]:
                                self.metrics[func_name]["user_data"][user_id] = 0
                            self.metrics[func_name]["user_data"][user_id] += 1

                    self._save_metrics()

            return wrapper

        return decorator

    def get_metrics(self, func_name=None):
        if func_name:
            return self.metrics.get(func_name, {})
        return self.metrics

    def reset_metrics(self, func_name=None):
        with self.lock:
            if func_name:
                if func_name in self.metrics:
                    self.metrics[func_name] = {
                        "calls": 0,
                        "errors": 0,
                        "total_time": 0,
                        "last_called": None,
                        "args_data": {},
                        "user_data": {},
                    }
            else:
                self.metrics = {}
            self._save_metrics()


# Create a singleton instance
metrics = FunctionMetrics()


# Main decorator to track function metrics
def track_metrics(track_args=False, track_user=True):
    return metrics.track(track_args, track_user)


# Helper function to get metrics data
def get_metrics(func_name=None):
    return metrics.get_metrics(func_name)


# Helper function to reset metrics data
def reset_metrics(func_name=None):
    metrics.reset_metrics(func_name)
