from werkzeug.wrappers import Response

from datasync.libs.authorization import Authorization
from datasync.libs.utils import *


class Auth():
	def __init__(self, app):
		self.app = app


	def __call__(self, environ, start_response):
		if is_local():
			return self.app(environ, start_response)
		request_ip = environ.get('REMOTE_ADDR')
		allow_ips = get_config_ini('local', 'allow_ips')
		if allow_ips and request_ip not in allow_ips.split('|'):
			res = Response(json_encode(response_error('403 Forbidden')), mimetype = 'text/plain', status = 403)
			return res(environ, start_response)
		authorization_key = environ.get('HTTP_AUTHORIZATION')
		if not authorization_key:
			res = Response(json_encode(response_error('Authorization failed. Please add AUTHORIZATION to header request')), mimetype = 'text/plain', status = 401)
			return res(environ, start_response)
		authorization_data = Authorization(private_key = get_config_ini('local', 'private_key')).decode(authorization_key)
		if not authorization_data:
			res = Response(json_encode(response_error('Authorization failed.')), mimetype = 'text/plain', status = 401)
			return res(environ, start_response)
		return self.app(environ, start_response)


	def authorize(self, time_request, hmac):
		private_key = get_config_ini('local', 'private_key')
		if not private_key:
			return False
		return to_str(hmac) == hash_hmac('sha256', time_request, private_key)
