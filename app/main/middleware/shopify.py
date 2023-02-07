import base64
import hashlib
import hmac

from app.main.middleware.base import MiddlewareBase


class MiddlewareShopify(MiddlewareBase):
	MSG = ''


	def __init__(self, environ, **kwargs):
		super().__init__(environ, **kwargs)


	def verify_webhook(self, data, hmac_header):
		digest = hmac.new(SECRET, data.encode('utf-8'), hashlib.sha256).digest()
		computed_hmac = base64.b64encode(digest)

		return hmac.compare_digest(computed_hmac, hmac_header.encode('utf-8'))


	def handle(self):
		pass
