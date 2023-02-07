import logging
import os
import random
import traceback

import six

from datasync.libs.utils import log


class Nosql:
	NAME = 'Nosql'
	AUTO_ID_CHARS = "abcdefghijklmnopqrstuvwxyz0123456789"


	def __init__(self, **kwargs):
		self._conn = None


	def get_conn(self, user_id):
		return self._create_connect(user_id)

		if self._conn:
			return self._conn
		self._conn = self._create_connect()
		return self._conn


	def _create_connect(self, user_id):
		return False


	def refresh_connect(self):
		self.close_connect()
		self._conn = self._create_connect()
		return self._conn


	def close_connect(self):
		return True


	def create_document(self, user_id, collection_name, _document_id = None, document_data = dict):
		return 0


	def set_field(self, user_id, collection_name, _document_id, update_data = dict):
		return True


	def update_document(self, user_id, collection_name, _document_id, update_data = dict):
		return True


	def update_many_document(self, user_id, collection_name, where, update_data = dict):
		return True


	def get_document(self, user_id, collection_name, _document_id):
		return False


	def delete_document(self, user_id, collection_name, _document_id):
		pass


	def get_all_collection(self, collection_name):
		pass


	def find_one(self, user_id, collection_name, where = list()):
		return ()


	def find_all(self, user_id, collection_name, where = list(), order_by = None, sort = None, limit = None, pages = None, stream = False, select_fields = None):
		return ()


	def count_document(self, user_id, collection_name, where = list()):
		return 0


	def log(self, msg):
		log(msg, os.path.join('db', self.NAME))


	def log_traceback(self):
		error = traceback.format_exc()
		self.log(error)


	def create_where_condition(self, field, value, condition = "=="):
		return False


	def next(self, object):
		try:
			value = object.__next__
			return value
		except StopIteration as e:
			return False
		except Exception:
			return False


	def document_auto_id(self):
		return "".join(random.choice(self.AUTO_ID_CHARS) for _ in six.moves.xrange(3))


	def unset(self, user_id, collection_name, _document_id, fields):
		return True


	def unset_many(self, user_id, collection_name, where, fields):
		return True

