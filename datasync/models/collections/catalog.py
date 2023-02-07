from datasync.libs.prodict import Prodict
from datasync.libs.utils import to_str
from datasync.models.collection import ModelCollection
from datasync.models.constructs.product import Product, ProductInventories


class Catalog(ModelCollection):
	COLLECTION_NAME = 'catalog'
	FILTER = ('price', 'qty')
	_data: Product


	def __init__(self, **kwargs):
		super().__init__(**kwargs)


	def get_collection_name(self):
		return self.COLLECTION_NAME


	def update_many_catalog(self, catalog_ids, where, update_data):
		where = self.create_where_condition('_id', catalog_ids, 'in')
		return self.update_many(where, update_data)


	def update_parent_product_inventories(self, parent_id, commit = True):
		try:
			product_data = self.get(parent_id)
		except Exception:
			return False
		if product_data['variant_count'] == 0:
			return True
		children_data = self.find_all(self.create_where_condition('parent_id', parent_id, '=='))
		product_inventories = ProductInventories()
		for child_data in children_data:
			for location_id, inventory_data in child_data['inventories']['inventory'].items():
				location_id = to_str(location_id)
				if location_id not in product_inventories['inventory']:
					product_inventories['inventory'][location_id] = inventory_data
				else:
					product_inventory = product_inventories['inventory'][location_id]
					for field in ('available', 'on_hand', 'reserved'):
						product_inventory[field] += inventory_data[field]
		for field in ('available', 'on_hand', 'reserved'):
			product_inventories[f'total_{field}'] = sum(inventory[field] for inventory in product_inventories['inventory'].values())
		update_data = {
			'variant_count': len(children_data),
			'qty': product_inventories['total_available'],
			'inventories': product_inventories,
		}
		return self.update_fields(parent_id, update_data)