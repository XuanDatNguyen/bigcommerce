from datasync.libs.db.online_mongo import OnlineMongo
from datasync.libs.utils import get_config_ini, to_str
from datasync.models.collections.activity import CollectionActivity
from datasync.models.collections.catalog import Catalog
from datasync.models.collections.category import Category
from datasync.models.collections.order import CollectionOrder
from datasync.models.collections.template import Template


class OnlineCatalog(Catalog):
	def get_db(self):
		if self._db:
			return self._db
		if not globals().get('db_mongo'):
			global db_mongo
			db_mongo = OnlineMongo()
		self._db = globals()['db_mongo']
		return self._db

class OnlineOrder(CollectionOrder):
	def get_db(self):
		if self._db:
			return self._db
		if not globals().get('db_mongo'):
			global db_mongo
			db_mongo = OnlineMongo()
		self._db = globals()['db_mongo']
		return self._db
class OnlineTemplate(Template):
	def get_db(self):
		if self._db:
			return self._db
		if not globals().get('db_mongo'):
			global db_mongo
			db_mongo = OnlineMongo()
		self._db = globals()['db_mongo']
		return self._db
class OnlineActivity(CollectionActivity):
	def get_db(self):
		if self._db:
			return self._db
		if not globals().get('db_mongo'):
			global db_mongo
			db_mongo = OnlineMongo()
		self._db = globals()['db_mongo']
		return self._db
class OnlineCategory(Category):
	def get_db(self):
		if self._db:
			return self._db
		if not globals().get('db_mongo'):
			global db_mongo
			db_mongo = OnlineMongo()
		self._db = globals()['db_mongo']
		return self._db

