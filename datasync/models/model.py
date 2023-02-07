from datasync.libs.utils import *


class Model:

	def __init__(self, **kwargs):
		self._data = Prodict(**kwargs)
		self._user_id = kwargs.get('user_id')
