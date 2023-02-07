from datasync.controllers.cart import ControllerCart

# from datasync.models.channel import ModelChannel
from datasync.libs.response import Response


class ControllerWix(ControllerCart):
	CART_TYPE = 'wix'


	def set_product_id(self, data = None):
		self._product_id = data['product'].get('productId')


	def get_webhook_product(self, data):
		self.init()
		product = self.get_channel().get_product_by_id(self._product_id)
		if product.result != Response.SUCCESS:
			return False
		return product['data']


	def get_webhook_order(self, data):
		self.init()
		order = self.get_channel().get_order_by_id(self._order_id)
		if order.result != Response.SUCCESS:
			return False
		return order['data']
