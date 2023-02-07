from datetime import datetime, timedelta

from datasync.controllers.channel import ControllerChannel
from datasync.controllers.controller import Controller
from datasync.libs.errors import Errors
from datasync.libs.response import Response
from datasync.libs.utils import to_int, check_pid
from datasync.models.channel import ModelChannel, get_model
from datasync.models.constructs.order import Order
from datasync.models.warehouse import ModelWareHouse


class ControllerOrder(Controller):
	_bridge: ModelChannel or None
	_channel: ModelChannel or None
	_channel_default: ModelChannel or None


	def __init__(self, data = None):
		super().__init__(data)
		self._bridge = None
		self._channel = None
		self._order_channels = dict()
		self._channel_default = None
		self._channel_id = data.get("channel_id") if data else None


	def get_bridge(self):
		if self._bridge:
			return self._bridge
		self._bridge = ModelChannel()
		self._bridge.set_channel_id(self._channel_id)
		self._bridge.set_user_id(self._user_id)
		self._bridge.set_data(self._data)
		return self._bridge


	def get_warehouse(self, user_id, channel_id = None, state = None):
		warehouse = ModelWareHouse()
		warehouse.set_state(state)
		warehouse.set_channel_id(channel_id)
		# warehouse.set_db(self.get_bridge().get_db())
		# warehouse.set_is_test(self._test)
		# warehouse.set_state_id(self._state_id)
		warehouse.set_user_id(user_id)
		# warehouse.set_date_requested(self._date_requested)
		# warehouse.set_process_type(self._process_type)
		# warehouse.set_is_inventory_process(self._is_inventory_process)
		return warehouse


	# def get_channel_by_state(self, state = None, sync_id = None):
	# 	channel_type = state.channel.channel_type
	# 	channel_version = state.channel.config.version
	# 	channel_name, channel_class = self.get_bridge().get_channel(channel_type, channel_version)
	# 	if not channel_name:
	# 		channel = ModelChannel()
	# 	else:
	# 		channel = get_model(channel_name, class_name = channel_class)
	# 	if not channel:
	# 		return None
	# 	channel.set_state(state)
	# 	channel.set_sync_id(sync_id)
	# 	channel.set_state_id(state._id)
	# 	channel.set_db(self.get_bridge().get_db())
	# 	channel.set_user_id(self._user_id)
	# 	if state.channel.name:
	# 		channel.set_name(state.channel.name)
	# 	if state.channel.id:
	# 		channel.set_id(state.channel.id)
	# 	if state.channel.identifier:
	# 		channel.set_identifier(state.channel.identifier)
	# 	if state.channel.url:
	# 		channel.set_channel_url(state.channel.url)
	# 	if state.channel.channel_type:
	# 		channel.set_channel_type(state.channel.channel_type)
	# 	return channel

	def get_channel_default(self):
		if self._channel_default:
			return self._channel_default
		channel = self.get_bridge()
		channel_default_data = channel.get_channel_default()
		if not channel_default_data:
			return False
		channel_default_process = channel.get_process_by_type(ModelChannel.PROCESS_TYPE_PRODUCT, channel_default_data['id'])
		state_default = channel.get_state_by_id(channel_default_process['state_id'])
		channel_version = state_default.channel.config.version
		channel_name, channel_class = self.get_bridge().get_channel(channel_default_data['type'], channel_version)
		if not channel_name:
			self._channel_default = ModelChannel()
		else:
			self._channel_default = get_model(channel_name, class_name = channel_class)
		if not self._channel_default:
			return None
		self._channel_default.set_state(state_default)
		self._channel_default.set_sync_id(channel_default_process['id'])
		self._channel_default.set_state_id(channel_default_process['state_id'])
		self._channel_default.set_is_inventory_process(False)
		self._channel_default.set_db(self.get_bridge().get_db())
		self._channel_default.set_user_id(self._user_id)
		self._channel_default.set_channel_id(channel_default_data['id'])
		if state_default.channel.name:
			self._channel_default.set_name(state_default.channel.name)
		if state_default.channel.id:
			self._channel_default.set_id(state_default.channel.id)
		if state_default.channel.identifier:
			self._channel_default.set_identifier(state_default.channel.identifier)
		if state_default.channel.url:
			self._channel_default.set_channel_url(state_default.channel.url)
		if state_default.channel.channel_type:
			self._channel_default.set_channel_type(state_default.channel.channel_type)
		self._channel_default.set_date_requested(self._date_requested)
		self._channel_default.set_data(self._data)
		return self._channel_default


	def create_order_process(self, data = None):
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
		process = self.get_bridge().create_order_process(product_state)
		if not process:
			return Response().error(Errors.PROCESS_ORDER_NOT_CREATE)
		after_create = self.get_channel_by_state(process['state'], process['process_id']).after_create_order_process(process)
		if after_create.result != Response.SUCCESS:
			return after_create
		return Response().success(process['process_id'])


	def create(self, data = None):
		channel_id = data.get('src', dict()).get('channel_id')
		order_id = data.get('id')
		# data['id'] = None
		user_id = data.get('user_id')
		warehouse = ModelWareHouse()
		warehouse.set_user_id(user_id)
		state = warehouse.init_state()
		state.channel.id = channel_id
		state.channel.channel_type = data.get('src', dict()).get('channel_type')
		warehouse.set_state(state)
		data = warehouse.process_order_before_import(data)
		data = warehouse.add_channel_to_convert_order_data(data, order_id)
		check = warehouse.get_order_map(order_id, channel_id)
		if check:
			return Response().success(check)
		order = warehouse.order_import(data, data, None)
		if order.result != Response.SUCCESS:
			return order
		id_desc, order_data = order['data']
		if not state.channel.default:
			channel_default = self.get_channel_default(state)
			if channel_default:
				warehouse.set_channel_id(channel_default.get_channel_id())
				warehouse.set_state(channel_default.get_state())
				order_ext = warehouse.get_orders_ext_export([data])
				convert_order = warehouse.convert_order_export(data, order_ext['data'], channel_id = channel_default.get_channel_id())
				if convert_order.result != Response.SUCCESS:
					warehouse.after_create_order_sync(id_desc, channel_id, convert_order, data)
				try:
					order_import = channel_default.order_import(convert_order['data'], None, None)
				except Exception:
					self.log_traceback()
					order_import = Response().error()
				warehouse.after_create_order_sync(id_desc, channel_id, order_import, data)
				if order_import.result == Response.SUCCESS:
					channel_default.after_order_import(order_import.data[0], data, None, None)
		return Response().success(order.data)


	def scheduler(self, data = None):
		scheduler_id = data['cron_id']
		user_id = data['user_id']
		scheduler_info = self.get_bridge().get_scheduler_info(scheduler_id)
		if not scheduler_info:
			return Response().error(Errors.SCHEDULER_NOT_EXIST)
		process_id = scheduler_info['process']
		if to_int(process_id) != to_int(data['sync_id']):
			return Response().error(Errors.SCHEDULER_NOT_EXIST)
		process = self.get_bridge().get_process_by_id(process_id)
		if process:
			pid = process['pid']
			if check_pid(pid):
				return Response().success()
		self.get_bridge().set_last_time_scheduler(scheduler_id)
		return ControllerChannel(data).start_pull_update(data)


	def export(self, data = None):
		user_id = data.get('user_id')
		warehouse = ModelWareHouse()
		warehouse.set_user_id(user_id)
		state = warehouse.init_state()
		create_file = warehouse.create_file_upload('orders')
		file_writer, file_name, open_file = create_file
		start_date = datetime.strptime(data['start_date'], "%Y-%m-%d")
		end_date = datetime.strptime(data['end_date'], "%Y-%m-%d")
		while True:
			order_mains = warehouse.get_orders_main_export(start_date = start_date.strftime("%Y-%m-%d 00:00:00"), end_date = end_date.strftime("%Y-%m-%d 23:59:59"))
			if not order_mains.data:
				break
			product_ext = warehouse.get_orders_ext_export(order_mains.data)
			if product_ext.result != Response.SUCCESS:
				return Response().error(Errors.PRODUCT_NOT_EXIST)
			for order in order_mains.data:
				# convert = warehouse.convert_order_export(order, product_ext.data)
				warehouse.export_order(file_writer, order)
				state.push.process.orders.id_src = order['_id']
			warehouse.set_state(state)
		finish_export = warehouse.finish_order_csv_export(file_name, open_file)
		if finish_export.result != Response.SUCCESS:
			return finish_export
		return Response().success()


	def update(self, data = None):
		order_ids = data['order_ids']
		if order_ids and not isinstance(order_ids, list):
			order_ids = [order_ids]
		user_id = data['user_id']
		warehouse = self.get_warehouse(user_id)
		order_mains = warehouse.get_order_by_ids(order_ids)
		if order_mains.result != Response.SUCCESS or not order_mains['data']:
			return Response().success()
		warehouse_orders = order_mains['data']
		channel_default = self.get_channel_default()
		for warehouse_order in warehouse_orders:
			channel_id = warehouse_order.channel_id
			order_id = warehouse_order['_id']
			channel = self.get_channel_order(channel_id)
			if not channel:
				continue
			channel_state = channel.get_state()
			warehouse.set_state(channel_state)
			order_channel = warehouse_order.channel.get(f'channel_{channel_id}')
			order_main = channel.get_order_by_id(order_channel.order_id)
			if order_main.result != Response.SUCCESS or not order_main.data:
				continue
			order = order_main.data
			order_ext = channel.get_orders_ext_export([order])
			if order_ext.result != Response.SUCCESS:
				continue
			convert_order = channel.convert_order_export(order, order_ext.data, channel_id)
			if convert_order.result != Response.SUCCESS:
				continue
			channel_order_data = warehouse.add_channel_to_convert_order_data(convert_order.data, order_channel.order_id)

			update = warehouse.order_update(order_id, channel_order_data)
			if update.result != Response.SUCCESS:
				continue
			if not channel_default:
				continue
			order_update = update.data
			order_ext = warehouse.get_orders_ext_export([order_update])
			convert_order = warehouse.convert_order_export(order_update, order_ext.data, channel_id = channel_default.get_channel_id())
			if convert_order.result != Response.SUCCESS:
				warehouse.after_create_order_sync(order_id, channel_default.get_channel_id(), convert_order, order_update)
				continue
			convert_order_data = convert_order['data']
			if convert_order_data.link_status != Order.LINKED:
				import_data = Response().error(msg = 'Product in order not link')
				warehouse.after_create_order_sync(order_id, channel_default.get_channel_id(), import_data, order)
				continue
			setting_order = True if channel_state.channel.config.setting.get('order', {}).get('status') != 'disable' else False
			channel_default.channel_order_sync_inventory(convert_order['data'], setting_order)
			if setting_order:
				try:
					order_import = channel_default.order_import(None, convert_order['data'], None)
				except Exception:
					self.log_traceback()
					order_import = Response().error()
				warehouse.after_create_order_sync(order_id, channel_default.get_channel_id(), order_import, convert_order['data'])
				if order_import.result != Response.SUCCESS:
					continue
				channel_default.after_order_import(order_import.data[0], order, None, None)
		return Response().success()
