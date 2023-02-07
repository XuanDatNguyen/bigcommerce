from typing import List

from datasync.libs.utils import get_current_time
from datasync.models.constructs.base import ConstructBase
from datasync.models.constructs.order import OrderAddress


class ShipmentProduct(ConstructBase):
	def __init__(self, **kwargs):
		self.id = None
		self.code = None
		self.product_id = None
		self.product_sku = None
		self.product_name = None
		self.qty = 0
		self.shipped_qty = 0
		self.carrier = ''
		self.shipped_at = None
		self.estimated_arrival_at = None
		self.tracking_number = ''
		super().__init__(**kwargs)


class Shipment(ConstructBase):
	STATUS_COMPLETED = 'completed'
	STATUS_PROCESSING = 'processing'
	STATUS_CANCELED = 'canceled'
	CARRIER_AMAZON = 'fba'
	products: List[ShipmentProduct]
	shipping_address: OrderAddress


	def __init__(self, **kwargs):
		self.id = ''
		self.fulfillment_id = ''
		self.tracking_number = ''
		self.tracking_url = ''
		self.tracking_company_code = ''
		self.tracking_company = ''
		self.status = self.STATUS_PROCESSING
		self.created_at = get_current_time()
		self.shipped_at = None
		self.error_message = None
		super().__init__(**kwargs)
