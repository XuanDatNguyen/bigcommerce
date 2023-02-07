import os

from datasync.controllers.channel import ControllerChannel
from datasync.controllers.controller import Controller
from datasync.libs.errors import Errors
from datasync.libs.response import Response
from datasync.libs.utils import to_str, log, get_model, to_bool
from datasync.models.channel import ModelChannel
from datasync.models.channels.file import ModelChannelsProductFile
from datasync.models.channels.files.inventory import ModelChannelsInventoryFile
from datasync.models.warehouse import ModelWareHouse


class ControllerProduct(Controller):
	_bridge: ModelChannel
	_warehouse: ModelWareHouse


	def __init__(self, data = None):
		super().__init__(data)
		self._bridge = None
		self._warehouse = None
		self._product_id = data.get('product_id')


	def log(self, msg, type_log = 'exceptions'):
		prefix = os.path.join("user", to_str(self._user_id), "product", to_str(self._product_id))
		log(msg, prefix, type_log)


	def get_bridge(self):
		if self._bridge:
			return self._bridge
		self._bridge = ModelChannel()
		self._bridge.set_user_id(self._user_id)
		self._bridge.set_data(self._data)
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
		channel.set_data(self._data)
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


	def edit(self, data = None):
		product_id = data.get('product_id')
		if not product_id or not self._user_id:
			return Response().error(Errors.PRODUCT_DATA_INVALID)
		del data['product_id']
		product = self.get_model_warehouse().get_product_by_id(product_id)
		if not product:
			return Response().error(Errors.PRODUCT_NOT_EXIST)
		channel_id = data.get('channel_id')
		channels = self.get_bridge().get_all_channels(channel_id)
		errors = list()
		update_data = dict()
		for channel_data in channels:
			state = self.get_bridge().get_state_by_id(channel_data.state_id)
			'''
			channel: ModelChannel
			'''
			channel = self.get_channel(state, channel_data.sync_id)
			channel_data = channel.filter_field_product(data)
			edit_product = channel.edit_product_channel(product, channel_data)
			if edit_product.result != Response.SUCCESS:
				errors.append(edit_product.msg)
				continue
			channel_update = channel.update_product(channel_data)
			if channel_update.result != Response.SUCCESS:
				errors.append(channel_update.msg)
				continue
			channel_update_data = channel_update.data.to_dict()
			for update_key, update_value in channel_update_data:
				update_data[update_key] = update_value
		if not channel_id:
			warehouse_data = self.get_model_warehouse().filter_field_product(data)
			warehouse_update = self.get_model_warehouse().update_product(warehouse_data)
			if warehouse_update.result != Response.SUCCESS:
				errors.append(warehouse_update.msg)
			else:
				warehouse_update_data = warehouse_update.data.to_dict()
				for update_key, update_value in warehouse_update_data.items():
					update_data[update_key] = update_value
		if update_data:
			update = self.get_model_warehouse().product_update_fields(product_id, update_data)
			if update.result != Response.SUCCESS:
				errors.append(update.msg)
		return Response().success(msg = errors)


	def create(self, data = None):
		channel_id = data.get('src', dict()).get('channel_id') if data.get('src', dict()) else None
		product_id = data.get('id')
		data['id'] = None
		user_id = data.get('user_id')
		warehouse = ModelWareHouse()
		warehouse.set_user_id(user_id)
		state = warehouse.init_state()
		state.channel.id = channel_id
		state.channel.channel_type = data.get('src', dict()).get('channel_type') if data.get('src', dict()) else None
		warehouse.set_state(state)
		prepare = warehouse.prepare_products_import(data)
		data = warehouse.process_product_before_import(data)
		data = warehouse.add_channel_to_convert_product_data(data, product_id)
		check = warehouse.get_product_map(product_id, channel_id)
		if not check:
			product = warehouse.product_import(data, None, None)
			if product.result != Response.SUCCESS:
				return product
			return Response().success(product.data[0])
		return Response().success(check)


	def export(self, data = None):
		user_id = data.get('user_id')
		bulk_edit = to_bool(data.get('bulk_edit'))
		product_filters = data.get('filter', {})
		warehouse = ModelWareHouse()
		warehouse.set_user_id(user_id)
		state = warehouse.init_state()
		create_file = warehouse.create_file_upload(bulk_edit = bulk_edit)
		file_writer, file_name, open_file = create_file
		while True:
			product_mains = warehouse.get_products_filter_export(product_filters)
			if not product_mains.data:
				break
			product_ext = warehouse.get_products_ext_export(product_mains.data)
			if product_ext.result != Response.SUCCESS:
				return Response().error(Errors.PRODUCT_NOT_EXIST)
			for product in product_mains.data:
				convert = warehouse.convert_product_export(product, product_ext.data)
				warehouse.export(file_writer, convert, bulk_edit)
				state.push.process.products.id_src = product['_id']
			warehouse.set_state(state)
		finish_export = warehouse.finish_export(file_name, open_file)
		if finish_export.result != Response.SUCCESS:
			return finish_export
		return Response().success()


	def listing(self, data = None):
		user_id = data['user_id']
		channel_id = data['channel_id']
		product_ids = data['product_ids']
		product_process = self.get_bridge().get_process_by_type('product', channel_id)
		if not product_process:
			return Response().error(Errors.PROCESS_PRODUCT_NOT_EXIST)
		state = self.get_bridge().get_state_by_id(product_process['state_id'])
		channel = self.get_channel(state, product_process['id'])
		# warehouse = ModelWareHouse()
		# warehouse.set_user_id(user_id)
		return channel.listing(channel_id, product_ids)


	def product_csv_file_sample(self, data = None):
		return ModelWareHouse().construct_products_csv_file()


	def inventory_csv_file_sample(self, data = None):
		return ModelWareHouse().construct_inventories_csv_file()


	def csv_import(self, data = None):
		user_id = data['user_id']
		csv_file_url = data.get('file_url')
		model_csv = ModelChannelsProductFile()
		model_csv.set_user_id(user_id)
		setup = model_csv.setup_storage_csv()
		if setup.result != Response.SUCCESS:
			return setup
		sync_id = model_csv.get_sync_id()
		storage = model_csv.storage_data(csv_file_url)
		if storage.result != Response.SUCCESS:
			return storage
		restart = model_csv.restart_pull()
		data = {
			'user_id': user_id,
			'sync_id': sync_id,
		}
		return ControllerChannel(data).restart_pull(data)


	def inventories_export(self, data = None):
		location_id = data['location_id']
		user_id = data['user_id']
		warehouse = ModelWareHouse()
		warehouse.set_user_id(user_id)
		state = warehouse.init_state()
		create_file = warehouse.create_file_upload('inventories')
		file_writer, file_name, open_file = create_file
		while True:
			product_mains = warehouse.get_inventories_main_export(location_id)
			if not product_mains.data:
				break
			product_ext = warehouse.get_products_ext_export(product_mains.data)
			if product_ext.result != Response.SUCCESS:
				return Response().error(Errors.PRODUCT_NOT_EXIST)
			for product in product_mains.data:
				convert = warehouse.convert_inventory_export(product, product_ext.data)
				warehouse.export_inventory(file_writer, convert, location_id)
				state.push.process.products.id_src = product.id
			warehouse.set_state(state)
		finish_export = warehouse.finish_inventory_export(file_name, open_file)
		if finish_export.result != Response.SUCCESS:
			return finish_export
		return Response().success()


	def inventories_import(self, data):
		user_id = data['user_id']
		csv_file_url = data.get('file_url')
		model_csv = ModelChannelsInventoryFile()
		model_csv.set_user_id(user_id)
		model_csv.set_data_context(data)
		setup = model_csv.setup_storage_csv()
		if setup.result != Response.SUCCESS:
			return setup
		sync_id = model_csv.get_sync_id()
		storage = model_csv.storage_data(csv_file_url)
		if storage.result != Response.SUCCESS:
			return storage
		restart = model_csv.restart_pull()

		data = {
			'user_id': user_id,
			'sync_id': sync_id,
			"inventory_process": True
		}
		return ControllerChannel(data).start_pull(data)


	def create_inventory_process(self, data = None):
		channel_id = data['channel_id']
		product_process = self.get_bridge().get_process_by_type('product', channel_id)
		if not product_process:
			return Response().error(Errors.PROCESS_PRODUCT_NOT_EXIST)
		self._user_id = product_process['user_id']
		self.get_bridge().set_channel_id(product_process.channel_id)
		self.get_bridge().set_user_id(product_process.user_id)
		self.get_bridge().set_state_id(product_process.state_id)
		self.get_bridge().set_sync_id(product_process.id)
		product_state = self.get_bridge().init_state()
		process = self.get_bridge().create_inventory_process(product_state)
		if not process:
			return Response().error(Errors.PROCESS_PRODUCT_NOT_EXIST)
		after_create = self.get_channel(process['state'], process['process_id']).after_create_inventory_process(process)
		if after_create.result != Response.SUCCESS:
			return after_create
		return Response().success(process['process_id'])
