from datasync.libs.utils import get_current_time
from datasync.models.constructs.base import ConstructBase


class Activity(ConstructBase):
	GROUP_NOTIFICATION = 'notification'
	GROUP_PROCESS = 'process'
	GROUP_RECENT = 'recent'
	GROUP_FEED = 'feed'
	STATUS_NEW = 'new'
	STATUS_READ = 'read'
	STATUS_DELETED = 'deleted'
	SUCCESS = 'success'
	FAILURE = 'failed'


	def __init__(self, **kwargs):
		self.group = ''
		self.code = ""
		self.activity_type = ""
		self.status = 'new'
		self.content = ''
		self.created_at = get_current_time()
		self.date_requested = None
		self.channel_id = ''
		self.description = ''
		self.result = ''
		super().__init__(**kwargs)


class ActivityNotification(Activity):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.group = self.GROUP_NOTIFICATION


class ActivityProcess(Activity):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.group = self.GROUP_PROCESS


class ActivityRecent(Activity):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.group = self.GROUP_RECENT
