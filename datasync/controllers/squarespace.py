from datasync.controllers.cart import ControllerCart
from datasync.libs.response import Response


class ControllerSquarespace(ControllerCart):
	CART_TYPE = 'squarespace'


	def set_order_id(self, data = None):
		self._order_id = data['order']['orderId']


	def get_webhook_order(self, data):
		self.init()
		order = self.get_channel().get_order_by_id(data['order']['orderId'])
		if order.result != Response.SUCCESS:
			return False
		return order['data']
