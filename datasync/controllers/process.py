import subprocess

from PIL.ImageFile import ERRORS

from datasync.controllers.channel import ControllerChannel
from datasync.libs.response import Response
from datasync.libs.utils import to_str, check_pid, to_int
from datasync.models.channel import ModelChannel


class ControllerProcess(ControllerChannel):
	def stop_process(self, data = None):
		sync_id = data.get('sync_id')
		self.init()
		sync_info = self.get_warehouse().get_sync_info(sync_id)
		if sync_info.get('user_id'):
			self.set_user_id(sync_info['user_id'])
		if sync_info and sync_info.get('pid'):
			pid = to_int(sync_info['pid'])
			retry = 5
			while check_pid(pid) and retry > 0:
				subprocess.call(['kill', '-9', to_str(pid)])
				retry -= 1
			self.log('Exit process {}'.format(pid), 'process')
		state = self.get_bridge().get_model_state().get(sync_info['state_id'])
		if state.get('process') and state['process'].get('pid'):
			pid = state['process'].get('pid')
			retry = 5
			while check_pid(pid) and retry > 0:
				subprocess.call(['kill', '-9', to_str(pid)])
				retry -= 1
			self.log('Exit process {}'.format(pid), 'process')
		self.save_sync(pid = None, status = ModelChannel.PROCESS_STOPPED)
		state_id = sync_info['state_id']
		self.get_warehouse().set_state_id(state_id)
		state = self.get_warehouse().init_state()
		action = state.resume.action
		update = {
			f"{action}.resume.process": ModelChannel.PROCESS_STOPPED,
			'running': False,
			'process.status': ModelChannel.PROCESS_STOPPED
		}
		self.get_warehouse().get_model_state().update(state_id, update)
		return Response().success()


	def reset_process(self, data = None):
		pass


	def start(self, data = None):
		self.init()
		action = self._state.resume.action
		if action not in self.ALLOW_ACTION:
			return Response().error(ERRORS.ACTION_INVALID)
		return getattr(self, 'start_{}'.format(action))()


	def refresh(self, data = None):
		self.init()
		process_type = self._process_type
		if hasattr(self, f'refresh_{process_type}'):
			return getattr(self, f'refresh_{process_type}')(data)
		return Response().success()