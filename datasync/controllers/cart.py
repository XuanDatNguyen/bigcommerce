from datasync.controllers.channel import ControllerChannel
from datasync.libs.prodict import Prodict
from datasync.libs.response import Response
from datasync.models.channel import ModelChannel
from datasync.models.constructs.product import Product, ProductChannel


class ControllerCart(ControllerChannel):
	CART_TYPE = ''


	def __init__(self, data = None):
		super().__init__(data)
		self._process_type = data.get('process_type')
		self._identifier = ''
		self._product_id = ''
		self._order_id = ''
		self._channel_id = data['channel_id']
		self.set_identifier(data)


	def set_identifier(self, data = None):
		self._identifier = data['identifier']


	def set_product_id(self, data = None):
		self._product_id = data['product']['id']


	def set_order_id(self, data = None):
		self._order_id = data['order']['id']


	def verify_webhook(self, data = None):
		if self._state.channel.channel_type != self.CART_TYPE:
			return False
		if self._identifier != self._state.channel.identifier:
			return False
		return True


	def get_webhook_product(self, data):
		return data.get('product')


	def get_webhook_order(self, data):
		return data.get('order')


	def init(self, new = False):
		if self._state and self._bridge:
			return self
		model_channel = ModelChannel()
		model_channel.set_data(self._data)
		process = model_channel.get_process_by_type(ModelChannel.PROCESS_TYPE_PRODUCT, self._channel_id)
		if not process:
			return Response().success()
		self.set_sync_id(process['id'])
		return super(ControllerCart, self).init(new)


	def product_update(self, data):
		self.set_product_id(data)

		webhook_product = self.get_webhook_product(data)
		if not webhook_product:
			return Response().success()
		webhook_product = Prodict.from_dict(webhook_product)
		model_channel = ModelChannel()
		model_channel.set_data(self._data)
		process = model_channel.get_process_by_type(ModelChannel.PROCESS_TYPE_PRODUCT, data['channel_id'])
		if not process:
			return Response().success()

		self.set_sync_id(process['id'])
		self.init()
		if not self.verify_webhook(data):
			return Response().success()
		# if not self.get_channel().is_channel_default():
		# 	return Response().success()
		ext = self.get_channel().get_products_ext_export([webhook_product])
		if ext.result != Response.SUCCESS:
			return Response().success()
		convert = self.get_channel().convert_product_export(Product(**webhook_product), ext['data'])
		if convert.result != Response.SUCCESS:
			return Response().success()
		product = self.get_warehouse().get_product_map(webhook_product['id'], data['channel_id'], True)
		if not product:
			return Response().success()
		channel_data = product.channel.get(f"channel_{data['channel_id']}")
		if channel_data.publish_status == ProductChannel.PUSHING:
			return Response().success()

		self.get_warehouse().product_update(product['_id'], convert.data, current_product = product)
		return Response().success()


	def product_delete(self, data):
		self.set_product_id(data)

		model_channel = ModelChannel()
		model_channel.set_data(self._data)
		process = model_channel.get_process_by_type(ModelChannel.PROCESS_TYPE_PRODUCT, data['channel_id'])
		if not process:
			return Response().success()

		self.set_sync_id(process['id'])
		self.init()
		if not self.verify_webhook(data):
			return Response().success()
		# if not self.get_channel().is_channel_default():
		# 	return Response().success()
		product = self.get_warehouse().get_product_map(self._product_id, data['channel_id'], True)
		if not product:
			return Response().success()
		self.get_warehouse().product_deleted(product['_id'], product)
		return Response().success()


	def order_update(self, data):
		self.set_order_id(data)
		webhook_order = self.get_webhook_order(data)
		if not webhook_order:
			return Response().success()
		model_channel = ModelChannel()
		model_channel.set_data(self._data)
		process = model_channel.get_process_by_type(ModelChannel.PROCESS_TYPE_PRODUCT, data['channel_id'])
		if not process:
			return Response().success()

		self.set_sync_id(process['id'])
		self.init()
		if not self.verify_webhook(data):
			return Response().success()
		self._channel_default = self.get_channel()
		data['order_id'] = self._order_id
		data['order'] = webhook_order
		return self.sync_order(data)
	# ext = self.get_channel().get_orders_ext_export([webhook_order])
	# if ext.result != Response.SUCCESS:
	# 	return Response().success()
	# convert = self.get_channel().convert_order_export(Prodict(**webhook_order), ext['data'])
	# if convert.result != Response.SUCCESS:
	# 	return Response().success()
	# order = self.get_warehouse().get_order_map(webhook_order['id'], data['channel_id'], True)
	# if not order:
	# 	return Response().success()
	# update = self.get_warehouse().order_update(order['_id'], convert.data, current_order = order)
	# if update.result != Response.SUCCESS:
	# 	return Response().success()
	# order_updated = update.data
	# order_channel_id = order_updated.channel_id
	# channel = self.get_channel_order(order_channel_id)
	# if not channel:
	# 	return Response().success()
	# channel.update_order_to_channel(order_updated)
	# return Response().success()
