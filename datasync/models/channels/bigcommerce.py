import requests

from datasync.libs.errors import Errors
from datasync.libs.response import Response
from datasync.libs.utils import *
from datasync.models.channel import ModelChannel
from datasync.models.constructs.order import Order, OrderDiscount, OrderShipping, OrderAddress, OrderPayment, Shipment, OrderCustomer, OrderProducts
from datasync.models.constructs.product import Product, ProductImage, ProductVariant, \
	ProductVariantAttribute

class ModelChannelsBigcommerce(ModelChannel):

	def __init__(self):
		super().__init__()
		self._api_url = None
		self._product_next_link = None
		self._flag_finish_order = None
		self._flag_finish_product = None
		self._last_product_images = None
		self._last_product_response = None
		self._order_next_link = False
		self._product_next_link = False

	# ------------------------------SETUP CHANNEL------------------------------
	def get_api_info(self):
		return {
			'access_token': 'X-Auth-Token'
		}

	def api(self, path, data = None, api_type = "get", add_version = True):
		path = self.get_api_path(path, add_version)
		url = self.get_api_url() + '/' + to_str(path).strip('/')
		res = self.requests(url, data, method = api_type)
		retry = 0
		while (res is False) or ('expected Array to be a Hash' in to_str(res)) or (
				"Exceeded 2 calls per second for api client. Reduce request rates to resume uninterrupted service" in to_str(
			res)) or self._last_status >= 500:
			retry += 1
			time.sleep(10)
			res = self.requests(url, data, method = api_type)
			if retry > 5:
				break
		return res

	def get_api_path(self, path, add_version = True):
		path = to_str(path)
		if not add_version:
			return "v2/" + path
		return "v3/" + path

	def get_api_url(self):
		if not self._api_url:
			self._api_url = self.create_api_url()
		return self._api_url

	def create_api_url(self):
		api_url = "https://api.bigcommerce.com/stores/{}".format(
			self._state.channel.config.api.shop)
		return api_url

	def display_setup_channel(self, data = None):
		parent = super().display_setup_channel(data)
		if parent.result != Response().SUCCESS:
			return parent
		url = self._channel_url
		bigcommerce_code = re.findall("https://store-(.*).mybigcommerce.com", url)
		self._state.channel.config.api.shop = bigcommerce_code[0]
		# add_version = False for using v2, True for v3
		store = self.api('store', add_version = False)
		if not store:
			return Response().error(Errors.BIGCOMMERCE_API_INVALID)
		return Response().success()

	def validate_bigcommerce_url(self, cart_url):
		bigcommerce_code = re.findall("https://store-(.*).mybigcommerce.com", cart_url)
		if not bigcommerce_code:
			return Response().error(Errors.BIGCOMMERCE_API_PATH_INVALID)
		return Response().success()

	def format_url(self, url, **kwargs):
		url = super().format_url(url, **kwargs)
		url.strip('[]')
		url_parse = urllib.parse.urlparse(url)
		url = "https://" + url_parse.hostname
		return url

	def validate_channel_url(self):
		parent = super().validate_channel_url()
		if parent.result != Response.SUCCESS:
			return parent
		return self.validate_bigcommerce_url(self._channel_url)

	def set_channel_identifier(self):
		parent = super().set_channel_identifier()
		if parent.result != Response().SUCCESS:
			return parent
		self.set_identifier(self._state.channel.config.api.shop)
		return Response().success()

	def requests(self, url, data = None, headers = None, method = 'get'):
		method = to_str(method).lower()
		if not headers:
			headers = dict()
			headers['User-Agent'] = get_random_useragent()
		elif isinstance(headers, dict) and not headers.get('User-Agent'):
			headers['User-Agent'] = get_random_useragent()
		headers['Content-Type'] = 'application/json'
		headers['Accept'] = 'application/json'
		headers['X-Auth-Token'] = self._state.channel.config.api.access_token

		request_options = {
			'headers': headers,
			'verify': True
		}
		if method == 'get' and data:
			request_options['params'] = data
		if method in ['post', 'put'] and data:
			request_options['json'] = data
		request_options = self.combine_request_options(request_options)
		response_prodict = Prodict()
		try:
			response = requests.request(method, url, **request_options)
			self._last_header = response.headers
			self._last_status = response.status_code
			response_data = json_decode(response.text)
			if response_data:
				try:
					response_prodict = Prodict(**response_data)
				except Exception:
					response_prodict = response_data
		except Exception as e:
			self.log_traceback()
		return response_prodict

	# ------------------------------ACTION PULL------------------------------
	def display_pull_channel(self):
		parent = super().display_pull_channel()
		if parent.result != Response().SUCCESS:
			return parent
		if self.is_product_process():
			if self.is_refresh_process():
				self._state.pull.process.products.id_src = 0
			# add_version = True to use v2, False to use v3
			products_api = self.api('products/count', add_version = False)
			self._state.pull.process.products.error = 0
			self._state.pull.process.products.imported = 0
			self._state.pull.process.products.new_entity = 0
			self._state.pull.process.products.total = 0
			if products_api and products_api.count:
				if self.is_refresh_process():
					self._state.pull.process.products.total = -1
				else:
					self._state.pull.process.products.total = products_api.count
		if self.is_order_process():
			self._state.pull.process.orders.total = 0
			self._state.pull.process.orders.imported = 0
			self._state.pull.process.orders.new_entity = 0
			self._state.pull.process.orders.error = 0
			self._state.pull.process.orders.id_src = 0
			start_time = self.get_order_start_time('iso')
			last_modifier = self._state.pull.process.orders.max_last_modified
			params = {
				"min_date_created": start_time
			}
			if last_modifier:
				params['min_date_modified'] = last_modifier
				self.set_order_max_last_modifier(last_modifier)
		orders_api = self.api('orders/count', data = params, add_version = False)
		if orders_api and orders_api.count:
			self._state.pull.process.orders.total = orders_api.count
		return Response().success()

	def get_products_main_export(self):
		if self._flag_finish_product:
			return Response().finish()
		if self._product_next_link:
			products = self.requests(self._product_next_link)
		else:
			limit_data = self._state.pull.setting.products
			params = {'limit': limit_data, 'include': 'variants,images'}
			products = self.api('catalog/products', data = params)
		links = self._last_header.get('link')
		next_link = ''
		if links and 'next' in links:
			list_link = links.split(',')
			for link_row in list_link:
				if 'next' in link_row:
					next_link = link_row.split(';')[0]
					next_link = next_link.strip('<> ')
		if next_link:
			self._product_next_link = next_link
		else:
			self._flag_finish_product = True
		if not products or not products.data:
			if self._last_status != 200:
				return Response().error(Errors.BIGCOMMERCE_GET_PRODUCT_FAIL)
			return Response().finish()
		return Response().success(data = products.data)

	def get_products_ext_export(self, products):
		extend = Prodict()
		for product in products:
			product_id = to_str(product.id)
			meta = self.api("catalog/products/{}/metafields".format(product.id))
			extend.set_attribute(product_id, Prodict())
			extend[to_str(product_id)].meta = meta.data
		return Response().success(extend)

	def get_product_id_import(self, convert: Product, product, products_ext):
		return product.id

	def _convert_product_export(self, product, products_ext: Prodict):
		product_id = to_str(product.id)
		product_data = Product()
		count_children = to_len(product.variants) if product.variants else None
		if not count_children:
			return Response().error(Errors.BIGCOMMERCE_API_INVALID)
		product.type = product.type
		product.variant_count = ""
		product_data.name = product.name
		product_data.sku = product.sku
		product_data.upc = product.upc
		product_data.gtin = product.gtin
		product_data.mpn = product.mpn
		product_data.description = product.description
		product_data.meta_keyword = ""
		product_data.price = product.sale_price if product.sale_price else product.price
		product_data.cost = product.cost_price
		product_data.msrp = product.retail_price
		product_data.weight = product.weight
		product_data.weight_units = 'kg'
		product_data.dimension_units = 'cm'
		product_data.width = product.width
		product_data.height = product.height
		product_data.manage_stock = True if product.inventory_tracking else False
		if product_data.manage_stock:
			product_data.is_in_stock = True if to_int(product.inventory_level) > 0 else False
		else:
			product_data.is_in_stock = True
		product_data.updated_at = convert_format_time(''.join(product.date_created.rsplit(':', 1)),
		                                              '%Y-%m-%dT%H:%M:%S%z')
		product_data.created_at = convert_format_time(''.join(product.date_modified.rsplit(':', 1)),
		                                              '%Y-%m-%dT%H:%M:%S%z')
		brand = self.api("catalog/brands/{}".format(product.brand_id))
		brand_data = brand.data
		if brand and brand_data:
			product_data.brand = brand_data.name
		if product.images:
			images_data = product.images
			for image in images_data:
				if image.is_thumbnail:
					product_data.thumb_image.url = image.url_zoom
					product_data.thumb_image.label = image.image_file
				product_image_data = ProductImage()
				product_image_data.url = image.url_zoom
				product_image_data.label = image.image_file.split("/")[-1]
				product_image_data.position = image.sort_order
				product_data.images.append(product_image_data)
		product_data.seo_url = f"{self.get_channel_url()}/{product.custom_url.url.strip('/')}"
		if product.variants:
			qty = 0
			manage_stock = False
			is_in_stock = False
			for variant in product.variants:
				variant_manage_stock = True if product.inventory_tracking else False
				if variant_manage_stock:
					manage_stock = True
				if product.inventory_tracking == 'variant':
					qty += to_int(variant.inventory_level)
				if product.inventory_tracking == 'product':
					qty = 0
				variant_is_in_stock = True if to_int(variant.inventory_level) > 0 else False
				if variant_is_in_stock:
					is_in_stock = True
				variant_data = ProductVariant()
				variant_data.id = to_str(variant.id)
				variant_data.name = to_str(variant.sku.replace(to_str(product.sku), product.name))
				variant_data.sku = to_str(variant.sku)
				variant_data.price = variant.price
				variant_data.qty = to_int(variant.inventory_level)
				variant_data.manage_stock = variant_manage_stock
				variant_data.is_in_stock = variant_is_in_stock
				variant_data.weight = variant.weight
				variant_data.dimension_units = 'cm'
				variant_data.weight_units = 'kg'
				if product.price and to_decimal(product.price) > to_decimal(product.sale_price):
					if variant.price:
						variant_data.price = variant.price
					variant_data.special_price.price = product.sale_price
					variant_data.price = product.price
				if variant.option_values:
					for option in variant.option_values:
						variant_attribute = ProductVariantAttribute()
						variant_attribute.id = f"{product.id}_{option.id}"
						option_type = self.api("catalog/products/{}/options/{}".format(product.id, option.option_id))
						variant_attribute.attribute_type = option_type.data.type
						variant_attribute.attribute_name = option.option_display_name
						variant_attribute.attribute_value_name = option.label
						variant_data.attributes.append(variant_attribute)
				product_data.variants.append(variant_data)
			product_data.qty = qty
			product_data.is_in_stock = is_in_stock
			product_data.manage_stock = manage_stock
		if not product_data.sku:
			product_data.sku = product.id
		return Response().success(product_data)

	# ------------------------------ACTION PUSH------------------------------
	def product_import(self, convert: Product, product, products_ext):
		convert_product = self.product_to_bigcommerce_data(product, products_ext)
		if convert_product.result != Response.SUCCESS:
			return convert_product
		post_data, images = convert_product.data
		response = self.api('catalog/products', post_data, 'Post')
		check_response = self.check_response_import(response, product, 'product')
		product_id = response['data']['id']
		product_images = dict()
		for index, image in enumerate(images):
			try:
				product_images[image] = response.data.images[index]['id']
			except:
				pass
		self.set_last_product_response(response, product_images)
		return Response().success(product_id)

	def product_to_bigcommerce_data(self, product: Product, product_ext):
		if not product.name:
			return Response.error(msg = "PRODUCT DATA INVALID")
		images = self.extend_images(product)
		bigcommerce_images = list()
		for index, image in enumerate(images):
			is_thumbnail = False
			if to_str(image) == to_str(product.thumb_image.url):
				is_thumbnail = True
			image_data = {
				'image_url': html_unquote(image),
				'sort_order': index,
				'is_thumbnail': is_thumbnail,
			}
			bigcommerce_images.append(image_data)

		post_data = {
			'name': product.name,
			'type': 'physical',
			'sku': product.sku,
			'price': to_decimal(product.max_price) if to_decimal(product.max_price) else to_decimal(product.price),
			'sale_price': to_decimal(product.min_price) if to_decimal(product.min_price) else to_decimal(product.price),
			'images': bigcommerce_images,
			'description': product.description
		}
		if product.weight:
			post_data['weight'] = to_decimal(product.weight)
		if product.length:
			post_data['length'] = to_decimal(product.length)
		if product.height:
			post_data['height'] = to_decimal(product.height)
		return Response().success((post_data, images))

	def after_product_import(self, product_id, convert: Product, product, products_ext):
		response, images = self.get_last_product_response()
		if product.variants:
			pass
		else:
			default_variant = response['data']['variants'][0]
			variants_post_data = {
				# 'product_id': product.id,
				'price': product.price,
				'weight': to_decimal(product.weight) if to_decimal(product.weight) > 0 else 0,
				'height': to_decimal(product.height) if to_decimal(product.height) > 0 else 0,
				'width': to_decimal(product.width) if to_decimal(product.width) > 0 else 0,
				'cost_price': product.cost,
				'price': product.price,
				'inventory_level': to_int(product.qty)
			}
			post_data = {
				'id': product_id,
				'variants': [variants_post_data],
			}
			var_response = self.api(f'catalog/products/{product_id}', post_data, 'Put')
			check_response = self.check_response_import(product, var_response)
			if check_response.result != Response().SUCCESS:
				return check_response
		return Response().success()

	def extend_images(self, product):
		images = list()
		if product.thumb_image.url:
			main_images = self.process_image_before_import(product.thumb_image.url, product.thumb_image.path)
			images.append(main_images['url'])
		for img_src in product.images:
			if 'status' in img_src and not img_src['status']:
				continue
			image_process = self.process_image_before_import(img_src.url, img_src.path)
			if image_process['url'] not in images:
				images.append(image_process['url'])
		return images

	def check_response_import(self, response, convert, entity_type = ''):
		entity_id = convert.id if convert.id else convert.code
		if not response:
			return Response().error()
		elif response and hasattr(response, 'errors') and response.errors:
			console = list()
			if isinstance(response.errors, list):
				for error in response.errors:
					if isinstance(error, list):
						error_messages = ' '.join(error)
					else:
						error_messages = error
					console.append(error_messages)
			if isinstance(response.errors, dict) or isinstance(response.errors, Prodict):
				for key, error in response['errors'].items():
					if isinstance(error, list):
						error_messages = ' '.join(error)
					else:
						error_messages = error
					console.append(key + ': ' + error_messages)
			else:
				console.append(response['errors'])
			msg_errors = '\n'.join(console)
			self.log(entity_type + ' id ' + to_str(entity_id) + ' import failed. Error: ' + msg_errors,
			         "{}_errors".format(entity_type))
			return Response().error(msg = msg_errors)

		else:
			return Response().success()

	def set_last_product_response(self, response, images):
		self._last_product_response = response
		self._last_product_images = images

	def get_last_product_response(self):
		return self._last_product_response, self._last_product_images

	# def is_special_price(self, product: Product):
	#     special_price = product.special_price
	#     if not to_decimal(special_price.price, 2) or to_decimal(special_price.price) >= to_decimal(
	#             product.price) or not to_timestamp_or_false(special_price.start_date):
	#         return False
	#     if not to_timestamp_or_false(special_price.end_date):
	#         return True
	#     if to_timestamp_or_false(special_price.start_date) <= time.time() <= to_timestamp_or_false(
	#             special_price.end_date):
	#         return True
	#     return False

	# def to_bigcommerce_price(self, product: Product):
	#     special_price = product.special_price
	#     price = product.price
	#     compare_price = None
	#     if self.is_special_price(product):
	#         sale_price = special_price.price
	#         compare_price = price if price and to_decimal(
	#             price) > to_decimal(sale_price) else None
	#     else:
	#         if product.msrp and to_decimal(product.msrp) > to_decimal(price):
	#             compare_price = product.msrp
	#             sale_price = price
	#         else:
	#             sale_price = price
	#     return round(to_decimal(compare_price), 2), round(to_decimal(sale_price), 2)

	def get_orders_main_export(self):
		if self._flag_finish_order:
			return Response().finish()
		if self._order_next_link:
			orders = self.requests(self._order_next_link)
		else:
			limit_data = self._state.pull.setting.orders
			id_src = self._state.pull.process.orders.id_src
			start_time = self.get_order_start_time('iso')
			last_modifier = self._state.pull.process.orders.max_last_modified
			params = {
				"min_date_created": start_time,
				"limit": limit_data,
			}
			if last_modifier:
				params['min_date_modified'] = last_modifier
			orders = self.api('orders', data = params, add_version = False)
		if not orders:
			if self._last_status != 200:
				return Response().error(Errors.BIGCOMMERCE_GET_ORDER_FAIL)
			return Response().finish()
		links = self._last_header.get('link')
		next_link = ''
		if links and 'next' in links:
			list_link = links.split(',')
			for link_row in list_link:
				if 'next' in link_row:
					next_link = link_row.split(';')[0]
					next_link = next_link.strip('<> ')
		if not next_link:
			self._flag_finish_order = True
		else:
			self._order_next_link = next_link
		return Response().success(data = orders)

	def set_order_max_last_modifier(self, last_modifier):
		if last_modifier and (not self._order_max_last_modified or to_timestamp(last_modifier, "%Y-%m-%dT%H:%M:%S") > to_timestamp(self._order_max_last_modified, '%Y-%m-%dT%H:%M:%S')):
			self._order_max_last_modified = last_modifier

	def get_orders_ext_export(self, orders):
		return Response().success()

	def convert_order_export(self, order, orders_ext, channel_id = None):
		self.set_order_max_last_modifier(order.updated_at)
		order_data = Order()
		order_data.id = order.id
		order_data.channel_order_number = order.id
		# order_data.order_number_prefix
		# order_data.order_number_suffix
		order_data.status = ''
		order_data.channel_order_status = ''
		order_data.tax.title = "total_tax"
		order_data.tax.amount = to_decimal(order.total_tax)
		if order.discount_amount:
			discount_coupons_api = self.api(f"{order.coupons.resource[1:]}", add_version=False)
			if discount_coupons_api:
				order_discount_data = OrderDiscount()
				order_discounts = list()
				for discount_coupon in discount_coupons_api:
					order_discount_data.code = discount_coupon.code
					order_discount_data.amount = discount_coupon.amount
					order_discount_data.modifier = order_discount_data.PERCENT
					order_discounts.append(order_discount_data)
				order_data.discount = order_discounts

			order_data.discount.amount = order.discount_amount
		order_data.discount.title = ''
		order_data.discount.code = ''
		order_data.discount.amount = ''
		order_data.shipping = OrderShipping()
		order_data.subtotal = order.subtotal_inc_tax
		order_data.total = order.total_inc_tax
		order_data.currency = order.currency_code
		order_data.created_at = isoformat_to_datetime(
			order.date_created).strftime("%Y-%m-%d %H:%M:%S")
		order_data.updated_at = isoformat_to_datetime(
			order.date_modified).strftime("%Y-%m-%d %H:%M:%S")
		order_data.customer = OrderCustomer()
		order_data.customer_address = OrderAddress()
		order_data.billing_address = OrderAddress()
		order_data.shipping_address = OrderAddress()
		order_data.payment = OrderPayment()
		order_data.products = OrderProducts()
		# order_data.product_ids = list()
		# order_data.is_assigned = False
		order_data.shipments = Shipment()
		# order_data.history = list()
		order_data.channel = dict()
		# order_data.channel_id = ''
		# order_data.channel_name = ''
		# order_data.updated_time = 0
		return Response().success(order_data)
