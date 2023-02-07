from datasync.controllers.controller import Controller
from datasync.models.channel import ModelChannel


class ControllerOperator(Controller):
	_route: ModelChannel


	def get_router(self):
		if self._route:
			return self._route
		self._route = ModelChannel()
		return self._route


	def stop_process(self):
		info_migration_id = self.get_router().get_sync_info()
		if not info_migration_id or not info_migration_id['pid']:
			if conn:
				response_from_subprocess(response_success())
				return
			else:
				return response_success()
		pid = to_int(info_migration_id['pid'])
		retry = 5
		while check_pid(pid) and retry > 0:
			subprocess.call(['kill', '-9', to_str(pid)])
			retry -= 1
		# if check_pid(pid):
		# 	if conn:
		# 		response_from_subprocess(response_error("Don't kill"))
		# 		return
		# 	else:
		# 		return response_error("Don't kill")
		# else:
		self._notice = json_decode(info_migration_id['notice'])
		self.init_cart()
		self.save_migration(True)
		if conn:
			response_from_subprocess(response_success())
			return
		else:
			return response_success()


	def start_process(self):
		pass


	def restart_process(self):
		pass


	def reset_process(self):
		pass
