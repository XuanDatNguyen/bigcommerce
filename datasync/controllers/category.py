import os

from datasync.controllers.controller import Controller
from datasync.libs.response import Response
from datasync.libs.utils import to_str, log, get_model
from datasync.models.channel import ModelChannel
from datasync.models.warehouse import ModelWareHouse


class ControllerCategory(Controller):
	_bridge: ModelChannel
	_warehouse: ModelWareHouse


	def __init__(self, data = None):
		super().__init__(data)
		self._bridge = None
		self._warehouse = None
		self._product_id = data.get('product_id')


	def log(self, msg, type_log = 'exceptions'):
		prefix = os.path.join('user', to_str(self._user_id), "category", to_str(self._product_id))
		log(msg, prefix, type_log)


	def get_bridge(self):
		if self._bridge:
			return self._bridge
		self._bridge = ModelChannel()
		self._bridge.set_user_id(self._user_id)
		return self._bridge


	def get_model_warehouse(self):
		if self._warehouse:
			return self._warehouse
		self._warehouse = ModelWareHouse()
		self._warehouse.set_user_id(self._user_id)
		self._warehouse.set_db(self.get_bridge().get_db())
		return self._warehouse


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


	def create(self, data = None):
		channel_id = data.get('src', dict()).get('channel_id')
		category_id = data.get('id')
		data['id'] = None
		user_id = data.get('user_id')
		warehouse = ModelWareHouse()
		warehouse.set_user_id(user_id)
		state = warehouse.init_state()
		state.channel.id = channel_id
		state.channel.channel_type = data.get('src', dict()).get('channel_type')
		warehouse.set_state(state)
		data = warehouse.process_category_before_import(data)
		data = warehouse.add_channel_to_convert_category_data(data, category_id)
		check = warehouse.get_category_map(category_id, channel_id)
		if not check:
			category = warehouse.category_import(data, None, None)
			if category.result != Response.SUCCESS:
				return category
			return Response().success(category.data)
		return Response().success(check)
