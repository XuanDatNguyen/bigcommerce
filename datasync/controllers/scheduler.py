from datasync.controllers.channel import ControllerChannel
from datasync.controllers.controller import Controller
from datasync.libs.errors import Errors
from datasync.libs.response import Response
from datasync.libs.utils import get_model, to_int, check_pid
from datasync.models.channel import ModelChannel


class ControllerScheduler(Controller):
	_bridge: ModelChannel
	_channel: ModelChannel


	def __init__(self, data = None):
		super().__init__(data)
		self._bridge = None
		self._channel = None
		self._channel_id = data.get("channel_id") if data else None


	def get_bridge(self):
		if self._bridge:
			return self._bridge
		self._bridge = ModelChannel()
		self._bridge.set_channel_id(self._channel_id)
		self._bridge.set_user_id(self._user_id)
		self._bridge.set_data(self._data)
		return self._bridge


	def get_channel(self, state, sync_id):
		channel_type = state.channel.channel_type
		channel_version = state.channel.config.version
		channel_name, channel_class = self.get_bridge().get_channel(channel_type, channel_version)
		if not channel_name:
			channel = ModelChannel()
		else:
			channel = get_model(channel_name, class_name = channel_class)
		if not channel:
			return None
		channel.set_state(state)
		channel.set_sync_id(sync_id)
		channel.set_state_id(state._id)
		channel.set_db(self.get_bridge().get_db())
		channel.set_user_id(self._user_id)
		if state.channel.name:
			channel.set_name(state.channel.name)
		if state.channel.id:
			channel.set_id(state.channel.id)
		if state.channel.identifier:
			channel.set_identifier(state.channel.identifier)
		if state.channel.url:
			channel.set_channel_url(state.channel.url)
		if state.channel.channel_type:
			channel.set_channel_type(state.channel.channel_type)
		return channel


	def scheduler(self, data = None):
		process_id = to_int(data['sync_id'])
		if to_int(process_id) != to_int(data['sync_id']):
			return Response().error(Errors.SCHEDULER_NOT_EXIST)
		process = self.get_bridge().get_process_by_id(process_id)
		if process:
			state = self.get_bridge().get_model_state().get(process['state_id'])
			if state.get('process') and state['process'].get('pid'):
				pid = state['process'].get('pid')
				if check_pid(pid):
					return Response().success()
			pid = process['pid']
			if check_pid(pid):
				return Response().success()
		# self.get_bridge().set_last_time_scheduler(scheduler_id)
		return ControllerChannel(data).start_scheduler(data)
