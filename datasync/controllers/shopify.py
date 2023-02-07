from datasync.controllers.cart import ControllerCart


class ControllerShopify(ControllerCart):
	CART_TYPE = 'shopify'
	def verify_webhook(self, data = None):
		if self._state.channel.channel_type != self.CART_TYPE:
			return False
		if self._identifier.replace('.myshopify.com', '') != self._state.channel.identifier.replace('.myshopify.com', ''):
			return False
		return True
