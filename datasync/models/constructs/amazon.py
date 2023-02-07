from datasync.models.constructs.base import ConstructBase


class CustomPriceTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.status = self.DISABLE
		self.value = 0
		super().__init__(**kwargs)


class AdjustmentPriceTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.direction = 'increment'
		self.modifier = 'percent'
		self.value = 0
		super().__init__(**kwargs)


class SimplePriceTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.adjustment = AdjustmentPriceTemplate()
		self.custom_price = CustomPriceTemplate()
		super().__init__(**kwargs)


class SimplePriceTemplateWithStatus(SimplePriceTemplate):
	def __init__(self, **kwargs):
		self.status = self.DISABLE

		super().__init__(**kwargs)


class AmazonSpecialPrice(SimplePriceTemplateWithStatus):
	def __init__(self, **kwargs):
		self.sale_start_date = ''
		self.sale_end_date = ''
		self.price = 0
		super().__init__(**kwargs)


class PriceTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.price = SimplePriceTemplate()
		self.special_price = AmazonSpecialPrice()
		self.msrp = SimplePriceTemplateWithStatus()
		self.map = SimplePriceTemplateWithStatus()
		super().__init__(**kwargs)


class AmazonCondition(ConstructBase):
	def __init__(self, **kwargs):
		self.new = ''
		self.used = ''
		self.reconditioned = ''
		self.value = ''
		super().__init__(**kwargs)


class OfferTemplate(ConstructBase):
	def __init__(self, **kwargs):
		self.condition = AmazonCondition()
		self.condition_notes = ''
		self.fulfillment = ''
		self.handling_time = 0
		self.tax_code = ''
		self.gift_message = self.DISABLE
		self.gift_wrap = self.DISABLE
		self.max_order_qty = 0
		self.launch_date = ''
		self.release_date = ''
		self.restock_date = ''
		super().__init__(**kwargs)
