import json
import os
import random
import time
import traceback

import firebase_admin
import six
from firebase_admin import credentials
from firebase_admin import firestore

from datasync.libs.db.nosql import Nosql
from datasync.libs.utils import get_root_path, get_pub_path


class Firestore(Nosql):
	AUTO_ID_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
	ALLOW_WHERE_CONDITION = ('==', '>', '>=', '<', '<=', 'in', 'array_contains', 'array_contains_any')
	EQUAL_TO = "=="
	GREATER_THAN = ">"
	GREATER_THAN_OR_EQUAL_TO = ">="
	LEST_THAN = ">"
	LEST_THAN_OR_EQUAL_TO = "<="
	EQUAL_TO_ANY_OF_THE_FOLLOWING = "in"
	AN_ARRAY_CONTAINING = "array_contains"
	AN_ARRAY_CONTAINING_ANY = "array_contains_any"


	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._conn = None
		self._app_name = kwargs.get('app_name')


	def get_conn(self):
		if self._conn:
			return self._conn
		self._conn = self._create_connect()
		return self._conn


	def _create_connect(self):
		try:
			cred = credentials.Certificate(os.path.join(get_root_path(), 'etc', 'firestore.json'))
		except Exception:
			self.log("File docs firestore invalid")
			return None
		firebase_option = {
			'credential': cred
		}
		if self._app_name:
			firebase_option['name'] = self._app_name
		firebase_admin.initialize_app(**firebase_option)
		connect = firestore.client()

		return connect


	def refresh_connect(self):
		self.close_connect()
		self._conn = self._create_connect()
		return self._conn


	def close_connect(self):
		firebase_option = dict()
		if self._app_name:
			firebase_option['name'] = self._app_name
		firebase_admin.delete_app(firebase_admin.get_app(**firebase_option))
		self._conn = None
		return True


	def convert_data(self, data):
		if hasattr(data, 'to_dict'):
			data = getattr(data, 'to_dict')()
		return data


	def create_document(self, collection_name, _document_id = None, document_data = dict):
		if document_data.get("_id"):
			_document_id = document_data['_id']
		if not _document_id:
			_document_id = self.document_auto_id()
		document_data["_id"] = _document_id
		conn = self.get_conn()
		conn.collection(collection_name).document(_document_id).set(self.convert_data(document_data))
		return _document_id


	def set_field(self, collection_name, _document_id, update_data = dict):
		if not update_data:
			return True
		conn = self.get_conn()
		try:
			conn.collection(collection_name).document(str(_document_id)).update(self.convert_data(update_data))
			return True
		except Exception as e:
			error = traceback.format_exc()
			self.log(error)
			return False


	def update_document(self, collection_name, _document_id, update_data = dict):
		if not update_data:
			return True
		conn = self.get_conn()
		try:
			conn.collection(collection_name).document(str(_document_id)).set(self.convert_data(update_data))
			return True
		except Exception as e:
			error = traceback.format_exc()
			self.log(error)
			return False


	def get_document(self, collection_name, _document_id):
		try:
			document = self.get_conn().collection(collection_name).document(_document_id).get()
			return document.to_dict()
		except Exception as e:
			error = traceback.format_exc()
			self.log(error)
			return False


	def delete_document(self, collection_name, _document_id):
		pass


	def get_all_collection(self, collection_name):
		pass


	def find_one(self, collection_name, where = list()):
		collection_ref = self.get_conn().collection(collection_name)
		if where:
			if not isinstance(where[0], list) and not isinstance(where[0], tuple):
				where = (where,)
			for condition in where:
				collection_ref = collection_ref.where(*condition)
		collection_ref = collection_ref.limit(1)
		docs = collection_ref.get()
		if docs:
			return docs[0].to_dict()
		return ()


	def find_all(self, collection_name, where = list(), order_by = None, sort_by = None, sort = None, limit = None, offset = None, stream = False):
		collection_ref = self.get_conn().collection(collection_name)
		if where:
			if not isinstance(where[0], list) and not isinstance(where[0], tuple):
				where = (where,)
			for condition in where:
				collection_ref = collection_ref.where(*condition)
		if limit:
			collection_ref = collection_ref.limit(limit)
		if stream:
			docs = collection_ref.stream()
		else:
			docs = collection_ref.get()
			docs = tuple(map(lambda x: x.to_dict(), docs))
		return docs


	def document_auto_id(self):
		return str(int(time.time())) + "".join(random.choice(self.AUTO_ID_CHARS) for _ in six.moves.xrange(3))


	def log(self, msg):
		path = get_pub_path() + '/log/'
		if not os.path.exists(path):
			os.makedirs(path)
			os.chmod(path, 0o777)
		file_name = os.path.join(path, 'firestore.log')
		if os.path.exists(file_name) and os.path.getsize(file_name) >= 10485760:
			os.remove(file_name)

		if isinstance(msg, dict):
			msg = json.dumps(msg)
		msg = str(msg) + '\r\n'
		date_time = time.strftime('%Y/%m/%d %H:%M:%S')
		msg = date_time + ' : ' + msg
		check_exist = False
		if os.path.isfile(file_name):
			check_exist = True
		with open(file_name, 'a') as log_file:
			log_file.write(msg)
		if not check_exist and os.path.isfile(file_name):
			os.chmod(file_name, 0o777)


	def create_where_condition(self, field, value, condition = "=="):
		if not field or not value or condition not in self.ALLOW_WHERE_CONDITION:
			return False
		return (field, condition, value)


	def next(self, object):
		try:
			value = object.__next__
			return value
		except StopIteration as e:
			return False
		except Exception:
			return False
