from datasync.controllers.cart import ControllerCart
from datasync.libs.response import Response
from datasync.libs.utils import to_str


class ControllerBigcommerce(ControllerCart):
	CART_TYPE = 'bigcommerce'

	def set_product_id(self, data = None):
		self._product_id = data['product']['data']['id']

	def set_order_id(self, data = None):
		self._order_id = data['order']['data']['id']

	def get_webhook_product(self, data):
		self.init()
		product = self.get_channel().get_product_by_id(data['product']['data']['id'])
		if product.result != Response.SUCCESS:
			return False
		return product['data']

	def get_webhook_order(self, data):
		self.init()
		order = self.get_channel().get_order_by_id(data['order']['data']['id'])
		if order.result != Response.SUCCESS:
			return False
		return order['data']

	def verify_webhook(self, data = None):
		if self._state.channel.channel_type != self.CART_TYPE:
			return False
		if to_str(self._identifier).replace('stores/', '') != to_str(self._state.channel.identifier).replace('stores/', ''):
			return False
		return True
