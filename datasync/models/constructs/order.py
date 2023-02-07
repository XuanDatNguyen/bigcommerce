from typing import List

from datasync.libs.utils import get_current_time
from datasync.models.constructs.base import ConstructBase


class OrderChannel(ConstructBase):
	ACTIVE = 'active'
	INACTIVE = "inactive"
	ERROR = "error"


	def __init__(self, **kwargs):
		self.order_id = ''
		self.channel_id = ""
		self.order_status = ""
		self.created_at = ""
		self.completed_at = ""
		self.status = self.ACTIVE
		self.order_number = ''
		super().__init__(**kwargs)


class OrderCustomer(ConstructBase):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.id = None
		self.username = ''
		self.email = ''
		self.telephone = ''
		self.first_name = ''
		self.middle_name = ''
		self.last_name = ''


class OrderAddressCountry(ConstructBase):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.country_code = ''
		self.country_name = ''


class OrderAddressState(ConstructBase):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.state_code = ''
		self.state_name = ''


class OrderAddress(ConstructBase):
	country: OrderAddressCountry
	state: OrderAddressState


	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.id = None
		self.first_name = ''
		self.middle_name = ''
		self.last_name = ''
		self.address_1 = ''
		self.address_2 = ''
		self.city = ''
		self.postcode = ''
		self.telephone = ''
		self.company = ''
		self.fax = ''
		self.country = OrderAddressCountry()
		self.state = OrderAddressState()


class OrderProductDetails(ConstructBase):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.id = None
		self.sku = None
		self.name = None


class OrderItemOption(ConstructBase):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.option_id = ''
		self.option_code = ''
		self.option_name = ''
		self.option_value_id = ''
		self.option_value_code = ''
		self.option_value_name = ''
		self.price = ''
		self.price_prefix = '+'


class OrderProducts(ConstructBase):
	FIXED = 'fixed'
	PERCENT = 'percent'
	# product: OrderProductDetails
	options: List[OrderItemOption]


	# warehouse_inventories: Dict[str, int]

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.id = None
		self.parent_id = None
		self.code = None
		self.product_id = None
		self.product_sku = None
		self.product_name = None
		self.qty = 0
		self.warehouse_inventories = {}
		self.price = 0.0
		self.original_price = 0.0
		self.tax_amount = 0.0
		self.tax_modifier = self.PERCENT
		self.discount_amount = 0.0
		self.discount_modifier = self.FIXED
		self.subtotal = 0.0
		self.total = 0.0
		self.created_at = 0.0
		self.updated_at = get_current_time()
		self.options = list()
		self.status = 'instock'
		self.link_status = 'unlink'


class OrderHistory(ConstructBase):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.id = ''
		self.code = ''
		self.status = ''
		self.comment = ''
		self.staff_note = False
		self.source = 'channel'
		self.created_at = ''
		self.updated_at = get_current_time()


class OrderHistoryStaff(OrderHistory):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.staff_note = True


class OrderPayment(ConstructBase):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.code = ''
		self.method = ''
		self.status = False
		self.title = ''
		self.transaction_id = ''
		self.cc_last_4 = ''
		self.cc_exp_month = ''
		self.cc_ss_start_year = ''
		self.cc_exp_year = ''
		self.cc_owner = ''
		self.additional_information = ''


class OrderTax(ConstructBase):
	FIXED = 'fixed'
	PERCENT = ' percent'


	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.title = ''
		self.amount = 0.0
		self.modifier = self.FIXED


class OrderDiscount(ConstructBase):
	FIXED = 'fixed'
	PERCENT = ' percent'


	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.title = ''
		self.code = ''
		self.amount = 0.0
		self.modifier = self.FIXED


class OrderShipping(ConstructBase):
	FIXED = 'fixed'
	PERCENT = ' percent'


	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.method = ''
		self.status = False
		self.title = ''
		self.amount = 0.0
		self.modifier = self.FIXED


class Shipment(ConstructBase):
	STATUS_COMPLETED = 'completed'
	STATUS_PROCESSING = 'processing'
	STATUS_CANCELED = 'canceled'
	CARRIER_AMAZON = 'fba'
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


class Order(ConstructBase):
	OPEN = 'open'
	LINKED = 'linked'
	UNLINK = 'unlink'
	AWAITING_PAYMENT = 'awaiting_payment'
	READY_TO_SHIP = 'ready_to_ship'
	SHIPPING = 'shipping'
	COMPLETED = 'completed'
	CANCELED = 'canceled'
	tax: OrderTax
	discount: OrderDiscount
	shipping: OrderShipping
	customer: OrderCustomer
	customer_address: OrderAddress
	billing_address: OrderAddress
	shipping_address: OrderAddress
	payment: OrderPayment
	products: List[OrderProducts]
	# shipments: List[Shipment]
	history: List[OrderHistory]


	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.id = None
		self.order_number = None
		self.channel_order_number = None
		self.order_number_prefix = ''
		self.order_number_suffix = ''
		self.status = None
		self.channel_order_status = None
		self.tax = OrderTax()
		self.discount = OrderDiscount()
		self.shipping = OrderShipping()
		self.subtotal = 0.0
		self.total = 0.0
		self.currency = ''
		self.created_at = ''
		self.imported_at = ''
		self.updated_at = get_current_time()
		self.customer = OrderCustomer()
		self.customer_address = OrderAddress()
		self.billing_address = OrderAddress()
		self.shipping_address = OrderAddress()
		self.payment = OrderPayment()
		self.products = list()
		self.product_ids = dict()
		self.is_assigned = False
		self.shipments = Shipment()
		self.history = list()
		self.channel = dict()
		self.channel_id = ''
		self.channel_name = ''
		self.updated_time = 0
		self.link_status = self.LINKED
