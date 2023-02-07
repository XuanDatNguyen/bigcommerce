from typing import List

from datasync.libs.prodict import Prodict
from datasync.libs.utils import get_current_time
from datasync.models.constructs.base import ConstructBase


class ProductImage(ConstructBase):
	def __init__(self, **kwargs):
		self.label = ''
		self.url = ''
		self.position = 0
		self.status = True
		super().__init__(**kwargs)


class ProductOptionValueLang(ConstructBase):
	def __init__(self, **kwargs):
		self.option_value_name = ''
		super().__init__(**kwargs)


class ProductOptionValue(ConstructBase):
	def __init__(self, **kwargs):
		self.id = ''
		self.code = ''
		self.option_value_code = ''
		self.option_value_name = ''
		self.option_value_qty = False
		self.option_value_sku = False
		self.option_value_languages = dict()
		self.option_value_price = 0.0
		self.price_prefix = '+'
		self.option_value_disabled = False
		self.thumb_image = ProductImage()
		super().__init__(**kwargs)


class ProductOptionLang(ConstructBase):
	def __init__(self, **kwargs):
		self.option_name = None
		super().__init__(**kwargs)


class ProductOption(ConstructBase):
	option_values: List[ProductOptionValue]


	def __init__(self, **kwargs):
		self.id = None
		self.code = None
		self.option_set = ''
		self.option_group = ''
		self.option_mode = ''
		self.option_type = ''
		self.option_code = None
		self.option_name = None
		self.required = True
		self.option_values = list()
		super().__init__(**kwargs)


class ProductTierPrice(ConstructBase):
	def __init__(self, **kwargs):
		self.id = None
		self.code = None
		self.sites = list()
		self.name = ''
		self.tier_code = ''
		self.group = list()
		self.qty = 0
		self.price = 0.0
		self.start_date = ''
		self.end_date = ''
		self.price_type = 'fixed'
		self.customer_group_id = 0
		self.all_group = False
		super().__init__(**kwargs)


class ProductManufacturer(ConstructBase):
	def __init__(self, **kwargs):
		self.id = None
		self.code = ''
		self.name = ''
		super().__init__(**kwargs)


class ProductTax(ConstructBase):
	def __init__(self, **kwargs):
		self.id = None
		self.code = None
		super().__init__(**kwargs)


class ProductRelation(ConstructBase):
	def __init__(self, **kwargs):
		self.id = None
		self.code = None
		self.type = None
		super().__init__(**kwargs)


class ProductRelate(ConstructBase):
	parent: List[ProductRelation]
	children: List[ProductRelation]


	def __init__(self, **kwargs):
		self.parent = list()
		self.children = list()
		super().__init__(**kwargs)


class ProductCategory(ConstructBase):
	def __init__(self, **kwargs):
		self.id = None
		self.code = None
		self.name = None
		self.position = 0
		super().__init__(**kwargs)


class ProductAttribute(ConstructBase):
	def __init__(self, **kwargs):
		self.id = None
		self.code = None
		self.attribute_mode = ''
		self.attribute_type = ''
		self.attribute_code = None
		self.attribute_name = None
		self.attribute_languages = dict()
		self.attribute_value_id = None
		self.attribute_value_code = ''
		self.attribute_value_name = ''
		self.attribute_value_languages = dict()
		self.price = 0.0
		self.price_prefix = '+'
		self.use_variant = False
		super().__init__(**kwargs)


class ProductVariantAttribute(ProductAttribute):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.use_variant = True


class ProductDownloadableSample(ConstructBase):
	def __init__(self, **kwargs):
		self.path = ''
		self.name = ''
		super().__init__(**kwargs)


class ProductDownloadable(ConstructBase):
	sample: ProductDownloadableSample


	def __init__(self, **kwargs):
		self.id = None
		self.path = ''
		self.name = ''
		self.limit = ''
		self.max_day = ''
		self.date_expired = ''
		self.price = 0.0
		self.sample = ProductDownloadableSample()
		self.required = True
		self.values = list()
		super().__init__(**kwargs)


class ProductSeo(ConstructBase):
	def __init__(self, **kwargs):
		self.request_path = ''
		self.seo_type = self.SEO_DEFAULT
		self.default = True
		self.store_id = ''
		self.category_id = ''
		super().__init__(**kwargs)


class ProductChannel(ConstructBase):
	ACTIVE = 'active'
	DRAFT = 'draft'
	INACTIVE = "inactive"
	UNLINK = "unlink"
	LINKED = "linked"
	NEW = 'new'
	PUSHING = 'pushing'
	ERRORS = 'error'
	COMPLETED = 'completed'


	def __init__(self, **kwargs):
		self.product_id = ''
		self.sku = ''
		self.name = ''
		self.channel_id = ""
		self.status = self.ACTIVE
		self.visible = True
		self.publish_status = self.NEW
		self.link_status = self.UNLINK
		self.qty = ''
		self.price = ''
		self.templates = dict()
		self.template_data = dict()
		self.edit = True
		self.auto_link = False
		super().__init__(**kwargs)


class ProductInventory(ConstructBase):
	def __init__(self, **kwargs):
		self.location_id = ''
		self.available = 0
		self.reserved = 0
		self.on_hand = 0
		self.updated_at = get_current_time()
		self.status = "active"
		super().__init__(**kwargs)


class ProductInventories(ConstructBase):
	inventory: Prodict


	def __init__(self, **kwargs):
		self.total_available = 0
		self.total_reserved = 0
		self.total_on_hand = 0
		self.inventory = dict()
		super().__init__(**kwargs)


class ProductSpecialPrice(ConstructBase):
	def __init__(self, **kwargs):
		self.price = 0.0
		self.start_date = ''
		self.end_date = ''
		super().__init__(**kwargs)


class ProductSource(ConstructBase):
	def __init__(self, **kwargs):
		self.channel_type = ''
		self.channel_id = ''
		super().__init__(**kwargs)


class Product(ConstructBase):
	PRODUCT_SIMPLE = 'simple'
	CONDITION_NEW = 'new'
	CONDITION_USED = 'used'
	CONDITION_RECONDITIONED = 'reconditioned'
	thumb_image: ProductImage
	special_price: ProductSpecialPrice
	tier_prices: List[ProductTierPrice]
	tax: ProductTax
	manufacturer: ProductManufacturer
	categories: List[ProductCategory]
	options: List[ProductOption]
	attributes: List[ProductAttribute]
	relate: ProductRelate
	seo: List[ProductSeo]
	downloadable: List[ProductDownloadable]
	channel: Prodict  # key = channel_{channel_id}, value = ProductChannel
	inventories: ProductInventories  # key = inventory_id, value = ProductInventory


	def __init__(self, **kwargs):
		self.id = ''
		self.code = ''
		self.type = ''
		self.is_variant = False
		self.variant_count = 0
		self.parent_id = False
		self.store_ids = list()
		self.product_skus = list()
		self.thumb_image = ProductImage()
		self.images = list()
		self.parent = dict()
		self.name = ''
		self.lower_name = ''
		self.condition = self.CONDITION_NEW  # new|used|reconditioned
		self.sku = ''
		self.model = ''
		self.upc = ''
		self.barcode = ''
		self.ean = ''
		self.asin = ''
		self.gtin = ''
		self.gcid = ''
		self.epid = ''
		self.isbn = ''
		self.mpn = '' #Manufacturer Part Number
		self.bpn = '' #Bin Packing Number
		self.url_key = ''
		self.description = ''
		self.short_description = ''
		self.meta_title = ''
		self.meta_keyword = ''
		self.tags = ''
		self.materials = ''
		self.price = 0.0
		self.min_price = 0.0
		self.max_price = 0.0
		self.cost = 0.0
		self.msrp = 0.0
		self.special_price = ProductSpecialPrice()
		self.group_prices = list()
		self.tier_prices = list()
		self.weight = 0.0
		self.weight_units = 'oz'
		self.dimension_units = 'in'
		self.length = 0.0
		self.width = 0.0
		self.height = 0.0
		self.status = True
		# self.import_status = 'active'
		self.manage_stock = True
		self.qty = 0
		self.is_in_stock = True
		self.tax = ProductTax()
		self.manufacturer = ProductManufacturer()
		self.brand = ''
		self.created_at = None
		self.updated_at = get_current_time()
		self.categories = list()
		self.languages = dict()
		self.options = list()
		self.group_parent_ids = list()
		self.group_child_ids = list()
		self.attributes = list()
		self.variants = list()
		self.relate = ProductRelate()
		self.seo_url = ""
		self.custom_url = list()
		self.downloadable = list()
		self.edit = False
		self.src = ProductSource()
		self.inventories = ProductInventories()
		self.variant_attributes = list()
		self.variant_options = list()
		self.channel = dict()
		self.templates = dict()
		self.template_data = dict()
		self.channel_data = dict()
		self.note = ''
		self.updated_time = 0
		self.category_ids = list()
		self.category_name_list = list()
		self.category_lower_name = ''
		super().__init__(**kwargs)


class ProductVariant(Product):
	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self.type = self.PRODUCT_SIMPLE
		self.is_variant = True


	def construct(self):
		variant = super().construct()
		variant['type'] = self.PRODUCT_SIMPLE
		variant['is_variant'] = True
		return variant


class ProductLang(ConstructBase):
	def __init__(self, **kwargs):
		self.name = ''
		self.description = ''
		self.short_description = ''
		self.meta_title = ''
		self.meta_keyword = ''
		self.price = ''
		super().__init__(**kwargs)
