import math
import os
from datetime import datetime

import psutil

from datasync.controllers.controller import Controller
from datasync.libs.response import Response
from datasync.libs.utils import to_len, json_decode


class ControllerServer(Controller):

	@staticmethod
	def get_average(data):
		return round(sum(data) / to_len(data), 1)


	def get_server_status(self, data):
		cpu_percent = []
		memory_percent = []
		disk_usage_percent = []
		readio_mps = []
		writeio_mps = []
		new_info = 0
		for x in range(10):
			cpu_percent.append(psutil.cpu_percent(interval = 0.2))
			memory_percent.append(psutil.virtual_memory().percent)
			disk_usage_percent.append(psutil.disk_usage('/')[3])
			if x == 0:
				new_info = psutil.disk_io_counters()
			else:
				old_info = new_info
				new_info = psutil.disk_io_counters()
				r = round((new_info.read_bytes - old_info.read_bytes) / 1024 ** 2, 1)
				readio_mps.append(r)
				w = round((new_info.write_bytes - old_info.write_bytes) / 1024 ** 2, 1)
				writeio_mps.append(w)
		status = {
			"cpu_percent": self.get_average(cpu_percent),
			"memory_percent": self.get_average(memory_percent),
			"disk_usage_percent": self.get_average(disk_usage_percent),
			"readio_mps": self.get_average(readio_mps),
			"writeio_mps": self.get_average(writeio_mps)
		}

		# get migrations info
		sync_processes = []
		for proc in psutil.process_iter():
			proc_cmd = proc.cmdline()
			if proc.pid == os.getpid() or not proc_cmd or 'python' not in proc_cmd[0]:
				continue
			len_proc = len(proc_cmd)
			if len_proc > 2 and proc_cmd[-2] and 'bootstrap.py' in proc_cmd[-2] and json_decode(proc_cmd[-1]):
				datasync_info = json_decode(proc_cmd[-1])
				proc_status = {
					"pid": proc.pid,
					"cpu_percent": proc.cpu_percent(interval = 0.2),
					"memory_info": str(math.ceil(proc.memory_info().rss / (1024 * 1024))) + "M",
					"create_time": datetime.fromtimestamp(proc.create_time()).strftime("%Y-%m-%d %H:%M:%S"),
					"path": proc_cmd[1],
					"datasync_info": json_decode(proc_cmd[-1])
				}
				sync_processes.append(proc_status)
		status["processes"] = sync_processes
		status["active_tasks"] = to_len(sync_processes)
		return Response().success(data = status)
