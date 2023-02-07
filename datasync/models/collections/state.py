from datasync.models.collection import ModelCollection
from datasync.models.constructs.state import SyncState


class State(ModelCollection):
	COLLECTION_NAME = 'state'
	_data: SyncState


	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._user_id = kwargs.get('user_id')


	def set_data(self, data):
		self._data = data


	def get_collection_name(self):
		return self.COLLECTION_NAME


	def get_sync_state(self, sync_id):
		state = self.get


	def get_state_by_sync_id(self, sync_id):
		info = self.get_sync_info()
		where = self.create_where_condition('sync_id', sync_id)
		state = self.find(where)
		if state:
			state = SyncState(**state)
		return state


	def delete_sync_state(self, sync_id):
		pass


	def update_state(self, _sync_id, state = None, pid = None, mode = None, status = None, finish = False, clear_entity_warning = False):
		pass


	def save(self, data = None):
		if self._document_id == 'litcommerce':
			return True
		return super(State, self).save(data)