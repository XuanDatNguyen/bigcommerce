from datasync.libs.prodict import Prodict


class ConstructBase(Prodict):
	ACTIVE = 'active'
	INACTIVE = 'inactive'
	DISABLE = 'disable'
	ENABLE = 'enable'
	def __init__(self, **kwargs):
		super().__init__(**kwargs)


	def construct(self):
		return {}
