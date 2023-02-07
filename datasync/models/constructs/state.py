from typing import List

from datasync.models.constructs.base import ConstructBase


class StateChannelConfigPriceSync(ConstructBase):
	ENABLE = 'enable'
	DISABLE = 'disable'
	INCREASE = 'increase'
	DECREASE = 'decrease'
	FIXED = 'fixed'
	PERCENT = 'percent'


	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.direction = self.INCREMENT
		self.modifier = self.FIXED
		self.value = 0
		super().__init__(**kwargs)


class StateChannelConfigQtySync(ConstructBase):
	ENABLE = 'enable'
	DISABLE = 'disable'


	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.adjust = 100
		super().__init__(**kwargs)


class StateChannelConfig(ConstructBase):
	def __init__(self, **kwargs):
		self.token = ''
		self.version = ''
		self.start_time = ''
		self.connector_version = ''
		self.table_prefix = 0
		self.charset = 0
		self.image_category = 0
		self.image_product = 0
		self.image_manufacturer = 0
		self.api = dict()
		self.folder = ''
		self.file = dict()
		self.database = dict()
		self.extend = dict()
		self.auth = StateChannelAuth()
		self.price_sync = StateChannelConfigPriceSync()
		self.qty_sync = StateChannelConfigQtySync()
		self.setting = dict()
		super().__init__(**kwargs)


class StateChannelClear(ConstructBase):
	def __init__(self, **kwargs):
		self.result = 'success'
		self.function = 'no_clear'
		self.msg = ''
		self.limit = None
		super().__init__(**kwargs)


class StateChannelSupport(ConstructBase):
	def __init__(self, **kwargs):
		self.taxes = False
		self.categories = False
		self.products = True
		self.orders = True
		super().__init__(**kwargs)


class StateConfig(ConstructBase):
	def __init__(self, **kwargs):
		self.taxes = False
		self.categories = False
		self.products = False
		self.orders = False
		self.test = False
		self.clear_channel = False
		self.reset_clear = False
		self.reset = False
		super().__init__(**kwargs)


class EntityProcessCondition(ConstructBase):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.field = ''
		self.value = ''
		self.condition = ''
		self._id = False


class EntityProcess(ConstructBase):
	condition: List[EntityProcessCondition]


	def __init__(self, **kwargs):
		self.total = 0
		self.imported = 0
		self.new_entity = 0
		self.error = 0
		self.id_src = 0
		self.limit = None
		self.time_start = 0
		self.time_resume = 0
		self.previous_imported = 0
		self.time_finish = 0
		self.execute_ids = False
		self.condition = list()
		self.updated_time = 0
		super().__init__(**kwargs)


class StateResume(ConstructBase):
	def __init__(self, **kwargs):
		self.process = 'new'
		self.type = ''
		self.action = ''
		self.description = ''
		super().__init__(**kwargs)


class StateChannelAuth(ConstructBase):
	def __init__(self, **kwargs):
		self.username = ''
		self.password = ''
		super().__init__(**kwargs)


class StateChannel(ConstructBase):
	config: StateChannelConfig
	clear: StateChannelClear
	support: StateChannelSupport


	def __init__(self, **kwargs):
		self.channel_type = ''
		self.setup_type = ''
		self.url = ''
		self.position = 1
		self.config = StateChannelConfig()
		self.site = dict()
		self.languages = dict()
		self.language_default = ''
		self.order_status = dict()
		self.clear_process = StateChannelClear()
		self.support = StateChannelSupport()
		self.id = ''
		self.identifier = ''
		self.name = ''
		self.default = False
		self.create_order_process = False
		self.create_sync_process = False
		self.created_at = False
		self.updated_time = 0
		super().__init__(**kwargs)


class EntitiesProcess(ConstructBase):
	def __init__(self, **kwargs):
		self.taxes = EntityProcess()
		self.categories = EntityProcess()
		self.products = EntityProcess()
		self.orders = EntityProcess()
		super().__init__(**kwargs)


class StateSetting(ConstructBase):
	def __init__(self, **kwargs):
		self.products = 10
		self.categories = 10
		self.orders = 10
		super().__init__(**kwargs)


class SyncStateProcess(ConstructBase):

	def __init__(self, **kwargs):
		self.process = EntitiesProcess()
		self.resume = StateResume()
		self.setting = StateSetting()
		super().__init__(**kwargs)


class SyncStateSync(ConstructBase):
	def __init__(self, **kwargs):
		self.pull = SyncStateProcess()
		self.push = SyncStateProcess()
		super().__init__(**kwargs)


class SyncState(ConstructBase):

	def __init__(self, **kwargs):
		self.channel = StateChannel()
		self.config = StateConfig()
		self.pull = SyncStateProcess()
		self.push = SyncStateProcess()
		self.sync = SyncStateSync()
		self.resume = StateResume()
		self.running = False
		self.finish = False
		self.mode = 'demo'
		self.version = '1.0.0'
		self.user_id = kwargs.get('user_id', 0)
		self.sync_id = kwargs.get('sync_id', 0)
		self.pid = None
		self.server_id = None
		super().__init__(**kwargs)
