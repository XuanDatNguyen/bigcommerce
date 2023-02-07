from datasync.libs.prodict import Prodict
from datasync.libs.utils import dict_key_to_str


class Response(Prodict):
	SUCCESS = 'success'
	DELETED = 'deleted'
	PROCESS = 'process'
	ERROR = 'error'
	WARNING = 'warning'
	FINISH = 'finish'
	SKIP = 'skip'
	STOP_EXPORT = 'stop_export'
	STOP = 'stop'
	SKIP_ERROR = 'skip_error'


	def __init__(self, **kwargs):
		self.result = ''
		self.msg = ''
		self.data = ''
		self.code = ''
		super().__init__(**kwargs)


	def success(self, data = None, msg = '', code = None, **kwargs):
		return self.create_response(self.SUCCESS, msg = msg, data = data, code = code, kwargs = kwargs)


	def error(self, code = None, msg = None, **kwargs):
		return self.create_response(self.ERROR, msg = msg, code = code, kwargs = kwargs)


	def stop(self, code = None, msg = None, **kwargs):
		return self.create_response(self.STOP, msg = msg, code = code, kwargs = kwargs)


	def warning(self, code = None, msg = None, **kwargs):
		return self.create_response(self.WARNING, msg = msg, code = code, kwargs = kwargs)


	def process(self, data = None, msg = None, code = None, **kwargs):
		return self.create_response(self.PROCESS, msg = msg, data = data, code = code, kwargs = kwargs)


	def skip(self, data = None, msg = None, code = None, **kwargs):
		return self.create_response(self.SKIP, msg = msg, data = data, code = code, kwargs = kwargs)


	def finish(self, data = None, msg = None, code = None, **kwargs):
		return self.create_response(self.FINISH, msg = msg, data = data, code = code, kwargs = kwargs)


	def reset_response(self):
		self.result = None
		self.msg = None
		self.data = None
		self.code = None


	def create_response(self, result = None, msg = None, data = None, code = None, **kwargs):
		self.reset_response()
		self.result = result
		self.msg = msg
		if isinstance(data, dict):
			data = dict_key_to_str(data)
		try:
			self.data = data
		except Exception as e:
			d = 3
		self.code = code
		return Prodict(**self.to_dict())
