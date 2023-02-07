from datasync.controllers.cart import ControllerCart
from datasync.models.channel import ModelChannel


class ControllerWoocommerce(ControllerCart):
	CART_TYPE = 'woocommerce'


	def set_identifier(self, data = None):
		self._identifier = str(ModelChannel().channel_url_to_identifier(data['identifier'])).strip('/')
