import pymongo

from datasync.libs.db.mongo import Mongo
from datasync.libs.utils import get_config_ini


class OnlineMongo(Mongo):
	def __init__client__(self):
		driver = get_config_ini('online_mongo', 'db_driver')
		password = self.encode_password(get_config_ini('online_mongo', 'db_password'))
		driver = driver.replace('<password>', password)
		self._client = pymongo.MongoClient(driver)

	def _create_connect(self, user_id):
		database_name = f"{get_config_ini('online_mongo', 'db_name')}_{user_id}"

		connect = getattr(self._get_client(), database_name)

		return connect