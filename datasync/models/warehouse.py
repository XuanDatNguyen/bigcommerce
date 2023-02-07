import copy
import csv
import decimal
import os
import time
import urllib.parse
import uuid

from datasync.libs.errors import Errors
from datasync.libs.messages import Messages
from datasync.libs.response import Response
from datasync.libs.storage.google import ImageStorageGoogle, FileStorageGoogle
from datasync.libs.tracking_company import TrackingCompany
from datasync.libs.utils import to_decimal, to_str, to_len, to_int, get_current_time, get_pub_path, change_permissions_recursive, \
	get_config_ini, random_string, to_bool, url_to_link, get_row_from_list_by_field, duplicate_field_value_from_list, html_unescape, html_unquote, to_object_id, to_timestamp
from datasync.models.channel import ModelChannel, Prodict
from datasync.models.collections.catalog import Catalog
from datasync.models.constructs.activity import Activity
from datasync.models.constructs.category import CatalogCategory
from datasync.models.constructs.order import Order, OrderChannel
from datasync.models.constructs.order import Shipment
from datasync.models.constructs.product import Product, ProductVariant, ProductChannel, ProductInventory

class ModelWareHouse(ModelChannel):
	_storage_image_service: ImageStorageGoogle

	def __init__(self, **kwargs):
		super().__init__(**kwargs)
		self._user_id = kwargs.get('user_id')
		self._storage_image_service = None
		self._storage_service = None
		self._max_order_number = None
		self._template = None
		self._updated_time = 0
		self._is_insert_updated_time = None
		self._product_filter_conditions = dict()
		self._categories = dict()

	def prepare_display_setup_warehouse(self, data = None):
		return Response().success()

	def display_setup_warehouse(self, data = None):
		return Response().success()

	def prepare_pull_warehouse(self):
		return Response().success()

	# TODO:category
	def check_category_import(self, category_id, convert: CatalogCategory):
		catalog = self.get_category_map(category_id)
		return catalog if catalog else False

	def import_category_parent(self, parent: CatalogCategory):
		catalog = self.get_category_map(parent.id)
		if catalog:
			self.get_model_category().update_field(catalog, 'is_parent', True)
			return Response().success(catalog)
		category_import = self.category_import(parent, None, None)
		if category_import.result != Response().SUCCESS:
			return category_import
		after_category_import = self.after_category_import(category_import.data, parent, None, None)
		return Response().success(category_import.data)

	def process_category_before_import(self, category):
		category = dict(category)
		category_construct = CatalogCategory().to_dict()
		category_data = CatalogCategory().to_dict()
		for field, value in category_construct.items():
			if category.get(field):
				value = category.get(field)
			category_data[field] = value
		if category.get('parent') and category.get('id', 0) != category['parent'].get('id', 1):
			category_data['parent'] = self.process_category_before_import(category_data['parent'])
		return Prodict.from_dict(category_data)

	def category_import(self, convert: CatalogCategory, category: CatalogCategory, categories_ext):
		parent_id = ''
		if convert.parent and convert.parent.id:
			parent = self.import_category_parent(convert.parent)
			if parent.result != Response().SUCCESS:
				return Response().error(Errors.CATEGORY_PARENT_NOT_CREATE)
			parent_id = parent.data
		else:
			convert.parent_id = 0
		category_data = convert
		if 'parent' in category_data:
			del category_data['parent']
		category_data.parent_id = parent_id
		category_data.channel_id = self.get_channel_id()
		category_data.channel_category_id = convert.id
		category_data.code = self.name_to_code(category_data.name)
		category_id = self.get_model_category().create(category_data)
		return Response().success([category_id, category_data])

	def get_categories_main_export(self):
		id_src = self._state.push.process.categories.id_src
		if not id_src:
			id_src = ""
		limit = self._state.push.setting.categories
		where = self.get_model_category().create_where_condition('id', id_src, '>')
		try:
			categories = self.get_model_category().find_all(where = where, limit = limit)
			if not categories:
				return Response().finish()
		except Exception as e:
			self.log_traceback()
			return Response().error()
		return Response().success(tuple(map(lambda x: Prodict.from_dict(x), categories)))

	def get_categories_ext_export(self, categories):
		return Response().success()

	def get_category_parent(self, parent_id):
		parent = self.get_model_category().get(parent_id)
		if not parent:
			return False
		convert = self.convert_category_export(CatalogCategory(**parent), None)
		return convert

	def convert_category_export(self, category: CatalogCategory, categories_ext):
		category_data = category
		parent = CatalogCategory()
		parent.id = ''
		if category.parent_id:
			parent_data = self.get_category_parent(category.parent_id)
			if parent_data:
				parent = parent_data
		category_data.parent = parent
		return category_data

	def get_category_id_import(self, convert: CatalogCategory, category, categories_ext):
		return category.id

	# TODO: product
	def check_product_import(self, product_id, convert: Product):
		if self.is_inventory_process():
			return False
		if convert.litc_id:
			return convert.litc_id
		catalog = self.get_product_map(product_id)
		if catalog:
			return catalog
		return False

	def generate_sku(self, product_name):
		# if not product_name:
		# 	product_name = random_string(lower = True)
		# sku = string_to_base64(product_name)
		return random_string(lower = True)

	def convert_product(self, product: Product):
		"""

		:rtype: Product
		"""
		if not product.sku:
			product.sku = product.id
		unescape = ['name', 'sku', 'description', 'short_description', 'meta_title', 'meta_keyword']
		for row in unescape:
			product[row] = html_unescape(to_str(product.get(row))).strip(' ')
		# product.name = to_str(product.name).strip(' ')
		# if not product.sku:
		# 	product.sku = self.generate_sku(product.name)
		# product.sku = to_str(product.sku).strip(' ')

		product.lower_name = self.product_lower_name(product.name)
		product.price = to_decimal(product.price)
		if to_int(product.qty) < 0:
			product.qty = 0
		qty = to_decimal(product.qty)
		if not product.description:
			product.description = product.short_description
		if product.special_price.price:
			product.special_price.price = to_decimal(product.special_price.price)
		for tier_price in product.tier_prices:
			tier_price.price = to_decimal(tier_price.price)
			tier_price.qty = to_decimal(tier_price.qty)
		for group_price in product.group_prices:
			group_price.price = to_decimal(group_price.price)
			group_price.qty = to_decimal(group_price.qty)
		if product.channel:
			for channel_id, channel in product.channel.items():
				if channel.qty:
					channel.qty = to_decimal(channel.qty)
				if channel.price:
					channel.price = to_decimal(channel.price)
		for attribute in product.attributes:
			attribute.attribute_name = html_unescape(to_str(attribute.attribute_name))
			attribute.attribute_value_name = html_unescape(to_str(attribute.attribute_value_name))

		# inventory = ProductInventory()
		# inventory.location_id = self.get_warehouse_location_default()
		# inventory.on_hand = product.qty
		# inventory.available = product.qty
		# inventories = ProductInventories()
		# inventories.total_available = product.qty
		# inventories.total_on_hand = product.qty
		# inventories.inventory.set_attribute(to_str(self.get_warehouse_location_default()), inventory)
		# product.inventories = inventories
		if isinstance(product.tags, list):
			product.tags = ','.join(product.tags)
		images_import = list()
		custom_manage_stock = self.is_custom_manage_stock()
		if custom_manage_stock is not None:
			product.manage_stock = custom_manage_stock
		if product.variants:
			try:
				options = self.variants_to_option(product.variants)
				for option_name, option_values in options.items():
					product.variant_options.append({
						'option_name': option_name,
						'option_values': option_values
					})
			except Exception:
				self.log_traceback('options')
			for variant in product.variants:
				dimension_fields = ['length', 'width', 'height', 'weight', 'dimension_units', 'weight_units']
				for field in dimension_fields:
					if variant.get(field) and not product.get(field):
						product[field] = variant[field]
				if variant.thumb_image.url:
					product.images.append(variant.thumb_image)
				if variant.images:
					product.images += variant.images
		if not product.thumb_image.url and product.images:
			product.thumb_image = copy.deepcopy(product.images[0])
			del product.images[0]
		if product.thumb_image.url:
			image_url = self.upload_image(product.thumb_image.url, self.create_destination_product_image(product.id, product.thumb_image.url))
			if image_url:
				product.thumb_image.url = image_url
			product.thumb_image.url = html_unquote(product.thumb_image.url)
			images_import.append(product.thumb_image.url)

		product_images = list()
		for image in product.images:
			if not image.url:
				continue
			image_url = self.upload_image(image.url, self.create_destination_product_image(product.id, image.url))
			if image_url:
				image.url = image_url
			image.url = html_unquote(image.url)
			if image.url in images_import:
				continue
			images_import.append(image.url)
			product_images.append(image)
		product.images = product_images
		if self.get_image_limit() and to_len(product.images) > self.get_image_limit() - 1:
			all_images = copy.deepcopy(product.images)
			product.images = all_images[0:self.get_image_limit() - 1]
			product['all_images'] = all_images
		# if self._state.channel.default:
		# 	product.import_status = 'active'
		# else:
		# 	product.import_status = 'draft'

		# import fba inventory
		# if self._state.channel.config.api.get('fulfillment') == 'fba':
		# 	fba_inventory = product.pop('fba_inventory', None)
		# 	if fba_inventory:
		# 		product.inventories.inventory.set_attribute(fba_inventory['location_id'], fba_inventory)
		# 		for field in ['available', 'on_hand', 'reserved']:
		# 			product.inventories[f'total_{field}'] = sum(inventory[field] for field in product.inventories.inventory.values())
		product_skus = list()
		if product.variants:

			min_price = product['price']
			max_price = product['price']
			max_attributes = 0
			qty = 0
			attributes = list()
			for variant in product.variants:
				variant_sku = to_str(variant.sku)
				if variant_sku and variant_sku != to_str(product.sku) and variant_sku not in product_skus:
					product_skus.append(variant_sku)
				if custom_manage_stock is not None:
					variant.manage_stock = custom_manage_stock
				variant_attribute = list()
				variant = self.convert_product(variant)
				qty += to_int(variant.qty)

				for attribute in variant.attributes:
					if attribute.use_variant:
						variant_attribute.append(attribute)
				if to_len(variant_attribute) > max_attributes:
					max_attributes = to_len(variant_attribute)
					attributes = variant_attribute
				if variant['price'] > max_price:
					max_price = variant['price']
				if variant['price'] < min_price:
					min_price = variant['price']
			for attribute in attributes:
				product.variant_attributes.append(attribute.attribute_name)
			product.qty = qty
			product.min_price = min_price
			product.max_price = max_price
			product.product_skus = product_skus
			product.variant_count = to_len(product.variants)
		product.updated_time = 0
		product.qty = to_int(product.qty)
		decimal_fields = ['price', 'min_price', 'max_price', 'cost', 'msrp', 'weight', 'length', 'width', 'height']
		for field in decimal_fields:
			product[field] = to_decimal(product[field])
		category_name_list = sorted(list(map(lambda x: self.name_to_code(x), product.category_name_list)))
		product.category_lower_name = ','.join(category_name_list)
		if product.manage_stock and not product.qty:
			product.is_in_stock = False
		return product

	# TODO products
	def assign_template(self, data):
		template = self.get_template(data)
		if not template:
			return Response().error(Errors.TEMPLATE_NOT_FOUND)
		product = self.get_model_catalog().update_many({f"channel.channel_{data.get('channel_id')}.channel_id": data.get('channel_id')}, f"channel.channel_{data.get('channel_id')}.template_data", template)
		return product

	def get_template(self, data):
		if self._template:
			return self._template
		self._user_id = data.get('user_id')
		model_template = self.get_model_template()
		template = model_template.get(data.get('template_id'))

		data = {}
		for field in template['template']:
			data[field] = self.unset_data_template(model_template.get(template['template'][field]))
		return data

	def prepare_products_import(self, data = None):
		super(ModelWareHouse, self).prepare_products_import(data)
		self._state.pull.process.products.auto_build = True
		if isinstance(data, dict):
			if 'auto_build' in data:
				self._state.pull.process.products.auto_build = to_bool(data.get('auto_build'))

	def inventory_import(self, convert: Product, product, products_ext):
		product_data = get_row_from_list_by_field(products_ext, '_id', product['id'])
		if not product_data:
			return Response().error(Errors.PRODUCT_DATA_INVALID)
		if product_data.variant_count > 0:
			return Response().success()
		inventories = product_data['inventories']
		location_id = to_str(product['location_id'])
		inventory = inventories['inventory'].get(location_id)
		if not inventory:
			inventory = ProductInventory(location_id = location_id)
			inventories['inventory'][location_id] = inventory
		# Override import
		if product['import_type'] == 'override':
			inventory['reserved'] = product['reserved']
			inventory['on_hand'] = product['on_hand']
			inventory['available'] = inventory['reserved'] + inventory['on_hand']
		# Adjust import
		if product['import_type'] == 'adjustment':
			inventory['reserved'] += product['reserved']
			inventory['on_hand'] += product['on_hand']
			inventory['available'] = inventory['reserved'] + inventory['on_hand']
		for field in ('available', 'reserved', 'on_hand'):
			inventories[f'total_{field}'] = sum(inventory[field] for inventory in inventories['inventory'].values())
		update_response = self.product_update_fields(product_data['_id'], {'inventories': inventories, 'qty': inventories['total_available']})

		# update parent inventories
		if product_data['parent_id']:
			parent_product_data = get_row_from_list_by_field(products_ext, '_id', product_data['parent_id'])
			if not parent_product_data:
				return Response().error(Errors.PRODUCT_DATA_INVALID)
			children_where = self.get_model_catalog().create_where_condition('parent_id', product_data['parent_id'], '==')
			children_data = self.get_model_catalog().find_all(children_where)
			parent_inventories = parent_product_data['inventories']
			# reset quantity and preserved index of location_id
			for parent_inventory in parent_inventories['inventory'].values():
				for field in ('available', 'reserved', 'on_hand'):
					parent_inventory[field] = 0
			for child_data in children_data:
				for child_inventory in child_data['inventories']['inventory'].values():
					child_location_id = to_str(child_inventory['location_id'])
					if child_location_id in parent_inventories['inventory']:
						parent_inventory = parent_inventories['inventory'][child_location_id]
						for field in ('available', 'reserved', 'on_hand'):
							parent_inventory[field] += child_inventory[field]
					else:
						parent_inventories['inventory'][child_location_id] = child_inventory
			for field in ('available', 'reserved', 'on_hand'):
				parent_inventories[f'total_{field}'] = sum(parent_inventory[field] for parent_inventory in parent_inventories['inventory'].values())
			update_response = self.product_update_fields(parent_product_data['_id'], {'inventories': parent_inventories, 'qty': parent_inventories['total_available']})
		return update_response

	def is_channel_import_parent(self):
		return self._state.channel.channel_type not in ['facebook']

	def import_product_parent(self, parent):
		parent_id = parent.id
		parent_product = self.get_product_warehouse_map(parent_id, return_product = True)
		if parent_product:
			return Response().success(parent_product)
		parent = self.add_channel_to_convert_product_data(parent, parent.id)
		product = self.product_import(parent, None, None)
		if product.result != Response.SUCCESS:
			return product
		# self.insert_map_product(product.data[1], product.data[0], parent.id)
		after_import = self.after_product_import(product.data[0], parent, None, None)
		return Response().success(product.data[1])

	def try_auto_link_product(self, product: Product):
		link_product = self.find_product_auto_link(product)
		if not link_product:
			return Response().error()
		channel = product.channel.get(f'channel_{self.get_channel_id()}')
		channel.link_status = ProductChannel.LINKED
		channel.description = product.description
		channel.thumb_image = product.thumb_image
		channel.images = product.images
		channel.auto_link = True
		if product.variant_attributes:
			channel.variant_attributes = product.variant_attributes
		if product.product_skus:
			channel.product_skus = product.product_skus
		self.get_model_catalog().update_field(link_product['_id'], f'channel.channel_{self.get_channel_id()}', channel)
		link_product.channel.set_attribute(f"channel_{self.get_channel_id()}", channel.to_dict())
		if product.variants:
			self.auto_link_variant(product, link_product)
		return Response().success(data = [link_product['_id'], link_product])

	def create_product_channel_data(self, product, channel_id):
		channel = ProductChannel()
		channel.product_id = to_str(product.id)
		channel.sku = product.sku
		channel.channel_id = channel_id
		channel.qty = product.qty
		channel.price = product.price
		channel.link_status = ProductChannel.LINKED
		if product.template_data:
			channel.template_data = copy.deepcopy(product.template_data)
			del product['template_data']
		if product.channel_data:
			channel.update(product.channel_data)
			del product['channel_data']
		return [channel, product]

	def auto_link_variant(self, product: Product, link_product: Product):
		link_variants = self.get_variants(link_product, self.get_channel_default_id())
		link_variants_key = dict()
		for variant in link_variants:
			link_variants_key[self.variant_key_generate(variant)] = variant
		link_ids = list()
		product_variants = product.variants
		unlink_variant = list()
		for variant in product_variants:
			key_generate = self.variant_key_generate(variant)
			if not link_variants_key.get(key_generate):
				unlink_variant.append(variant)
				continue
			link_variant = link_variants_key[key_generate]
			link_ids.append(link_variant['_id'])
			variant_channel = variant.channel.get(f'channel_{self.get_channel_id()}')
			variant_channel.link_status = ProductChannel.LINKED
			self.get_model_catalog().update_field(link_variant['_id'], f'channel.channel_{self.get_channel_id()}', variant_channel)
		create_variants = list()
		create_products = list()
		for variant in unlink_variant:
			'''
			variant: Product
			'''
			if self.is_valid_variant(variant, product.variant_attributes):
				del variant['variants']
				variant.parent_id = link_product['_id']
				create_variants.append(variant)
			else:
				variant.is_variant = False
				if not self.get_product_map(variant.id):
					create_products.append(variant)

		if create_variants:
			variant_ids = self.get_model_catalog().create_many(create_variants)
		if create_products:
			product_ids = self.get_model_catalog().create_many(create_products)
		return

	def get_available_variant_link(self, variant, link_variants, link_ids):
		attributes = ['sku', 'name']
		for attribute in attributes:
			for product_variant in link_variants:
				if product_variant['_id'] in link_ids:
					continue
				if product_variant.get(attribute) == variant.get(attribute):
					return product_variant
		return False

	def find_product_auto_link(self, product: Product) -> Product or bool:
		channel_default_id = self.get_channel_default_id()
		where = dict()
		where_name = [
			self.get_model_catalog().create_where_condition('sku', product.sku, "="),
			self.get_model_catalog().create_where_condition('name', product.name, "="),
			self.get_model_catalog().create_where_condition('lower_name', product.lower_name, "="),
		]
		where.update(self.get_model_catalog().create_where_condition(None, where_name, 'or'))
		where.update(self.get_model_catalog().create_where_condition('is_variant', product.is_variant))
		if product.variants:
			where.update(self.get_model_catalog().create_where_condition('variant_count', 0, '>'))
		else:
			where.update(self.get_model_catalog().create_where_condition('variant_count', 0))

		where.update(self.get_model_catalog().create_where_condition(f'channel.channel_{channel_default_id}.status', 'active'))
		where.update(self.get_model_catalog().create_where_condition(f'channel.channel_{self.get_channel_id()}.status', 'active', '!='))
		product_link = self.get_model_catalog().find_all(where)
		if not product_link:
			return False
		return product_link[0]

	def get_category_by_name(self, category_name):
		category_code = self.name_to_code(category_name)
		if self._categories.get(category_code):
			return self._categories.get(category_code)
		check_category = self.get_model_category().find('code', category_code)
		if check_category:
			self._categories[category_code] = check_category['_id']
			return check_category['_id']
		category_id = self.get_model_category().create({'name': category_name, 'code': category_code, 'channel_id': self.get_channel_id()})
		if category_id:
			self._categories[category_code] = category_id
			return category_id
		return False

	def product_import(self, convert: Product, product, products_ext):
		if self.is_inventory_process():
			return self.inventory_import(convert, product, products_ext)
		if not self.is_channel_default():
			if not self.check_product_available_import(notify = True):
				return Response().create_response('stop')
			self._total_product += 1
			self._total_product_batch_import += 1
		convert = self.convert_product(convert)
		if convert.channel_data:
			del convert['channel_data']
		if not convert.sku:
			convert.sku = self.generate_sku(convert.name)
		if not self.is_channel_default() and self.is_auto_build():
			auto_build = self.try_auto_link_product(convert)
			if auto_build.result == Response.SUCCESS:
				return auto_build
		if self.is_channel_default():
			category_ids = list()
			if convert.category_name_list:
				for category in convert.category_name_list:
					category_id = self.get_category_by_name(category)
					if category_id:
						category_ids.append(category_id)
			convert.category_ids = category_ids
		variants = copy.deepcopy(convert.variants)
		parent_product = copy.deepcopy(convert.parent)
		del convert['variants']
		del convert['parent']

		# categories = list()
		# for category in convert.categories:
		# 	category_id = self.get_category_map(category.id)
		# 	if category_id:
		# 		category_data = copy.deepcopy(category)
		# 		category_data.id = category_id
		# 		categories.append(category_data)
		# convert.categories = categories
		if parent_product:
			parent = self.import_product_parent(parent_product)
			if parent.result != Response.SUCCESS:
				return parent
			if self.is_valid_variant(convert, parent.data.variant_attributes):
				convert.is_variant = True
				convert.parent_id = parent.data['_id']
				catalog_id = self.get_model_catalog().create(convert)
				self.get_model_catalog().update_field(parent.data['_id'], 'variant_count', parent.data.variant_count + 1)
				return Response().success([catalog_id, convert])
		valid_variant = 0
		if variants:
			for variant in variants:
				if self.is_valid_variant(variant, convert.variant_attributes):
					valid_variant += 1
			convert.variant_count = valid_variant
		catalog_id = ''
		if not convert.variants or valid_variant > 1 or self.is_channel_import_parent():
			convert['updated_time'] = time.time()
			catalog_id = self.get_model_catalog().create(convert)
		create_variants = list()
		create_products = list()
		for variant in variants:
			'''
			variant: Product
			'''
			if not variant.sku:
				variant.sku = self.generate_sku(variant.name)
			if not variant.name:
				variant_name = convert.name
				for attribute in variant.attributes:
					if not attribute.use_variant:
						continue
					variant_name += f" - {attribute.attribute_value_name}"
				variant.name = variant_name
			if self.is_valid_variant(variant, convert.variant_attributes):
				del variant['variants']
				variant.parent_id = catalog_id
				create_variants.append(variant)
			else:
				variant.is_variant = False
				if not self.get_product_map(variant.id):
					create_products.append(variant)

		if create_variants:
			variant_ids = self.get_model_catalog().create_many(create_variants)
		if create_products:
			product_ids = self.get_model_catalog().create_many(create_products)

		return Response().success([catalog_id, convert])

	def after_product_import(self, product_id, convert: Product, product, products_ext):
		return Response().success()

	def finish_product_import(self):
		if not self._is_update and not self.is_refresh_process():
			name = "Main Store" if self.is_channel_default() else self._state.channel.channel_type + ' Listing'
			notification_data = {
				'code': '',
				'content': Messages.LISTING_IMPORT_CONTENT.format(name),
				'activity_type': 'listing_import',
				'description': Messages.LISTING_IMPORT.format(self._state.channel.channel_type),
				'date_requested': self._date_requested,
				'result': Activity.SUCCESS
			}
			notification = self.create_activity_notification(**notification_data)
		if self.is_csv_add_new():
			feed_data = {
				'feed_id': to_int(self.get_sync_id()),
				'message': Messages.FEED_PRODUCT_ADD.format(self._state.pull.process.products.new_entity or self._state.pull.process.products.imported),
				'created_at': get_current_time(),
				'result': Activity.SUCCESS
			}
			notification = self.create_activity_feed(**feed_data)
		return Response().success()

	# TODO: PUSH
	def display_push_warehouse(self):
		return Response().success()

	def prepare_push_warehouse(self, data = None):
		if data.get('product_ids'):
			self._state.push.process.products.id_src = 0
			self._state.push.process.products.imported = 0
			self._state.push.process.products.error = 0
			self._state.push.process.products.execute_ids = data['product_ids']
		else:
			self._state.push.process.products.execute_ids = False
		entities = ('products', 'orders')
		for entity in entities:
			if not self.is_inventory_process():
				self._state.push.process[entity]['condition'] = list()
				if not data.get('condition') or not isinstance(data['condition'], dict) or not data['condition'].get(entity) or not self.validate_condition_push(data['condition'][entity]):
					continue
				self._state.push.process[entity]['condition'] = list(map(lambda x: Prodict.from_dict(x), data['condition'][entity]))
			self._state.push.process.products.id_src = 0
			self._state.push.process.products.imported = 0
			self._state.push.process.products.error = 0
		id_src = self._state.push.process.products.id_src
		where = dict()
		if self._state.channel.channel_type not in self.channel_no_parent():
			channel = self.get_channel_by_id(self.get_channel_id())
			if not channel.get('custom_linked_product'):
				where.update(self.get_model_catalog().create_where_condition('is_variant', False, '='))
			else:
				where_show_list = [
					self.get_model_catalog().create_where_condition('is_variant', False, '='),
					self.get_model_catalog().create_where_condition(f'channel.channel_{self.get_channel_id()}.show_in_grid', True)
				]
				where = self.get_model_catalog().create_where_condition(None, where_show_list, 'or')
		# if not self._state.channel.default:
		# 	where.update(self.get_model_catalog().create_where_condition('import_status', 'active', '='))
		if self._state.push.process.products.execute_ids is not False:
			where.update(self.get_model_catalog().create_where_condition('_id', self._state.push.process.products.execute_ids, 'in'))
		if self._state.push.process.products.condition:
			for condition in self._state.push.process.products.condition:
				where.update(self.get_model_catalog().create_where_condition(condition.field, condition.value, condition.condition))
		if self.is_inventory_process():
			if not self.is_insert_updated_time():
				self._state.push.process.products.updated_time = 0.0
			updated_time = self._state.push.process.products.updated_time
			if updated_time:
				where.update(self.get_model_catalog().create_where_condition('updated_time', updated_time, '>'))
		products = self.get_model_catalog().count(where)
		if not self.is_inventory_process() and not self._template_update:
			update = {
				f"channel.channel_{self.get_src_channel_id()}.publish_status": ProductChannel.PUSHING,
				f"channel.channel_{self.get_src_channel_id()}.publish_action": self.get_publish_action(),
			}
			self.get_model_catalog().update_many(where, update)
		self._state.push.process.products.total = products
		self._state.push.process.products.total_view = products
		if self.is_inventory_process() and products:
			self._state.push.process.products.total = -1

		if self._state.config.categories:
			id_src_category = self._state.push.process.categories.id_src
			where_category = dict()
			where_category.update(self.get_model_category().create_where_condition('id', id_src_category, '>'))
			categories = self.get_model_category().count(where_category)
			self._state.push.process.categories.total = categories

		return Response().success()

	def validate_condition_push(self, condition):
		if not isinstance(condition, list):
			return False
		for row in condition:
			if not isinstance(row, dict) or not to_str(row.get('field')) or not to_str(row.get('value')):
				return False
		return True

	# TODO Product
	def get_product_by_id(self, product_id):
		catalog = self.get_model_catalog().find('id', product_id)
		if catalog:
			return catalog
		return False

	def edit_product(self, product_id, data):
		return Response().success()

	def update_product(self, data):
		return Response().success(data)

	def filter_field_product(self, data):
		filter_data = dict()
		fields = Catalog.FILTER
		for data_key, data_value in data.items():
			if data_key in fields:
				filter_data[data_key] = data_value
		return filter_data

	def get_product_filter_conditions(self, product_filters):
		if self._product_filter_conditions:
			return self._product_filter_conditions
		where = dict()
		channel_default_id = self.get_channel_default_id()
		where.update(self.get_model_catalog().create_where_condition(f"channel.channel_{channel_default_id}.status", "active"))
		if self._state.channel.channel_type not in self.channel_no_parent():
			where.update(self.get_model_catalog().create_where_condition('is_variant', False, '='))
		if self._state.push.process.products.condition:
			for condition in self._state.push.process.products.condition:
				where.update(self.get_model_catalog().create_where_condition(condition.field, condition.value, condition.condition))
		# if self.is_inventory_process():
		# 	where.update(self.get_model_catalog().create_where_condition('updated_time', to_int(self._updated_time), ">="))

		min_qty = product_filters.get('minQty') or product_filters.get('min_qty')
		max_qty = product_filters.get('maxQty') or product_filters.get('max_qty')
		if min_qty and max_qty:
			where.update(self.get_model_catalog().create_where_condition('qty', (to_int(min_qty), to_int(max_qty)), 'range'))
		elif min_qty:
			where.update(self.get_model_catalog().create_where_condition('qty', to_int(min_qty), '>='))
		elif max_qty:
			where.update(self.get_model_catalog().create_where_condition('qty', to_int(max_qty), '<='))
		min_price = product_filters.get('min_price')
		max_price = product_filters.get('max_price')

		if min_price and max_price:
			where.update(self.get_model_catalog().create_where_condition('price', (to_decimal(min_price), to_decimal(min_price)), 'range'))
		elif min_qty:
			where.update(self.get_model_catalog().create_where_condition('price', to_decimal(min_price), '>='))
		elif max_qty:
			where.update(self.get_model_catalog().create_where_condition('price', to_decimal(max_price), '<='))
		where_title_sku = []
		if product_filters.get('sku'):
			sku = html_unquote(to_str(product_filters.get('sku')).strip())
			sku_contains = self.get_model_catalog().create_where_condition('sku', sku, 'like')

			where_title_sku.append(self.get_model_catalog().create_where_condition(None, [
				self.get_model_catalog().create_where_condition('sku', sku, 'like'),
				self.get_model_catalog().create_where_condition('product_skus', [sku_contains['sku']], 'in')
			], 'or'))
		if product_filters.get('title'):
			name = html_unquote(to_str(product_filters.get('title')).strip())
			where_title_sku.append(self.get_model_catalog().create_where_condition(None, [
				self.get_model_catalog().create_where_condition('name', name, 'like'),
				self.get_model_catalog().create_where_condition('lower_name', self.product_lower_name(name), 'like'),
			], 'or'))
		if len(where_title_sku) == 2:
			where_title_sku = self.get_model_catalog().create_where_condition(None, where_title_sku, 'and')
		elif len(where_title_sku) == 1:
			where_title_sku = where_title_sku[0]
		if where_title_sku:
			where = self.get_model_catalog().create_where_condition(None, [where, where_title_sku], 'and')
		for field in ['mpn', 'bpn', 'ean', 'upc']:
			if product_filters.get(field):
				value = html_unquote(to_str(product_filters.get(field)).strip())
				where.update(self.get_model_catalog().create_where_condition(field, value))

		where.update(self.get_model_catalog().create_where_condition('parent_id', False, '='))
		if to_int(product_filters.get("in_channel")):
			where.update(self.get_model_catalog().create_where_condition(f'channel.channel_{to_int(product_filters.get("in_channel"))}.status', ['active', 'draft', 'error'], 'in'))
		if to_int(product_filters.get("nin_channel")):
			where.update(self.get_model_catalog().create_where_condition(f'channel.channel_{to_int(product_filters.get("nin_channel"))}.status', ['active', 'draft', 'error'], 'nin'))
		self._product_filter_conditions = where
		return where

	def get_products_filter_export(self, product_filters):
		id_src = self._state.push.process.products.id_src
		limit = 50
		where = self.get_product_filter_conditions(product_filters)
		if id_src and to_object_id(id_src):
			where_id = None
			if '_id' in where:
				where_id = {"_id": where['_id']}
				del where['_id']
			where_id_src = self.get_model_catalog().create_where_condition('_id', id_src, '>')
			if where_id:
				where.update(self.get_model_catalog().create_where_condition(None, [where_id, where_id_src], 'and'))
			else:
				where.update(where_id_src)

		try:
			product_option = {
				'where': where,
				'limit': limit,
			}

			products = self.get_model_catalog().find_all(**product_option)
			if not products:
				return Response().finish()
		except Exception as e:
			self.log_traceback()
			return Response().error()
		return Response().success(tuple(map(lambda x: Prodict.from_dict(x), products)))

	def get_products_main_export(self):
		id_src = self._state.push.process.products.id_src
		limit = 50
		where = dict()

		if self._state.channel.channel_type not in self.channel_no_parent():
			channel = self.get_channel_by_id(self.get_channel_id())
			if not channel.get('custom_linked_product'):
				where.update(self.get_model_catalog().create_where_condition('is_variant', False, '='))
			else:
				where_show_list = [
					self.get_model_catalog().create_where_condition('is_variant', False, '='),
					self.get_model_catalog().create_where_condition(f'channel.channel_{self.get_channel_id()}.show_in_grid', True)
				]
				where = self.get_model_catalog().create_where_condition(None, where_show_list, 'or')
		# if not self._state.channel.default:
		# 	where.update(self.get_model_catalog().create_where_condition('import_status', 'active', '='))
		if self._state.push.process.products.execute_ids is not False:
			where.update(self.get_model_catalog().create_where_condition('_id', self._state.push.process.products.execute_ids, 'in'))
		if self._state.push.process.products.condition:
			for condition in self._state.push.process.products.condition:
				where.update(self.get_model_catalog().create_where_condition(condition.field, condition.value, condition.condition))
		# if self.is_inventory_process():
		# 	where.update(self.get_model_catalog().create_where_condition('updated_time', to_int(self._updated_time), ">="))
		if self.is_inventory_process():
			updated_time = self._state.push.process.products.updated_time
			if updated_time:
				where.update(self.get_model_catalog().create_where_condition('updated_time', updated_time, '>'))
		else:
			if id_src and to_object_id(id_src):
				where_id = None
				if '_id' in where:
					where_id = {"_id": where['_id']}
					del where['_id']
				where_id_src = self.get_model_catalog().create_where_condition('_id', id_src, '>')
				if where_id:
					where.update(self.get_model_catalog().create_where_condition(None, [where_id, where_id_src], 'and'))
				else:
					where.update(where_id_src)
		try:
			product_option = {
				'where': where,
				'limit': limit,
			}
			if self.is_inventory_process():
				product_option['order_by'] = 'updated_time'

			products = self.get_model_catalog().find_all(**product_option)
			if not products:
				return Response().finish()
		except Exception as e:
			self.log_traceback()
			return Response().error()
		return Response().success(tuple(map(lambda x: Prodict.from_dict(x), products)))

	def get_products_ext_export(self, products):
		variants = list()
		parents = list()
		categories = list()
		# Get variants
		# if self._state.channel.channel_type not in self.channel_no_parent():
		# 	parent_ids = list()
		# 	for product in products:
		# 		if to_int(product.variant_count) > 0:
		# 			parent_ids.append(product._id)
		# 	if parent_ids:
		# 		where_variant = {
		# 			'$or':
		# 				[
		# 					{
		# 						'$and': [
		# 							self.get_model_catalog().create_where_condition('parent_id', parent_ids, 'in'),
		# 							self.get_model_catalog().create_where_condition(f'channel.channel_{self._channel_id}.status', 'unlink', '!=')
		# 						]
		# 					},
		# 					self.get_model_catalog().create_where_condition(f'channel.channel_{self._channel_id}.parent_mongo_id', parent_ids, 'in')
		# 				]
		# 		}
		# 		variants = self.get_model_catalog().find_all(where_variant)
		# Get parents
		if self._state.channel.channel_type in self.channel_no_parent():
			parent_ids = list(filter(None, duplicate_field_value_from_list(products, 'parent_id')))
			if parent_ids:
				where_parents = self.get_model_catalog().create_where_condition('_id', parent_ids, 'in')
				parents = self.get_model_catalog().find_all(where_parents)
		# Get categories
		category_ids = list()
		for product in products:
			category_ids.extend(duplicate_field_value_from_list(product.get('categories', []), 'id'))
		# if category_ids:
		# 	where_category = self.get_model_category().create_where_condition('_id', category_ids, 'in')
		# 	categories = self.get_model_category().find_all(where_category)
		products_ext = {
			# 'variants': variants,
			'parents': parents,
			'categories': []
		}
		return Response().success(products_ext)

	def convert_product_export(self, product, products_ext):
		convert = product
		if isinstance(convert.tags, list):
			convert.tags = ','.join(convert.tags)
		unescape = ['name', 'sku', 'description', 'short_description', 'meta_title', 'meta_keyword']
		for row in unescape:
			convert[row] = html_unescape(to_str(convert.get(row))).strip(' ')
		if to_int(product.variant_count) > 0:
			variants = self.get_variants(product, self.get_src_channel_id())
			for variant in variants:
				# variant = self.update_product_from_channel(variant)
				if isinstance(variant.tags, list):
					variant.tags = ','.join(variant.tags)
					for row in unescape:
						variant[row] = html_unescape(to_str(variant.get(row)))
			convert.variants = variants
		else:
			convert.variants = []
		for category in product.categories:
			category_data = get_row_from_list_by_field(products_ext['categories'], '_id', category.id)
			if category_data:
				category.update(category_data)
		return convert

	def update_product_from_channel(self, product: Product):
		convert = self._update_product_from_channel(product)
		if convert.variants:
			for variant in convert.variants:
				variant = self._update_product_from_channel(variant)
		return convert

	def _update_product_from_channel(self, product: Product, unset = ('channel_id', 'product_id', 'status', '_id')):
		field = "channel.channel_{}".format(self._state.channel.id)
		channel_data = dict()
		channel_id = self._state.channel.id
		if self.is_channel_default():
			channel_id = self.get_src_channel_id()
		if product.channel.get('channel_{}'.format(channel_id)):
			channel_data = copy.deepcopy(product.channel.get('channel_{}'.format(channel_id)))
			for field in unset:
				if field in channel_data:
					del channel_data[field]
		unescape = ['name', 'sku', 'description', 'short_description', 'meta_title', 'meta_keyword']
		for row in unescape:
			if not channel_data.get(row):
				continue
			channel_data[row] = html_unescape(to_str(channel_data.get(row)))
		copy_channel_data = copy.deepcopy(channel_data)
		for channel_key, value in copy_channel_data.items():
			if channel_key in ['qty', 'price', 'manage_stock', 'is_in_stock'] and self.is_inventory_process():
				if channel_key in channel_data:
					del channel_data[channel_key]
				continue

			if value is None or value == '' and channel_key in channel_data:
				del channel_data[channel_key]
		product.update(channel_data)
		if product.attributes and not isinstance(product.attributes, list):
			product.attributes = list(product.attributes.values())
		return product

	def allow_update(self):
		return (
			'product_skus',
			'variant_options',
			'variant_attributes',
			'variant_count',
			'special_price',
			'name', 'sku', 'model', 'condition', 'upc', 'barcode', 'ean', 'asin', 'gtin', 'gcid', 'epid', 'isbn', 'categories',
			'mpn', 'bpn', 'url_key', 'description', 'short_description', 'meta_title', 'meta_keyword', 'tags', 'price',
			'msrp', 'weight', 'length', 'width', 'height', 'status', 'manage_stock', 'qty', 'is_in_stock', 'brand', 'updated_at', 'seo_url',
			'images', 'attributes'
		)

	def _product_update(self, product_id, convert: Product, product, products_ext):
		current_product = self.get_model_catalog().get(product_id)
		channel_data = current_product.channel.get(f"channel.channel_{self._state.channel.id}")
		update_data = dict()
		for field in self.allow_update():
			if convert.get(field) != current_product.get(field):
				update_data[field] = convert.get(field)
		if update_data:
			channel_data.update(update_data)
			self.get_model_catalog().update(product_id, channel_data)
		return True

	def product_bulk_edit(self, product_id, convert: Product, product = None, products_ext = None, current_product: Product = None, update_image = True):
		convert = self.convert_product(convert)
		if not current_product:
			current_product = self.get_model_catalog().get(product_id)
			if isinstance(current_product, dict):
				current_product = Prodict(**current_product)
		update_data = dict()
		allow_update = "name,qty,price,description,brand,height,length,width,dimension_units,weight,weight_units,images".split(',')
		if convert.allow_update:
			allow_update = convert.allow_update
		if isinstance(allow_update, str):
			allow_update = allow_update.split(',')
		for field in allow_update:
			if convert.get(field) != current_product.get(field):
				update_data[field] = convert.get(field)
		if 'images' in allow_update:
			if convert.thumb_image.url != current_product.thumb_image.url:
				update_data['thumb_image'] = convert.thumb_image
			update_data['images'] = convert.images
		channel_update_data = dict()
		for row, value in update_data.items():
			channel_update_data[f"channel.channel_{self.get_channel_id()}.{row}"] = value
		update_data.update(channel_update_data)
		if update_data.get('qty') or update_data.get('price'):
			time.sleep(0.001)
			update_data['updated_time'] = time.time()
		self.get_model_catalog().update(product_id, update_data)
		if convert.variants:
			for variant in convert.variants:
				if self.get_channel_type() == 'bulk_edit':
					variant_id = variant.id
					current_variant = self.get_model_catalog().get(variant_id)
					if not current_variant or current_variant.parent_id != product_id or not current_variant.channel.get(f'channel_{self.get_channel_default_id()}') or not current_variant.channel[f'channel_{self.get_channel_default_id()}'].get('product_id'):
						continue
				else:
					variant_channel_id = variant.id
					current_variant = self.get_product_map(variant_channel_id, self.get_channel_id(), True)
					if not current_variant:
						continue
					variant_id = current_variant['_id']
				self.product_bulk_edit(variant_id, variant, current_product = current_variant)
		return Response().success()

	def product_update(self, product_id, convert: Product, product = None, products_ext = None, current_product: Product = None, is_variant = False):
		if self.get_channel_type() in ['bulk_edit', 'ebay'] or self.is_csv_update():
			return self.product_bulk_edit(product_id, convert, product, products_ext, current_product)
		convert = self.convert_product(convert)
		if not current_product:
			current_product = self.get_model_catalog().get(product_id)
			if isinstance(current_product, dict):
				current_product = Prodict(**current_product)
		if not self.is_channel_default():
			current_product = self.update_product_from_channel(current_product)
		update_data = dict()
		is_updated_time = False
		allow_update = self.allow_update()
		if convert.allow_update:
			allow_update = convert.allow_update
			if isinstance(allow_update, str):
				allow_update = allow_update.split(',')
		for field in allow_update:
			if field in ['images', 'attributes', 'categories']:
				continue
			if convert.get(field) != current_product.get(field):
				if field in ['qty', 'price', 'manage_stock', 'is_in_stock']:
					is_updated_time = True
				update_data[field] = convert.get(field)
		if (self.is_channel_default() or current_product.src.channel_id == self.get_channel_id()) and 'images' in allow_update:
			if convert.thumb_image.url != current_product.thumb_image.url:
				update_data['thumb_image'] = convert.thumb_image
			if self.is_difference_image(convert.images, current_product.images):
				update_data['images'] = convert.images
		if 'attributes' in allow_update:
			update_data['attributes'] = convert.attributes
		if self.is_channel_default() and 'categories' in allow_update:
			if current_product.category_lower_name != convert.category_lower_name:
				category_ids = list()
				if convert.category_name_list:
					for category in convert.category_name_list:
						category_id = self.get_category_by_name(category)
						if category_id:
							category_ids.append(category_id)
				update_data['category_ids'] = category_ids
		data_update = copy.deepcopy(update_data)
		if not self.is_channel_default():
			channel_data = current_product.channel.get(f"channel_{self._state.channel.id}")
			new_channel_data = convert.channel.get(f"channel_{self._state.channel.id}")
			convert_channel_data = convert.channel_data
			if convert_channel_data:
				channel_data.update(convert_channel_data)
			if 'status' in update_data:
				del update_data['status']
			channel_data.update(update_data)
			# channel_data.update(convert.channel_data)
			if convert.template_data or new_channel_data.template_data:
				channel_data.template_data = convert.template_data or new_channel_data.template_data
			data_update = {f"channel.channel_{self._state.channel.id}": channel_data}
		else:
			for row, value in update_data.items():
				if row == 'status':
					continue
				data_update[f"channel.channel_{self.get_channel_id()}.{row}"] = value
		if self.get_channel_type() != 'amazon':
			if convert.variants:
				variants = self.get_variants(current_product, self.get_channel_id())
				current_variants = dict()
				channel_variant_ids = duplicate_field_value_from_list(convert.variants, 'id')
				channel_variant_ids = list(map(lambda x: str(x), channel_variant_ids))
				current_variant_ids = list()
				for variant in variants:
					variant_id = to_str(variant.channel.get(f"channel_{self._channel_id}", dict()).get('product_id'))
					if not variant_id or variant_id not in channel_variant_ids:
						self.product_deleted(variant['_id'], variant)
						continue
					current_variants[variant['_id']] = variant
					current_variant_ids.append(variant_id)
				new_variant = list()
				valid_variants = list()
				variant_product = list()
				for channel_variant in convert.variants:
					if self.is_valid_variant(channel_variant, current_product.variant_attributes):
						valid_variants.append(channel_variant)
					else:
						variant_product.append(channel_variant)
				for channel_variant in valid_variants:
					channel_variant_id = to_str(channel_variant['id'])
					if channel_variant_id not in current_variant_ids:
						channel_variant = self.convert_product(channel_variant)
						self.add_channel_to_convert_product_data(channel_variant, channel_variant['id'])
						del channel_variant['variants']
						del channel_variant['id']
						channel_variant['parent_id'] = product_id
						new_variant.append(channel_variant)
						continue
					for variant_id, variant in current_variants.items():
						map_variant_id = to_str(variant.channel.get(f"channel_{self._channel_id}", dict()).get('product_id'))
						if channel_variant_id != map_variant_id:
							continue
						if variant.qty != channel_variant.qty or variant.price != channel_variant.price or variant.manage_stock != channel_variant.manage_stock:
							is_updated_time = True
						self.product_update(variant_id, channel_variant, current_product = variant, is_variant = True)
				for channel_variant in variant_product:
					channel_variant = self.convert_product(channel_variant)
					current_variant = self.get_product_map(channel_variant.id, return_product = True)
					if current_variant:
						self.product_update(current_variant['_id'], channel_variant, current_product = current_variant, is_variant = True)
					else:
						del channel_variant['variants']
						# del channel_variant['id']
						channel_variant.parent_id = product_id
						channel_variant = self.add_channel_to_convert_product_data(channel_variant, channel_variant['id'])
						new_variant.append(channel_variant)
				if new_variant:
					if not variants:
						data_update['variant_attributes'] = convert.variant_attributes
						data_update['variant_options'] = convert.variant_options
						data_update['variant_count'] = convert.variant_count
					is_updated_time = True
					self.get_model_catalog().create_many(new_variant)
			else:
				variants = self.get_variants(current_product, self.get_channel_id())
				for variant in variants:
					self.product_deleted(variant['_id'], variant)
				all_channel = self.get_all_channels()
				for channel_id, channel_data in all_channel.items():
					if is_updated_time and current_product.channel.get(f"channel_{channel_id}") and current_product.channel[f"channel_{channel_id}"].get("parent_id"):
						self.get_model_catalog().update_field(current_product.channel[f"channel_{channel_id}"].get("parent_id"), "updated_time", time.time())
						is_updated_time = False
		time_update = time.time()
		if is_updated_time:
			time.sleep(0.1)
			data_update['updated_time'] = time_update

		if data_update:
			if self.is_channel_default():
				for channel_id, value in current_product.channel.items():
					if value.status not in ['draft', 'error']:
						data_update[f'channel.{channel_id}.edited'] = True
			self.get_model_catalog().update(product_id, data_update)
		if not is_variant and current_product.parent_id:
			self.update_qty_for_parent(current_product.parent_id)

		return Response().success()

	def get_product_id_import(self, convert: Product, product, products_ext):
		return product['_id']

	def get_product_updated_time(self, product):
		return product.updated_time

	def product_update_fields(self, product_id, update_data):
		update = self.get_model_catalog().update_fields(product_id, update_data)
		if update:
			return Response().success()
		return Response().error()

	def mapping_construct_data(self, construct: dict, data: dict):
		map_data = dict()
		for key, value in construct.items():
			if data.get(key):
				value = data[key]
				if isinstance(value, dict):
					value = self.mapping_construct_data(value, data[key])
			map_data[key] = value
		return map_data

	def process_product_before_import(self, product):
		product = dict(product)
		product_construct = Product().to_dict() if not product['is_variant'] else ProductVariant().to_dict()
		product_data = Product().to_dict()
		for field, value in product_construct.items():
			if product.get(field):
				value = product.get(field)
			product_data[field] = value
		if not product['is_variant'] and product.get('variants'):
			variants = list()
			for variant in product['variants']:
				variant = self.process_product_before_import(variant)
				variants.append(variant)
				product_data['variants'] = variants
		return Prodict.from_dict(product_data)

	# TODO: orders

	def check_order_import(self, order_id, convert: Order):
		order = self.get_order_map(order_id)
		return order if order else False

	def process_order_before_import(self, order):
		order = dict(order)
		order_data = self.mapping_construct_data(Order().to_dict(), order)
		return Prodict.from_dict(order_data)

	def sync_product_quantity(self, product_data, product, latest_status, old_status = None):
		product_data = copy.deepcopy(product_data)
		inventories = product.get('inventories', {})
		qty = product_data['qty']
		warehouse_inventories = product_data.get('warehouse_inventories', {})
		mapping_status = ' - '.join(map(str, (old_status, latest_status)))
		# - on_hand, + reserved ('open')
		if mapping_status in ['None - open', 'None - awaiting_payment', 'None - ready_to_ship', ]:
			inventories['total_on_hand'] -= qty
			inventories['total_reserved'] += qty
			for inventory in inventories['inventory'].values():
				if inventory['status'] != 'active':
					continue
				if inventory['on_hand'] - qty > 0:
					inventory['on_hand'] -= qty
					inventory['reserved'] += qty
					warehouse_inventories[to_str(inventory['location_id'])] = qty
					qty = 0
				else:
					qty -= inventory['on_hand']
					inventory['reserved'] += inventory['on_hand']
					warehouse_inventories[to_str(inventory['location_id'])] = inventory['on_hand']
					inventory['on_hand'] = 0
				inventory['available'] = inventory['reserved'] + inventory['on_hand']
			if qty != 0:
				inventory = list(inventories['inventory'].values())[0]
				inventory['on_hand'] -= qty
				inventory['reserved'] += qty
				warehouse_inventories[to_str(inventory['location_id'])] = qty
				inventory['available'] = inventory['reserved'] + inventory['on_hand']
		# + on_hand, - reserved ('cancel')
		elif mapping_status in ['open - canceled', 'awaiting_payment - canceled', 'ready_to_ship - canceled']:
			for location_id, location_qty in warehouse_inventories.items():
				inventories['total_on_hand'] += location_qty
				inventories['total_reserved'] -= location_qty
				for inventory in inventories['inventory'].values():
					if str(inventory['location_id']) == str(location_id):
						inventory['on_hand'] += location_qty
						inventory['reserved'] -= location_qty
					else:
						list(inventories['inventory'].values())[0]['on_hand'] += location_qty
						list(inventories['inventory'].values())[0]['reserved'] -= location_qty
		# - on_hand ('shipping', 'completed')
		elif mapping_status in ['None - shipping', 'None - completed', 'completed - completed']:
			inventories['total_on_hand'] -= qty
			inventories['total_available'] -= qty
			for inventory in inventories['inventory'].values():
				if inventory['status'] != 'active':
					continue
				if inventory['on_hand'] - qty > 0:
					inventory['on_hand'] -= qty
					warehouse_inventories[to_str(inventory['location_id'])] = qty
					qty = 0
				else:
					qty -= inventory['on_hand']
					warehouse_inventories[to_str(inventory['location_id'])] = inventory['on_hand']
					inventory['on_hand'] = 0
				inventory['available'] = inventory['reserved'] + inventory['on_hand']
			if qty != 0:
				inventory = list(inventories['inventory'].values())[0]
				inventory['on_hand'] -= qty
				warehouse_inventories[to_str(inventory['location_id'])] = qty
				inventory['available'] = inventory['reserved'] + inventory['on_hand']
		# - reserved ('shipping' or 'completed')
		elif mapping_status in ['open - shipping', 'open - completed', 'awaiting_payment - shipping', 'awaiting_payment - completed', 'ready_to_ship - shipping',
		                        'ready_to_ship - completed']:
			for location_id, location_qty in warehouse_inventories.items():
				inventories['total_reserved'] -= location_qty
				inventories['total_available'] -= location_qty
				for inventory in inventories['inventory'].values():
					if str(inventory['location_id']) == str(location_id):
						inventory['reserved'] -= location_qty
						inventory['available'] -= location_qty
					else:
						inventory = list(inventories['inventory'].values())[0]
						inventory['reserved'] -= location_qty
						inventory['available'] -= location_qty
		# + on_hand ('cancel')
		elif mapping_status in ['shipping - cancel']:
			for location_id, location_qty in product_data.get('inventory_tracking', {}).items():
				inventories['total_on_hand'] += location_qty
				inventories['total_available'] += location_qty
				for inventory in inventories['inventory'].values():
					if str(inventory['location_id']) == str(location_id):
						inventory['on_hand'] += location_qty
						inventory['available'] += location_qty
					else:
						inventory = list(inventories['inventory'].values())[0]
						inventory['on_hand'] += location_qty
						inventory['available'] += location_qty
		update_fields = {
			'qty': inventories['total_available'],
			'inventories': inventories
		}
		self.product_update_fields(product.get('_id'), update_fields)
		if product.parent_id:
			self.get_model_catalog().update_parent_product_inventories(product.parent_id)
		product_data['warehouse_inventories'] = warehouse_inventories
		return product_data

	def convert_order(self, convert: Order, order, orders_ext, is_import = False):
		order_products = list()
		product_ids = dict()
		link_status = Order.LINKED
		if convert.shipments:
			if isinstance(convert.shipments, list):
				convert.shipments = convert.shipments[0]
			if convert.shipments.tracking_company_code or convert.shipments.tracking_company:
				tracking_company = TrackingCompany(convert.shipments.tracking_company_code, convert.shipments.tracking_company)
				convert.shipments.tracking_company_code = tracking_company.get_code()
				convert.shipments.tracking_company = tracking_company.get_name()
		if not convert.products:
			return False
		for product in convert.products:
			product.subtotal = to_decimal(to_decimal(product.qty) * to_decimal(product.price), 2)
			if not product.total:
				product.total = product.subtotal
			# product_data = copy.deepcopy(product)
			if product.product_id:
				product.product_id = to_str(product.product_id)
				default_map, product_map = self.get_product_channel_default_map(product.product_id, return_product = True)
				if product_map:
					product.id = product_map.get('_id')
					product.product_name = product_map.name
					product.product_sku = product_map.sku
					product_ids[to_str(product_map.get('_id'))] = True
					product.parent_id = product_map.parent_id
					product.product_bpn = product_map.bpn
					if is_import and convert.status not in [Order.CANCELED]:
						new_qty = to_int(product_map.get('qty')) - to_int(product.qty)
						if new_qty < 0:
							product.status = 'outofstock'
							new_qty = 0
						time.sleep(0.01)
						update_data = {
							'qty': new_qty,
							"updated_time": time.time()
						}
						self.get_model_catalog().update(product_map.get('_id'), update_data)
						if product_map.parent_id:
							self.update_qty_for_parent(product_map.parent_id, channel_id = self.get_channel_default_id())
				# product_data = self.sync_product_quantity(product_data, product, convert.status)
				if not default_map:
					link_status = Order.UNLINK
				else:
					product.link_status = Order.LINKED

				product.product_name = html_unescape(product.product_name)
				product.product_sku = html_unescape(product.product_sku)
			else:
				return False
		# if product_data.get('warehouse_inventories'):
		# 	convert.is_assigned = True
		# order_products.append(product_data)
		convert.link_status = link_status
		# convert.products = order_products
		convert.product_ids = product_ids
		return convert

	def order_import(self, convert: Order, order, orders_ext):
		if not self.check_order_available_import(True):
			return Response().create_response('stop')

		convert = self.convert_order(convert, order, orders_ext, True)
		if not convert:
			return Response().error(code = Errors.ORDER_NO_PRODUCT)
		convert.channel_id = self.get_channel_id()
		all_channel = self.get_all_channels()
		channel_info = all_channel.get(self.get_channel_id())
		if channel_info:
			convert.channel_name = channel_info.name
		# if convert.status not in [Order.CANCELED]:
		# 	for product in convert.products:
		# 		update_field = {}
		# 		if product.id:
		# 			default_map, product_map = self.get_product_channel_default_map(product.product_id, return_product = True)
		# 			if default_map:
		# 				if to_int(product_map.get('qty')) >= to_int(product.qty):
		# 					update_field['qty'] = to_int(product_map.get('qty')) - to_int(product.qty)
		# 					self.get_model_catalog().update(product_map.get('_id'), update_field)
		# 				else:
		# 					update_field['qty'] = 0
		#
		# 					product.status = 'outofstock'

		channel_order_number = convert['order_number'] if convert.get('order_number') else convert['id']
		convert.order_number = self.create_order_number()
		convert.channel_order_number = to_str(channel_order_number)
		convert.imported_at = get_current_time()
		order_number_prefix = self.get_order_number_prefix()
		if order_number_prefix == '__channel_name__':
			convert.order_number_prefix = convert.channel_name
		convert.order_number_suffix = self.get_order_number_suffix()
		order_id = self.get_model_order().create(convert)
		return Response().success([order_id, convert])

	def order_update(self, order_id, convert: Order, order = None, orders_ext = None, current_order = None):
		if not current_order:
			current_order = self.get_model_order().get(order_id)
		if current_order:
			current_order = Prodict(**current_order)
		convert = self.convert_order(convert, None, None)
		if not convert:
			return Response().error(code = Errors.ORDER_NO_PRODUCT)
		field_update = ['link_status', 'products', 'product_ids', 'customer', 'customer_address', 'shipping_address', 'billing_address',
		                'created_at', 'updated_at', 'status', 'shipment', 'shipments', 'currency']
		if to_int(current_order.channel_id) != self.get_channel_id():
			field_update = ['updated_at', 'status']
		update_field = dict()
		current_status = current_order.link_status
		for field in field_update:
			if current_status == 'linked' and field in ['link_status', 'products']:
				continue
			current_order[field] = convert.get(field)
			update_field[field] = convert.get(field)
		update_field[f'channel.channel_{self.get_channel_id()}.created_at'] = convert.created_at

		if convert.channel[f'channel_{self.get_channel_id()}'].get('order_status'):
			update_field[f'channel.channel_{self.get_channel_id()}.order_status'] = convert.channel[f'channel_{self.get_channel_id()}'].get('order_status')
		self.get_model_order().update(order_id, update_field)
		return Response().success(current_order)

	def sync_order_status(self, order_id, convert: Order, current_order: Order = None):
		if not current_order:
			current_order = self.get_model_order().get(order_id)
			current_order = Prodict(**current_order)
		update_field = {
			'status': convert.status,
		}
		if convert.shipments != current_order.shipments:
			update_field['shipments'] = convert.shipments
			current_order.shipments = convert.shipments
		if convert.get('channel_data', dict()).get('order_status'):
			update_field[f'channel.channel_{self.get_channel_id()}.order_status'] = convert.get('channel_data', dict()).get('order_status')
		self.get_model_order().update(order_id, update_field)
		current_order.status = convert.status

		return Response().success(current_order)

	def get_max_order_number(self):
		if not self._max_order_number:
			max_order_number = 0
			where = self.get_model_order().create_where_condition('channel_id', self._state.channel.id)
			where.update(self.get_model_order().create_where_condition('order_number', "", '>'))
			order = self.get_model_order().find_all(where = where, limit = 1, sort = "-order_number", select_fields = ('order_number',))
			if order:
				position = to_str(to_int(self._state.channel.position if self._state.channel.position else 1))
				order_number = to_str(order[0]['order_number'])

				max_order_number = to_int(order_number[to_len(position):])
			self._max_order_number = max_order_number
		self._max_order_number += 1
		return self._max_order_number

	def create_order_number(self):
		max_order_number = self.get_max_order_number()
		position = to_str(to_int(self._state.channel.position if self._state.channel.position else 1))
		number_zero_digit = 11 - to_len(to_str(max_order_number)) - to_len(position)
		order_number = f"{position}{'0' * number_zero_digit}{max_order_number}"
		return order_number

	def finish_order_import(self):
		imported = to_int(self._state.pull.process.orders.new_entity)
		if not self.is_order_process() or not imported:
			return Response().success()
		# if self._state.pull.process.orders.total == -1:
		# 	content = Messages.ORDER_IMPORT_CONTENT
		# else:
		content = Messages.ORDER_IMPORT_CONTENT_WITH_NUMBER.format(imported, 's' if imported else '')
		notification_data = {
			'code': '',
			'content': content,
			'activity_type': 'order_import',
			'description': "",
			'date_requested': self._date_requested,
			'result': Activity.SUCCESS
		}
		recent = self.create_activity_notification(**notification_data)
		return Response().success()

	def after_create_order_sync(self, order_id, channel_id, order_import, order: Order):
		order_channel_data = OrderChannel()
		order_channel_data.channel_id = channel_id
		update_data = dict()
		if order_import.result != Response.SUCCESS:
			order_channel_data.status = OrderChannel.ERROR
			update_data['link_status'] = Order.UNLINK
			update_data['error_message'] = order_import.msg
		else:
			order_return = order_import['data'][1]
			order_channel_data.status = OrderChannel.ACTIVE
			# order_channel_data.order_status = OrderChannel.ACTIVE
			order_channel_data.order_id = to_str(order_import['data'][0])
			order_channel_data.order_number = to_str(order_return.get('order_number'))
			order_channel_data.order_status = order_return.get('order_status')
			order_channel_data.created_at = order_return.get('created_at')
		update_data[f"channel.channel_{channel_id}"] = order_channel_data

		self.get_model_order().update(order_id, update_data)
		return order_import

	def after_create_product_sync(self, product_id, channel_id, product_import, product = None, src_channel_id = None):
		product_channel_data = self.get_product_channel_data(product, product_import.data, channel_id)
		product_channel_data.channel_id = channel_id
		update_data = dict()
		if product_import.result != Response.SUCCESS:
			product_channel_data.status = ProductChannel.ERRORS
			product_channel_data.link_status = ProductChannel.UNLINK
			product_channel_data.error_message = product_import.msg
		else:
			product_channel_data.status = ProductChannel.ACTIVE
			product_channel_data.product_id = to_str(product_import.data)
			product_channel_data.qty = to_str(product.qty)
			product_channel_data.price = to_str(product.price)
			map_data = self.extend_data_insert_map_product()
			if map_data:
				product_channel_data.update(map_data)
			if to_int(channel_id) == to_int(self.get_channel_default_id()):
				if src_channel_id != channel_id:
					update_data[f"channel.channel_{src_channel_id}.link_status"] = ProductChannel.LINKED
				where_variant = self.get_model_catalog().create_where_condition('is_variant', True)
				where_variant.update(self.get_model_catalog().create_where_condition('parent_id', product_id))
				where_variant.update(self.get_model_catalog().create_where_condition(f"channel.channel_{src_channel_id}.status", ProductChannel.ACTIVE))
				self.get_model_catalog().update_many(where_variant, {f"channel.channel_{src_channel_id}.link_status": ProductChannel.LINKED})
			if to_int(src_channel_id) == to_int(self.get_channel_default_id()):
				product_channel_data.link_status = ProductChannel.LINKED
				where_variant = self.get_model_catalog().create_where_condition('is_variant', True)
				where_variant.update(self.get_model_catalog().create_where_condition('parent_id', product_id))
				where_variant.update(self.get_model_catalog().create_where_condition(f"channel.channel_{channel_id}.status", ProductChannel.ACTIVE))
				self.get_model_catalog().update_many(where_variant, {f"channel.channel_{channel_id}.link_status": ProductChannel.LINKED})
		update_data[f"channel.channel_{channel_id}"] = product_channel_data

		self.get_model_catalog().update(product_id, update_data)
		return product_import

	# TODO: MAP
	def get_category_map(self, category_id, channel_id = None):
		if not channel_id:
			channel_id = self._state.channel.id
		field_check = "channel.channel_{}.category_id".format(channel_id)
		catalog = self.get_model_category().find(field_check, to_str(category_id))
		return catalog.get('_id') if catalog else False

	def get_product_map(self, product_id, channel_id = None, return_product = False):
		return self.get_product_warehouse_map(product_id, channel_id, return_product)

	def get_product_channel_default_map(self, product_id, channel_id = None, return_product = False):
		if not channel_id:
			channel_id = self._state.channel.id
		warehouse_map = self.get_product_warehouse_map(product_id, channel_id, return_product = True)
		if not warehouse_map:
			return False, False
		channel_product = warehouse_map.channel.get(f'channel_{channel_id}')
		channel_default_id = self.get_channel_default_id()
		channel_product_default = warehouse_map.channel.get(f'channel_{channel_default_id}')
		if not channel_product or channel_product.get('link_status') != ProductChannel.LINKED or not channel_product_default or not channel_product_default.get('product_id'):
			return False, warehouse_map.get('_id') if not return_product else warehouse_map
		return True, warehouse_map.get('_id') if not return_product else warehouse_map

	def get_order_map(self, order_id, channel_id = None, return_order = False):
		if not channel_id:
			channel_id = self._state.channel.id
		field_check = "channel.channel_{}.order_id".format(channel_id)
		order = self.get_model_order().find(field_check, to_str(order_id))
		if not order:
			return False
		return order.get('_id') if not return_order else order

	# TODO: import/export file

	def construct_inventories_csv_file(self):
		title = "id,sku,parent_id,available,on_hand,reserved"
		return title.split(',')

	def construct_orders_csv_file(self):
		title = 'Order Id,Order Date,Order Status,Channel,Channel Name,Channel Order Id,Currency,Subtotal,Shipping,Tax,Discount,Total,Shipping Method,LineItem Number,LineItem SKU,LineItem Name,LineItem Quantity,LineItem Price,LineItem Subtotal,Bin Picking Number,Billing Name,Billing Address 1,Billing Address 2,Billing Address 3,Billing Company,Billing City,Billing Zip,Billing State Province,Billing Country,Billing Phone,Billing Email,Shipping Name,Shipping Address 1,Shipping Address 2,Shipping Address 3,Shipping Company,Shipping City,Shipping Zip,Shipping State Province,Shipping Country,Shipping Phone,Shipping Email,Notes'
		channel_default = self.get_channel_default()
		if channel_default and channel_default.get('type') != 'bigcommerce':
			title = title.replace(',Bin Picking Number', '')
		return title.split(',')

	def create_file_upload(self, file_type = 'products', bulk_edit = True):
		file_path = os.path.join(get_pub_path(), 'media', to_str(self._user_id))
		if not os.path.exists(file_path):
			os.makedirs(file_path, mode = 0o777)
			change_permissions_recursive(file_path, 0x777)
		file_name = "{}_{}.csv".format(file_type, get_current_time("%Y-%m-%d_%H-%M-%S"))
		construct = f"construct_{file_type}_csv_file"
		csv_title = getattr(self, construct)()
		csv_title.append('active_listings')
		if file_type == 'products' and bulk_edit:
			csv_title = self.construct_products_csv_bulk_edit()
		product_file = open(os.path.join(file_path, file_name), mode = 'a')
		file_writer = csv.writer(product_file, delimiter = ',', quotechar = '"', quoting = csv.QUOTE_MINIMAL)
		file_writer.writerow(csv_title)
		return file_writer, file_name, product_file

	def product_to_csv_data(self, product):
		csv_data = dict()
		title = self.construct_products_csv_file()
		for row in title:
			if isinstance(product.get(row), bool):
				value = 1 if product.get(row) else ''
			else:
				value = product.get(row, "") if row != 'product_id' else product.get('_id')
			if isinstance(value, float):
				float_value = decimal.Decimal(value)
				value = to_str(float_value.normalize())
			csv_data[row] = value
		csv_data['manufacturer'] = product.manufacturer.name
		csv_data['product_image_1'] = product.thumb_image.url
		for index, image in enumerate(product.images):
			product_image_index = index + 2
			if product_image_index > 10:
				break
			csv_data['product_image_{}'.format(to_str(product_image_index))] = image.url
		active_listings = list()
		if product.channel:
			for channel, channel_data in product.channel.items():
				if channel_data.status != 'active':
					continue
				channel_id = to_int(to_str(channel).replace('channel_', ''))
				if self.get_all_channels().get(channel_id):
					active_listings.append(self.get_all_channels()[channel_id]['name'])
		csv_data['active_listings'] = ','.join(active_listings)

		return csv_data

	def export(self, file_writer, product: Product, bulk_edit = False):
		variants_csv_data = list()
		if bulk_edit:
			csv_title = self.construct_products_csv_bulk_edit()
		else:
			csv_title = self.construct_products_csv_file()
			csv_title.append('active_listings')
		csv_data = list()
		product_data = self.product_to_csv_data(product)
		if product.variants:
			default_variant = dict()
			max_attribute = 0
			for variant in product.variants:
				"""
				variant: ProductVariant
				"""
				if len(variant.attributes) > max_attribute:
					max_attribute = len(variant.attributes)
					default_variant = variant
			if default_variant:
				for index, attribute in enumerate(default_variant.attributes):
					if index > 4:
						break
					product_data[f'variation_{index + 1}'] = attribute['attribute_name']
			for variant in product.variants:
				variant_data = self.product_to_csv_data(variant)
				variant_data['parent_sku'] = product.sku
				variant_data['parent_id'] = product['_id']
				attribute_data = dict()
				for attribute in variant.attributes:
					attribute_data[attribute['attribute_name']] = attribute['attribute_value_name']
				for index in range(1, 6):
					variant_key = f'variation_{index}'
					if not product_data[variant_key]:
						continue
					variant_data[variant_key] = attribute_data.get(product_data[variant_key], "")
				variants_csv_data.append(variant_data)
		file_path = os.path.join(get_pub_path(), 'media', to_str(self._user_id))
		csv_data.append(product_data)
		csv_data = list(csv_data + variants_csv_data)
		for data in csv_data:
			column = list()
			for field in csv_title:
				value = data.get(field, '')
				column.append(value)
			file_writer.writerow(column)
		return Response().success()

	def finish_export(self, file_name, open_file):
		open_file.close()
		file_path = os.path.join(get_pub_path(), 'media', to_str(self._user_id), file_name)
		prefix = self.get_prefix_storage()
		file_upload = self.get_storage_service().upload_file_from_local(file_path, os.path.join(prefix, 'products', file_name))
		# send email
		notification_data = {
			'code': 'inventory_export_csv',
			'activity_type': 'export_csv',
			'description': 'Export Csv Inventory',
			'date_requested': self._date_requested,
			'result': Activity.SUCCESS if file_upload else Activity.FAILURE
		}
		if file_upload:
			notification_data['content'] = Messages.PRODUCT_EXPORT_CSV_SUCCESS.format(url_to_link(file_upload, 'download'))
			notification_data['result'] = Activity.SUCCESS
		else:
			notification_data['result'] = Activity.FAILURE
			notification_data['content'] = Messages.PRODUCT_EXPORT_CSV_FAILURE
		self.create_activity_notification(**notification_data)
		self.log(file_upload, 'export')
		os.remove(file_path)
		return Response().success(file_upload)

	# TODO: image
	def get_storage_image_service(self):
		if self._storage_image_service:
			return self._storage_image_service
		self._storage_image_service = ImageStorageGoogle()
		return self._storage_image_service

	def get_storage_service(self):
		if self._storage_service:
			return self._storage_service
		self._storage_service = FileStorageGoogle()
		return self._storage_service

	def get_prefix_storage(self):
		prefix = to_str(self._user_id) if self._user_id else 'undefined'
		mode = get_config_ini('local', 'mode')
		if mode == 'live':
			prefix = 'production/' + prefix
		else:
			prefix = 'test/' + prefix
		return prefix

	def create_destination_product_image(self, product_id, image_url):
		image_url_parse = urllib.parse.urlparse(image_url)
		image_name = image_url_parse.path
		if not product_id:
			product_id = to_str(to_int(time.time()))
		random_id = to_str(uuid.uuid4())
		mimetype_image = to_str(image_name).split('.')[-1]
		prefix = self.get_prefix_storage()
		return prefix + "/" + to_str(product_id) + "/" + random_id + "." + mimetype_image

	def upload_image(self, url, destination_image):
		return self.get_storage_image_service().upload_file_from_url(url, destination_image)

	# todo: inventories
	def get_inventories_main_export(self, location_id):
		id_src = self._state.push.process.products.id_src
		if not id_src:
			id_src = ""
		limit = self._state.push.setting.products
		where = dict()
		where.update(self.get_model_catalog().create_where_condition('id', id_src, '>'))
		where.update(self.get_model_catalog().create_where_condition(f"inventories.inventory.{location_id}.location_id", to_int(location_id)))
		try:
			products = self.get_model_catalog().find_all(where = where, limit = limit, order_by = 'id', select_fields = ("inventories.inventory", "parent_id", "sku", "id"))
			if not products:
				return Response().finish()
		except Exception as e:
			self.log_traceback()
			return Response().error()
		return Response().success(tuple(map(lambda x: Prodict.from_dict(x), products)))

	def get_inventories_ext_export(self, products):
		return Response().success()

	def convert_inventory_export(self, convert, products_ext):
		return convert

	def export_inventory(self, file_writer, convert, location_id):
		csv_title = self.construct_inventories_csv_file()
		product_data = self.inventory_to_csv_data(convert, location_id)
		column = list()
		for field in csv_title:
			value = product_data[field]
			column.append(value)
		file_writer.writerow(column)

	def finish_inventory_export(self, file_name, open_file):
		open_file.close()
		file_path = os.path.join(get_pub_path(), 'media', to_str(self._user_id), file_name)
		prefix = self.get_prefix_storage()

		file_upload = self.get_storage_service().upload_file_from_local(file_path, os.path.join(prefix, 'inventories', file_name))
		notification_data = {
			'code': 'inventory_export_csv',
			'activity_type': 'export_csv',
			'description': 'Export Csv Inventory',
			'date_requested': self._date_requested,
			'result': Activity.SUCCESS if file_upload else Activity.FAILURE
		}
		if file_upload:
			notification_data['content'] = Messages.INVENTORY_EXPORT_CSV_SUCCESS.format(url_to_link(file_upload, 'download'))
			notification_data['result'] = Activity.SUCCESS
		else:
			notification_data['result'] = Activity.FAILURE
			notification_data['content'] = Messages.INVENTORY_EXPORT_CSV_FAILURE
		self.create_activity_notification(**notification_data)
		# send email
		self.log(file_upload, 'export')
		return Response().success(file_upload)

	def inventory_to_csv_data(self, product, location_id):
		csv_data = Prodict()
		csv_data.id = product.get('_id')
		csv_data.sku = product.sku
		csv_data.parent_id = to_str(product.parent_id) if to_bool(product.parent_id) else ""
		inventory = product.inventories.inventory.get(to_str(location_id))
		csv_data.on_hand = to_int(inventory.on_hand)
		csv_data.reserved = to_int(inventory.reserved)
		csv_data.available = to_int(inventory.available)
		return csv_data

	def display_finish_pull_warehouse(self):
		return Response().success()

	def display_finish_push_warehouse(self):
		return Response().success()

	# TODO: Order
	def get_orders_main_export(self, start_date = None, end_date = None):
		id_src = self._state.push.process.orders.id_src
		limit = self._state.push.setting.orders
		where = dict()
		where_date = self.get_model_order().create_where_condition('created_at', start_date, '>=')
		where_date['created_at'].update(self.get_model_order().create_where_condition('created_at', end_date, '<=')['created_at'])
		where.update(where_date)
		if id_src:
			where.update(self.get_model_order().create_where_condition('_id', id_src, '>'))

		if self._state.push.process.orders.execute_ids is not False:
			where.update(self.get_model_order().create_where_condition('_id', self._state.push.process.orders.execute_ids, 'in'))
		if self._state.push.process.orders.condition:
			for condition in self._state.push.process.orders.condition:
				where.update(self.get_model_order().create_where_condition(condition.field, condition.value, condition.condition))
		try:
			orders = self.get_model_order().find_all(where = where, limit = limit, order_by = '_id')
			if not orders:
				return self._response.finish()
		except Exception as e:
			self.log_traceback()
			return self._response.error()
		return self._response.success(tuple(map(lambda x: Prodict.from_dict(x), orders)))

	def get_order_by_ids(self, order_ids):
		where = self.get_model_order().create_where_condition('_id', order_ids, 'in')
		try:
			orders = self.get_model_order().find_all(where = where, order_by = 'id')
			if not orders:
				return self._response.finish()
		except Exception as e:
			self.log_traceback()
			return self._response.error()
		return self._response.success(tuple(map(lambda x: Prodict.from_dict(x), orders)))

	def get_order_by_id(self, order_id):
		return self.get_model_order().get(order_id)

	def get_orders_ext_export(self, orders):
		product_ids = []
		for order in orders:
			product_ids.extend([row['id'] for row in order.products])
		product_ids = list(set(product_ids))
		products = self.get_model_catalog().find_all(self.get_model_catalog().create_where_condition('_id', product_ids, 'in'), select_fields = ('channel', 'parent_id'))
		parent_ids = []
		for product in products:
			if product['parent_id'] and product['parent_id'] not in product_ids:
				parent_ids.append(product['parent_id'])
		parent_ids = list(set(parent_ids))
		if parent_ids:
			parent_products = self.get_model_catalog().find_all(self.get_model_catalog().create_where_condition('_id', parent_ids, 'in'), select_fields = ('channel', 'parent_id'))
			products.extend(parent_products)
		orders_ext = {
			'products': products
		}
		return Response().success(orders_ext)

	def convert_order_export(self, order, orders_ext, channel_id = None):
		if not channel_id:
			channel_id = self._state.channel.id
		products = {product['_id']: product for product in orders_ext['products']}
		if not order.shipments:
			order.shipments = Shipment()
		if isinstance(order.shipments, list) and order.shipments:
			order.shipments = order.shipments[0]

		if order.products:
			for item in order.products:
				product_id = item['id']
				product_channel_id = None
				variant_channel_id = None
				product = None
				parent_product = None
				if products.get(product_id):
					product = products[product_id]
					if product['channel'].get(f'channel_{channel_id}') and product['channel'][f'channel_{channel_id}'].get('product_id'):
						product_channel_id = product['channel'][f'channel_{channel_id}']['product_id']
					else:
						return Response().error()
					if product['parent_id'] and product['parent_id'] in products:
						parent_product = products[product['parent_id']]
						if parent_product['channel'].get(f'channel_{channel_id}') and parent_product['channel'][f'channel_{channel_id}'].get('product_id'):
							variant_channel_id = product_channel_id
							product_channel_id = parent_product['channel'][f'channel_{channel_id}']['product_id']
				item['product'] = product
				if variant_channel_id:
					item['product_id'] = variant_channel_id
					item['parent_id'] = product_channel_id
					item['parent'] = parent_product

				else:
					item['product_id'] = product_channel_id
					item['parent_id'] = None
					item['parent'] = None

		return Response().success(order)

	def get_order_updated_time(self, order):
		return order.updated_time

	def export_order(self, file_writer, order: Order):
		# variants_csv_data = list()
		csv_title = self.construct_orders_csv_file()
		csv_data = self.order_to_csv_data(order)
		file_path = os.path.join(get_pub_path(), 'media', to_str(self._user_id))
		# csv_data.append(order_data)
		# csv_data = list(csv_data + variants_csv_data)
		for data in csv_data:
			column = list()
			for field in csv_title:
				value = data[field]
				column.append(value)
			file_writer.writerow(column)
		return self._response.success()

	def order_to_csv_data(self, order: Order):
		title = self.construct_orders_csv_file()
		csv_data = {row: '' for row in title}
		result = list()
		csv_data['Order Id'] = order['order_number']
		csv_data['Order Date'] = order.get('created_at')
		csv_data['Order Status'] = order.get('status')
		csv_data['Channel'] = order.get('channel').get('type')
		csv_data['Channel Name'] = order.get('channel').get('name')
		csv_data['Channel Order Id'] = order.get('channel_id')
		# csv_data['Paid Date'] = order.get('paid_date')
		# csv_data['Shipped Date'] = order.get('shipping').get('')
		# csv_data['Canceled Date'] = ''
		csv_data['Currency'] = order.get('currency')
		csv_data['Subtotal'] = order.subtotal or 0
		csv_data['Shipping'] = order.shipping.amount or 0
		csv_data['Tax'] = order.tax.amount or 0
		csv_data['Discount'] = order.discount.amount or 0
		csv_data['Total'] = order.total or 0
		csv_data['Shipping Method'] = order.shipping.method or order.shipping.title
		csv_data['LineItem Number'] = len(order.products)
		billing_name = [order.billing_address.first_name, order.billing_address.last_name]
		csv_data['Billing Name'] = " ".join(billing_name)
		csv_data['Billing Address 1'] = order.billing_address.address_1
		csv_data['Billing Address 2'] = order.billing_address.address_2
		csv_data['Billing Company'] = order.billing_address.company
		csv_data['Billing City'] = order.billing_address.city
		csv_data['Billing Zip'] = order.billing_address.postcode
		# csv_data['Billing State Province'] =
		csv_data['Billing Country'] = order.billing_address.country.country_code
		csv_data['Billing Phone'] = order.billing_address.telephone

		shipping_name = [order.shipping_address.first_name, order.shipping_address.last_name]
		csv_data['Shipping Name'] = " ".join(shipping_name)
		csv_data['Shipping Address 1'] = order.shipping_address.address_1
		csv_data['Shipping Address 2'] = order.shipping_address.address_2
		csv_data['Shipping Company'] = order.shipping_address.company
		csv_data['Shipping City'] = order.shipping_address.city
		csv_data['Shipping Zip'] = order.shipping_address.postcode
		# csv_data['Shipping State Province'] =
		csv_data['Shipping Country'] = order.shipping_address.country.country_code
		csv_data['Shipping Phone'] = order.shipping_address.telephone
		for item in order.products:
			item_data = copy.deepcopy(csv_data)
			item_data['LineItem Number'] = len(order.products)
			item_data['LineItem SKU'] = item.product_sku
			item_data['LineItem Name'] = item.product_name
			item_data['LineItem Quantity'] = item.qty
			# csv_data['LineItem Fulfilled'] =
			item_data['LineItem Price'] = item.price
			item_data['LineItem Subtotal'] = item.subtotal or item.total or 0
			item_data['Bin Picking Number'] = item.product_bpn
			result.append(item_data)
		return result

	def finish_order_csv_export(self, file_name, open_file):
		open_file.close()
		file_path = os.path.join(get_pub_path(), 'media', to_str(self._user_id), file_name)
		prefix = self.get_prefix_storage()

		file_upload = self.get_storage_service().upload_file_from_local(file_path, os.path.join(prefix, 'orders', file_name))
		notification_data = {
			'code': 'order_export_csv',
			'activity_type': 'export_csv',
			'description': 'Export Csv Order',
			'date_requested': self._date_requested,
			'result': Activity.SUCCESS if file_upload else Activity.FAILURE
		}
		if file_upload:
			notification_data['content'] = Messages.ORDER_EXPORT_CSV_SUCCESS.format(url_to_link(file_upload, 'download'))
			notification_data['result'] = Activity.SUCCESS
		else:
			notification_data['result'] = Activity.FAILURE
			notification_data['content'] = Messages.ORDER_EXPORT_CSV_FAILURE
		self.create_activity_notification(**notification_data)
		# send email
		self.log(file_upload, 'export')
		return self._response.success(file_upload)

	def product_update_template_data(self, product: Product):
		template_data = product.channel.get(f"channel_{self.get_channel_id()}").get('template_data')
		self.get_model_catalog().update_field(product['_id'], f"channel.channel_{self.get_channel_id()}.template_data", template_data)
		if product.variants:
			for variant in product.variants:
				self.product_update_template_data(variant)

	def is_insert_updated_time(self):
		return True
		if self._is_insert_updated_time is not None:
			return self._is_insert_updated_time
		self._is_insert_updated_time = True
		frequent = [8, 20]
		hour_now = to_int(get_current_time("%H"))
		current_milestone = frequent[-1]
		for field in frequent:
			if hour_now >= field:
				current_milestone = field
		current_time_mile_stone = to_timestamp(get_current_time(f"%Y-%m-%d {current_milestone}:%M:%S"))
		if self._state.push.process.products.previous_start_time and self._state.push.process.products.previous_start_time < current_time_mile_stone:
			self._is_insert_updated_time = False
		return self._is_insert_updated_time
