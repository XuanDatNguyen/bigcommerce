import time

from datasync.models.collection import ModelCollection
from datasync.models.constructs.activity import ActivityNotification, ActivityProcess, ActivityRecent


class CollectionActivity(ModelCollection):
	COLLECTION_NAME = 'activities'


	def before_create(self, data, **kwargs):
		data.activity_type = kwargs.get('activity_type')
		data.code = kwargs.get('code')
		data.channel_id = kwargs.get('channel_id')
		data.description = kwargs.get('description')
		data.date_requested = kwargs.get('date_requested')
		data.result = kwargs.get('result')
		data.content = kwargs.get('content')
		return data


	def create_notification(self, **kwargs):
		data = ActivityNotification()
		data = self.before_create(data, **kwargs)
		return self.create(data.to_dict())


	def create_feed(self, **kwargs):
		kwargs['group'] = 'feed'
		kwargs['channel_id'] = kwargs['channel_id']
		kwargs['time_created'] = time.time()
		create = self.create(kwargs)
		where = self.create_where_condition('group', 'feed')
		where.update(self.create_where_condition('feed_id', kwargs['feed_id']))
		recent = self.find_all(where, sort = '-time', limit = 10)
		recent_ids = [row['_id'] for row in recent]
		if recent_ids:
			where.update(self.create_where_condition('_id', recent_ids, 'nin'))
			self.delete_many_document(where)
		return create


	def create_process(self, **kwargs):
		data = ActivityProcess()
		data = self.before_create(data, **kwargs)
		return self.create(data.to_dict())


	def create_recent(self, **kwargs):
		data = ActivityRecent()
		data = self.before_create(data, **kwargs)
		create = self.create(data.to_dict())
		where = self.create_where_condition('group', 'recent')
		recent = self.find_all(where, sort = '-_id', limit = 10)
		recent_ids = [row['_id'] for row in recent]
		if recent_ids:
			where.update(self.create_where_condition('_id', recent_ids, 'nin'))
			self.delete_many_document(where)
		return create
