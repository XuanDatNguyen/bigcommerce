from datasync.models.constructs.base import ConstructBase


class CategoryChannel(ConstructBase):
	ACTIVE = 'active'
	INACTIVE = "inactive"


	def __init__(self, **kwargs):
		self.category_id = ''
		self.channel_id = ""
		self.status = self.ACTIVE
		super().__init__(**kwargs)


class CategoryImage(ConstructBase):
	def __init__(self, **kwargs):
		self.label = ''
		self.url = ''
		self.position = 0
		self.status = True
		super().__init__(**kwargs)


class CatalogCategory(ConstructBase):

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.id = None
		self.code = None
		self.name = ''
		self.path = ''
		self.parent_id = 0
		self.channel_category_id = 0
		self.channel_id = 0
		self.is_parent = False


class CatalogCategoryParent(CatalogCategory):

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.is_parent = True
