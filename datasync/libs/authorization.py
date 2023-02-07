import time

import jwt

from datasync.libs.utils import get_config_ini, to_bool


class Authorization:
	PREFIX = 'lit'


	def __init__(self, **kwargs):
		self._private_key = kwargs.get('private_key', get_config_ini('local', 'private_key'))
		self._user_id = kwargs.get('user_id')


	def encode(self, data = None):
		if not data:
			data = dict()
		data['time'] = str(int(time.time()))
		data['user_id'] = self._user_id
		jwt_token = jwt.encode(data, self._private_key, algorithm = 'HS256')
		if isinstance(jwt_token, bytes):
			jwt_token = jwt_token.decode()
		return f"{self.PREFIX} {jwt_token}"


	def decode(self, authorization):
		if not authorization or not isinstance(authorization, str):
			return False
		authorization = authorization.split(' ')
		if len(authorization) != 2 and authorization[0] != self.PREFIX:
			return False
		try:
			data = jwt.decode(authorization[1], self._private_key, algorithms = ['HS256'])
		except jwt.exceptions.InvalidSignatureError as e:
			return False
		except Exception as e:
			return False
		return data


	def get_user_id(self, authorization):
		data = self.decode(authorization)
		if not data:
			return self.get_user_id_default()
		return data.get('user_id', self.get_user_id_default())


	def get_user_id_from_headers(self, flask_request):
		authorization = flask_request.environ.get('HTTP_AUTHORIZATION')
		if not authorization:
			return self.get_user_id_default()
		return self.get_user_id(authorization)


	def get_user_id_default(self):
		if to_bool(get_config_ini('local', 'is_local')):
			return get_config_ini('local', 'user_id_default')
		return 0
