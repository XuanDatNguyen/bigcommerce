import os

from datasync.libs.response import Response
from datasync.libs.utils import get_current_time, to_str, log, json_encode
from datasync.models.constructs.state import SyncState


class ModelMode:
	_state: SyncState

	def __init__(self, data = None):
		super().__init__()
		self._sync_id = data.get('sync_id') if isinstance(data, dict) else None
		self._state = None
		self._mode = None
		self._user_id = None
		self._response = Response()


	def set_state(self, state):
		self._state = state


	def set_user_id(self, user_id):
		self._user_id = user_id


	def set_sync_id(self, sync_id):
		self._sync_id = sync_id


	def get_sync_state(self, sync_id):
		pass


	def delete_sync_state(self, sync_id):
		pass


	def update_state(self, _sync_id, state = None, pid = None, mode = None, status = None, finish = False, clear_entity_warning = False):
		pass


	def set_status_sync(self, sync_id, status):
		pass

	def set_state_id_for_sync(self, sync_id, state_id):
		pass


	def get_info_sync(self, sync_id):
		pass


	def get_app_mode_limit(self):
		pass


	def search_demo_error(self, where):
		pass


	def create_demo_error(self, data):
		pass


	def create_channel(self, channel_id_exist = None):
		pass


	def delete_channel(self, channel_id):
		pass


	def update_channel(self, channel_id, **kwargs):
		return True


	def create_product_sync_process(self, state_id, channel_id_exist = None):
		pass


	def create_order_sync_process(self, state_id, channel_id):
		pass


	def create_inventory_sync_process(self, state_id, channel_id):
		pass


	def delete_sync_process(self, sync_id):
		pass


	def is_channel_exist(self, channel_type, identifier):
		pass


	def get_channel_create_data(self):
		api_info = self._state.channel.config.api
		if hasattr(api_info, 'to_json'):
			api_info = getattr(api_info, 'to_json')()
		if isinstance(api_info, dict):
			api_info = json_encode(api_info)
		channel_data = {
			'type': self._state.channel.channel_type,
			'url': self._state.channel.url,
			'identifier': self._state.channel.identifier,
			'name': self._state.channel.name,
			'user_id': self._user_id,
			'api': api_info,
			'created_at': get_current_time(),
			'updated_at': get_current_time(),
			'status': 'connected'
		}
		return channel_data


	def get_process_create_data(self, state_id, process_type = 'product'):
		channel_data = {
			'state_id': state_id,
			'created_at': get_current_time(),
			'updated_at': get_current_time(),
			'user_id': self._user_id,
			'channel_id': self._state.channel.id,
			'status': 'new',
			'type': process_type
		}
		return channel_data


	def get_entity_limit(self):
		pass


	def get_sync_info(self, sync_id):
		pass


	def save_sync(self, sync_id, **kwargs):
		pass


	def  get_all_channels(self):
		pass


	def log(self, msg, log_type = 'exceptions'):
		prefix = to_str(self._user_id)
		if self._sync_id:
			prefix = os.path.join(prefix, 'channel', self._sync_id)

		log(msg, prefix, log_type)


	def get_warehouse_locations(self):
		pass


	def get_warehouse_location_default(self):
		pass


	def get_warehouse_location_fba(self):
		pass


	def get_process_file(self):
		pass


	def get_process_by_type(self, channel_id, process_type):
		pass


	def get_process_by_id(self, process_id):
		pass


	def get_scheduler_info(self, scheduler_id):
		pass


	def create_scheduler_process(self, process_id):
		pass


	def set_last_time_scheduler(self, scheduler_id):
		pass


	def get_user_plan(self):
		pass


	def try_upgrade_plan(self):
		pass


	def get_channel_default(self):
		pass


	def get_channel_by_id(self, channel_id):
		pass


	def get_user_info(self):
		return {}


	def get_category_path(self, channel_type, type_search, params):
		pass


	def create_refresh_process_scheduler(self, channel_id):
		pass


	def after_import(self, channel_id, process_id):
		pass