import importlib

from datasync.libs.db.mongo import Mongo
from datasync.libs.prodict import Prodict
from datasync.libs.utils import get_config_ini, BASE_DIR, to_str


class ModelCollection:
	_db: Mongo
	COLLECTION_NAME = 'catalog_1'


	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._user_id = kwargs.get('user_id')
		self._collection_name = None
		self._document_id = None
		self._data = None
		self._db = kwargs.get('mongo_db', None)


	def get_db(self):
		if self._db:
			return self._db
		if not globals().get('db_mongo'):
			global db_mongo
			db_mongo = Mongo()
		self._db = globals()['db_mongo']
		return self._db

		database_engine = get_config_ini('local', 'database_engine', 'firestore')
		db_name = "{}.{}.{}.{}".format(BASE_DIR, 'libs', 'db', database_engine)
		module_class = importlib.import_module(db_name)
		model_class = getattr(module_class, database_engine.capitalize())
		self._db = model_class(database_name = get_config_ini(database_engine, 'db_name') + "_" + to_str(self._user_id))
		return self._db


	def set_db(self, db):
		self._db = db


	def set_user_id(self, user_id):
		self._user_id = user_id


	def get_collection(self, collection_name, where = list, order_by = None, sort_by = None, sort = None, limit = None, offset = None, stream = False):
		return self.get_db().find_all(collection_name, where, order_by, sort_by, sort, limit, offset, stream)


	def create_where_condition(self, field, value, condition = "=="):
		return self.get_db().create_where_condition(field, value, condition)


	def next(self, obj):
		return self.get_db().next(obj)


	def set_data(self, data):
		self._data = data


	def set_document_id(self, document_id):
		self._document_id = document_id


	def set_collection_name(self, collection_name):
		self._collection_name = collection_name


	def get_collection_name(self):
		if self._collection_name:
			return self._collection_name
		return self.COLLECTION_NAME


	def create(self, document_data = dict, document_id = None):
		return self.get_db().create_document(self._user_id, self.get_collection_name(), document_id, document_data)


	def create_many(self, document_data: list):
		return self.get_db().create_many_document(self._user_id, self.get_collection_name(), document_data)


	def update(self, document_id, update_data = dict, raw = False):
		if raw:
			return self.get_db().update_raw_document(self._user_id, self.get_collection_name(), document_id, update_data)
		return self.get_db().update_document(self._user_id, self.get_collection_name(), document_id, update_data)


	def update_many(self, where, update_data = dict, raw = False):
		if raw:
			return self.get_db().update_raw_many_document(self._user_id, self.get_collection_name(), where, update_data)
		return self.get_db().update_many_document(self._user_id, self.get_collection_name(), where, update_data)


	def update_field(self, document_id, field, value):
		update_data = {
			field: value
		}
		return self.get_db().set_field(self._user_id, self.get_collection_name(), document_id, update_data)


	def update_fields(self, document_id, update_data):
		return self.get_db().set_field(self._user_id, self.get_collection_name(), document_id, update_data)


	def get(self, _document_id, select_fields = None):
		entity = self.get_db().get_document(self._user_id, self.get_collection_name(), _document_id, select_fields)
		if entity:
			entity = Prodict.from_dict(entity)
		return entity


	def set(self, document_id, collection_data):
		return self.create(collection_data, document_id)


	def delete(self, document_id):
		return self.get_db().delete_document(self._user_id, self.get_collection_name(), document_id)


	def delete_all(self):
		return self.get_db().delete_all(self._user_id, self.get_collection_name())


	def delete_many_document(self, where):
		return self.get_db().delete_many_document(self._user_id, self.get_collection_name(), where)


	def all(self):
		return self.get_db().get_all_collection(self.get_collection_name())


	def find(self, field, value, select_fields = None):
		'''

		:return:
		'''
		where = self.create_where_condition(field, value)
		find = self.get_db().find_one(self._user_id, self.get_collection_name(), where, select_fields)
		if find:
			find = Prodict(**find)
		return find


	def find_all(self, where = (), order_by = None, sort = None, limit = None, pages = None, stream = False, select_fields = None):
		'''

		:param where: list of self.create_where_condition()
		:param order_by:
		:param sort:
		:param limit:
		:param pages:
		:param stream:
		:return: generator
		'''
		find = self.get_db().find_all(self._user_id, self.get_collection_name(), where, order_by, sort, limit, pages, stream, select_fields)
		if find:
			find = list(map(lambda x: Prodict(**x), find))
		return find


	def count(self, where = ()):
		return self.get_db().count_document(self._user_id, self.get_collection_name(), where)


	def select_aggregate(self, query):
		return self.get_db().select_aggregate(self._user_id, self.get_collection_name(), query)


	def save(self, data = None):
		if not data:
			data = self._data
		if not self._data:
			return False
		if not self._document_id:
			return self.create(data)
		return self.update(self._document_id, data)


	def unset(self, document_id, fields):
		return self.get_db().unset(self._user_id, self.get_collection_name(), document_id, fields)


	def unset_many(self, where, fields):
		return self.get_db().unset_many(self._user_id, self.get_collection_name(), where, fields)


	def create_index(self, field, option = 1, index_name = None):
		return self.get_db().create_index(self._user_id, self.get_collection_name(), field, option, index_name)


	def create_compound_index(self, fields, option = 1, index_name = None):
		return self.get_db().create_compound_index(self._user_id, self.get_collection_name(), fields, option, index_name)


	def create_text_index(self, fields, index_name = None):
		return self.get_db().create_text_index(self._user_id, self.get_collection_name(), fields, index_name)


	def list_index(self):
		return self.get_db().list_index(self._user_id, self.get_collection_name())


	def get_index(self, name):
		name = to_str(name)
		if not name:
			return False
		list_index = self.list_index()
		if not list_index or not list_index.get(name):
			return False
		return list_index.get(name)


	def drop_index(self, name):
		return self.get_db().drop_index(self._user_id, self.get_collection_name(), name)
