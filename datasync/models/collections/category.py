from datasync.models.collection import ModelCollection


class Category(ModelCollection):
	COLLECTION_NAME = 'categories'


	def __init__(self, **kwargs):
		super().__init__(**kwargs)


	def get_collection_name(self):
		return self.COLLECTION_NAME
