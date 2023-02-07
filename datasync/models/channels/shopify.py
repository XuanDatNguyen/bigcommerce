import io
from urllib.request import Request, urlopen

import requests
from PIL import Image
from PIL import ImageFile

from datasync.libs.errors import Errors
from datasync.libs.response import Response
from datasync.libs.utils import *
from datasync.models.channel import ModelChannel
from datasync.models.constructs.category import CatalogCategory
from datasync.models.constructs.order import Order, OrderProducts, OrderItemOption, OrderHistory
from datasync.models.constructs.product import Product, ProductImage, ProductAttribute, ProductVariant, \
    ProductVariantAttribute


class ModelChannelsShopify(ModelChannel):
    FORMAT_DATETIME = '%Y-%m-%d %H:%M:%S'
    CUSTOM_COLLECTION = 'custom'
    SMART_COLLECTION = 'smart'
    ORDER_STATUS = {
        "pending": Order.OPEN,
        "partially_refunded": Order.OPEN,
        "authorized": Order.AWAITING_PAYMENT,
        "partially_paid": Order.SHIPPING,
        "paid": Order.COMPLETED,
        "voided": Order.CANCELED,
        "refunded": Order.CANCELED,
    }
    FINANCIAL_ORDER_STATUS = {
        Order.OPEN: "pending",
        Order.AWAITING_PAYMENT: "authorized",
        Order.READY_TO_SHIP: "paid",
        Order.SHIPPING: "paid",
        Order.COMPLETED: "paid",
        Order.CANCELED: "refunded",
    }
    FULFILLMENT_STATUS = {
        # Order.SHIPPING: "fulfilled",
        Order.COMPLETED: "fulfilled",
        Order.CANCELED: "restocked",
    }

    def __init__(self):
        super().__init__()
        self._api_url = None
        self._version_api = None
        self._last_status = None
        self._collection_type = None
        self._shopify_countries = None
        self._location_id = None
        self._last_product_response = None
        self._last_images = None
        self._flag_finish_product = False
        self._flag_finish_order = False
        self._product_next_link = False
        self._order_next_link = False
        self._order_max_last_modified = False

    def get_api_info(self):
        return {
            'password': "API Password",
            # 'app_secret': 'Shared Secret'
        }

    def set_last_product_response(self, response, images):
        self._last_product_response = response
        self._last_images = images

    def get_last_product_response(self):
        return self._last_product_response, self._last_images

    # api code

    def get_api_path(self, path, add_version=True):
        path = to_str(path).replace('admin/', '')
        prefix = 'admin'
        if add_version:
            prefix += '/api/' + self.get_version_api()
        path = prefix + '/' + path
        return path

    def get_version_api(self):
        if self._version_api:
            return self._version_api
        year = get_current_time("%Y")
        month = get_current_time("%m")
        quarter = (to_int(month) - 1) // 3
        version_api = (to_int(quarter) - 1) * 3 + 1
        if version_api < 10:
            version_api = "0" + to_str(version_api)
        else:
            version_api = to_str(version_api)

        self._version_api = to_str(year) + "-" + version_api
        self._version_api = "2023-01"
        return self._version_api

    def api(self, path, data=None, api_type="get", add_version=True):
        path = self.get_api_path(path, add_version)
        header = {"Content-Type": "application/json"}
        url = self.get_api_url() + '/' + to_str(path).strip('/')
        res = self.requests(url, data, method=api_type)
        retry = 0
        while (res is False) or ('expected Array to be a Hash' in to_str(res)) or (
            "Exceeded 2 calls per second for api client. Reduce request rates to resume uninterrupted service" in to_str(
                res)) or self._last_status >= 500:
            retry += 1
            time.sleep(10)
            res = self.requests(url, data, method=api_type)
            if retry > 5:
                break
        return res

    def get_api_url(self):
        if not self._api_url:
            self._api_url = self.create_api_url()
        return self._api_url

    def create_api_url(self):
        api_url = "https://{}.myshopify.com".format(
            self._state.channel.config.api.shop)
        return api_url

    def requests(self, url, data=None, headers=None, method='get'):
        method = to_str(method).lower()
        if not headers:
            headers = dict()
            headers['User-Agent'] = get_random_useragent()
        elif isinstance(headers, dict) and not headers.get('User-Agent'):
            headers['User-Agent'] = get_random_useragent()
        headers['X-Shopify-Access-Token'] = self._state.channel.config.api.password
        headers['Content-Type'] = 'application/json'

        response = False
        request_options = {
            'headers': headers,
            'verify': True
        }
        if method == 'get' and data:
            request_options['params'] = data
        if method in ['post', 'put'] and data:
            request_options['json'] = data
        request_options = self.combine_request_options(request_options)
        response_data = False
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
                response_data = response_prodict
            if response.headers.get('x-shopify-shop-api-call-limit'):
                res_called_data = response.headers.get(
                    'x-shopify-shop-api-call-limit')
                res_called_arr = res_called_data.split('/')
                request_remain = to_int(
                    res_called_arr[1]) - to_int(res_called_arr[0])
                if request_remain < 5:
                    time.sleep(1)
            else:
                time.sleep(1)

            def log_request_error():
                error = {
                    'method': method,
                    'status': response.status_code,
                    'data': to_str(data),
                    'header': to_str(response.headers),
                    'response': response.text,
                }
                self.log_request_error(url, **error)

            if response.status_code == 403:
                if response_data.errors and 'This action requires merchant approval for ' in to_str(
                        response_data.errors):
                    log_request_error()
                    # self.log('Daily variant creation limit reached, delay 1day', 'delay')
                    scope = re.findall(r"This action requires merchant approval for ([a-z_]+) scope",
                                       to_str(response_data.errors))
                    msg_scope = ''
                    if scope:
                        msg_scope = scope[0]
                    self.notify(Errors.SHOPIFY_SCOPE)
                    return response_data

            if response.status_code == 429:
                if response_data.errors and 'Daily variant creation limit reached. Please try again later' in to_str(
                        response_data.errors):
                    log_request_error()
                    self.notify(Errors.SHOPIFY_VARIANT_LIMIT)
                    time.sleep(24 * 60 * 60)
                    return self.requests(url, data, headers, method)
            if response.status_code > 201:
                log_request_error()
        except Exception as e:
            self.log_traceback()
        return response_data

    def display_setup_channel(self, data=None):
        parent = super().display_setup_channel(data)
        if parent.result != Response().SUCCESS:
            return parent
        url = self._channel_url
        shopify_code = re.findall("https://(.*).myshopify.com", url)
        self._state.channel.config.api.shop = shopify_code[0]
        shop = self.api('shop.json')
        if not shop:
            return Response().error(Errors.SHOPIFY_API_INVALID)
        try:
            if shop.errors:
                return Response().error(Errors.SHOPIFY_API_INVALID)

        except Exception as e:
            return Response().error(Errors.SHOPIFY_API_INVALID)
        access_scopes = self.get_access_scopes()
        fail_scope = list()
        if access_scopes:
            list_scope = 'read_products,write_products,write_inventory,read_locations'
            for scope in list_scope.split(','):
                if scope not in access_scopes:
                    fail_scope.append(scope)

        if fail_scope:
            self.log(','.join(fail_scope), 'scope')
            return Response().error(Errors.SHOPIFY_SCOPE_INVALID)

        self._state.channel.clear_process.function = "clear_channel_taxes"
        return Response().success()

    def get_access_scopes(self):
        scope = self.requests(
            f'{self.get_channel_url()}/admin/oauth/access_scopes.json')
        if not scope or not scope.get('access_scopes'):
            return list()
        list_access_scopes = list()
        for access_scopes in scope['access_scopes']:
            list_access_scopes.append(access_scopes['handle'])
        return list_access_scopes

    def set_channel_identifier(self):
        parent = super().set_channel_identifier()
        if parent.result != Response().SUCCESS:
            return parent
        self.set_identifier(self._state.channel.config.api.shop)
        return Response().success()

    def after_create_channel(self, data):
        if is_local():
            return Response().success()
        entities = ['order']
        webhook_token_data = {
            'channel_id': data.channel_id,
            'channel_type': 'shopify'
        }
        token = 'ay8PRsxHHHzQL9TG'
        events = dict()
        if self.is_channel_default():
            # events[f"products/update"] = f'product/update'
            events[f"orders/updated"] = f'order/update'
        events["products/delete"] = 'product/delete'
        for event, url in events.items():
            address = get_api_server_url(
                f'merchant/shopify/webhook/{data.channel_id}/{url}')
            if not self._state.channel.config.api.app_id:
                address += f"?password={token}"
            webhook_data = {
                "webhook": {
                    "topic": event,
                    "address": address,
                    "format": "json"
                }
            }
            webhook = self.api('webhooks.json', webhook_data, 'post')
        return Response().success()

    def get_max_last_modified_product(self):
        if self._state.pull.process.products.last_modified:
            if to_str(self._state.pull.process.products.last_modified).isnumeric():
                return convert_format_time(self._state.pull.process.products.last_modified, new_format="%Y-%m-%dT%H:%M:%S+07:00")
            return self._state.pull.process.products.last_modified
        return False

    def create_webhook_product(self):
        pass

    def display_pull_channel(self):
        parent = super().display_pull_channel()
        if parent.result != Response().SUCCESS:
            return parent
        if self.is_product_process():
            params = {}
            if self.is_refresh_process():
                self._state.pull.process.products.id_src = 0
                params['since_id'] = 0
                last_modified = self.get_max_last_modified_product()
                if last_modified:
                    params['updated_at_min'] = last_modified
            else:
                if not self.is_import_inactive():
                    params['status'] = 'active'
            products_api = self.api('products/count.json', data=params)
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
                "created_at_min": start_time,
                "status": 'any'
            }
            if last_modifier:
                params['updated_at_min'] = last_modifier
                self.set_order_max_last_modifier(last_modifier)
            orders_api = self.api('orders/count.json', data=params)
            if orders_api and orders_api.count:
                self._state.pull.process.orders.total = orders_api.count
        if self.is_category_process():
            self._state.pull.process.categories.total = 0
            self._state.pull.process.categories.imported = 0
            # self._state.pull.process.categories.new_entity = 0
            self._state.pull.process.categories.error = 0
            self._state.pull.process.categories.id_src = 0
            self._state.pull.process.categories.id_src_smart = 0
            custom_collections_api = self.api('custom_collections/count.json')
            smart_collection_api = self.api('smart_collections/count.json')
            if custom_collections_api and custom_collections_api.count:
                self._state.pull.process.categories.total += custom_collections_api.count
            if smart_collection_api and smart_collection_api.count:
                self._state.pull.process.categories.total += smart_collection_api.count
        return Response().success()

    def set_order_max_last_modifier(self, last_modifier):
        if last_modifier and (not self._order_max_last_modified or to_timestamp(last_modifier, "%Y-%m-%dT%H:%M:%S") > to_timestamp(self._order_max_last_modified, '%Y-%m-%dT%H:%M:%S')):
            self._order_max_last_modified = last_modifier

    def clear_channel_taxes(self):
        next_clear = Prodict.from_dict({
            'result': 'process',
            'function': 'clear_channel_categories',
        })
        self._state.channel.clear_process = next_clear
        return next_clear

    def clear_channel_categories(self):
        next_clear = Prodict.from_dict({
            'result': 'process',
            'function': 'clear_channel_products',
        })
        self._state.channel.clear_process = next_clear
        if not self._state.config.categories:
            return next_clear
        try:
            all_collections = self.api('custom_collections.json?limit=100')
            while all_collections:
                if not all_collections.custom_collections:
                    break
                for collect in all_collections.custom_collections:
                    id_collect = collect.id
                    res = self.api(
                        'custom_collections/{}.json'.format(id_collect), None, 'Delete')
                # a = res
                all_collections = self.api('custom_collections.json?limit=100')
                time.sleep(0.1)
            all_collections = self.api('smart_collections.json?limit=100')

            while all_collections:
                if not all_collections:
                    return next_clear
                if not all_collections.smart_collections:
                    return next_clear
                for collect in all_collections.smart_collections:
                    id_collect = collect.id
                    res = self.api(
                        'smart_collections/{}.json'.format(id_collect), None, 'Delete')
                # a = res
                all_collections = self.api('smart_collections.json?limit=100')
                time.sleep(0.1)
        except Exception:
            self.log_traceback()
            return next_clear
        return next_clear

    def clear_channel_products(self):
        next_clear = Prodict.from_dict({
            'result': 'success',
            'function': '',
        })
        self._state.channel.clear_process = next_clear
        if not self._state.config.products:
            return next_clear
        try:
            all_products = self.api('products.json?limit=100')
            while all_products:
                if not all_products:
                    return next_clear
                if not all_products.products:
                    return next_clear
                for product in all_products.products:
                    id_product = product.id
                    res = self.api(
                        'products/{}.json'.format(id_product), None, 'Delete')
                all_products = self.api('products.json?limit=100')
                time.sleep(0.1)
        except Exception:
            self.log_traceback()
            return next_clear
        return next_clear

    def get_collection_type(self):
        if self._collection_type:
            return self._collection_type
        self._collection_type = self.CUSTOM_COLLECTION
        return self._collection_type

    def set_collection_type(self, collection_type):
        self._collection_type = collection_type

    def get_categories_main_export(self):
        collection_type = self.get_collection_type()
        limit_data = 100
        categories_data = list()
        if collection_type == self.CUSTOM_COLLECTION:
            id_src = self._state.pull.process.categories.id_src
            collections = self.api('custom_collections.json', data={
                                   'since_id': id_src, 'limit': limit_data})
            if not collections:
                return Response().finish()
            categories_data = collections.get('custom_collections')
            if not categories_data:
                collection_type = self.SMART_COLLECTION
                self.set_collection_type(self.SMART_COLLECTION)
        if collection_type == self.SMART_COLLECTION:
            id_src = self._state.pull.process.categories.id_src_smart
            if not id_src:
                id_src = 0
            collections = self.api('smart_collections.json', data={
                                   'since_id': id_src, 'limit': limit_data})
            if not collections:
                return Response().finish()

            if not collections.get('smart_collections'):
                return Response().finish()
            categories_data = collections['smart_collections']
        return Response().success(categories_data)

    def get_categories_ext_export(self, categories):
        return Response().success()

    def convert_category_export(self, category, categories_ext):
        category_data = CatalogCategory()
        category_data.id = category.id
        category_data.name = category.title
        category_data.collection_type = self.get_collection_type()
        return Response().success(category_data)

    def get_category_id_import(self, convert: CatalogCategory, category, categories_ext):
        return category['id']

    def set_category_id_src(self, id_src):
        if self.get_collection_type() == self.SMART_COLLECTION:
            self._state.pull.process.products.id_src_smart = id_src
        else:
            self._state.pull.process.products.id_src = id_src

    def category_import(self, convert: CatalogCategory, category, categories_ext):
        if not category.name:
            return response_error('import category ' + to_str(category.id) + ' false.')
        post_data = {
            'smart_collection': {
                'title': category.name,
                'body_html': category.description,
                'published_scope': 'web',
                'disjunctive': 'false',
                'sort_order': 'best-selling',
                'rules': []
            }
        }

        # Add Thumbnail image
        if category.thumb_image.url:
            main_image = self.process_image_before_import(
                category.thumb_image.url, category.thumb_image.path)
            image_data = self.resize_image(main_image['url'])
            if image_data:
                post_data['smart_collection']['image'] = image_data

        # Status
        if not category.active:
            post_data['smart_collection']['published_at'] = None

        # Add rules: the list of rules that define what products go into the smart collections.
        tag_rule = {
            'column': 'tag',
            'relation': 'equals',
            'condition': category.name
        }
        post_data['smart_collection']['rules'].append(tag_rule)

        # Post data
        response = self.api('smart_collections.json', post_data, 'Post')
        check_response = self.check_response_import(
            response, category, 'category')
        if check_response.result != Response.SUCCESS:
            if 'Image' in check_response.msg:
                del post_data['smart_collection']['image']
                response = self.api(
                    'smart_collections.json', post_data, 'Post')
                check_response = self.check_response_import(
                    response, category, 'category')
                if check_response.result != Response.SUCCESS:
                    return check_response
            else:
                return check_response

        category_id = response['smart_collection']['id']
        handle = response['smart_collection'].get('handle')
        return Response().success(category_id)

    def get_product_by_id(self, product_id):
        product = self.api(f'products/{product_id}.json')
        if self._last_status == 404:
            return Response().create_response(result=Response.DELETED)
        if not product or not product.get('product'):
            return Response().error()
        return Response().success(product['product'])

    def get_product_by_updated_at(self):
        if self._flag_finish_product:
            return Response().finish()
        if self._product_next_link:
            products = self.requests(self._product_next_link)
        else:
            limit_data = self._state.pull.setting.products
            params = {'limit': 100}
            last_modified = self.get_max_last_modified_product()
            if last_modified:
                params['updated_at_min'] = last_modified

            products = self.api('products.json', data=params)
        links = self._last_header.get('link')
        next_link = ''
        if links and 'next' in links:
            list_link = links.split(',')
            for link_row in list_link:
                if 'next' in link_row:
                    next_link = link_row.split(';')[0]
                    next_link = next_link.strip('<> ')
        if not next_link:
            self._flag_finish_product = True
        else:
            self._product_next_link = next_link
        if not products or not products.products:
            if self._last_status != 200:
                return Response().error(Errors.SHOPIFY_GET_PRODUCT_FAIL)
            return Response().finish()
        return Response().success(data=products.products)

    def get_products_main_export(self):
        if self._flag_finish_product:
            return Response().finish()
        if self._product_next_link:
            products = self.requests(self._product_next_link)
        else:
            limit_data = self._state.pull.setting.products
            params = {'limit': 100}

            products = self.api('products.json', data=params)
        links = self._last_header.get('link')
        next_link = ''
        if links and 'next' in links:
            list_link = links.split(',')
            for link_row in list_link:
                if 'next' in link_row:
                    next_link = link_row.split(';')[0]
                    next_link = next_link.strip('<> ')
        if not next_link:
            self._flag_finish_product = True
        else:
            self._product_next_link = next_link
        if not products or not products.products:
            if self._last_status != 200:
                return Response().error(Errors.SHOPIFY_GET_PRODUCT_FAIL)
            return Response().finish()
        return Response().success(data=products.products)

    def _get_products_main_export(self):
        limit_data = self._state.pull.setting.products
        id_src = self._state.pull.process.products.id_src
        params = {'since_id': id_src, 'limit': 100}
        if not self.is_import_inactive():
            params['status'] = 'active'
        products = self.api('products.json', data=params)
        if not products or not products.products:
            if self._last_status != 200:
                return Response().error(Errors.SHOPIFY_GET_PRODUCT_FAIL)
            return Response().finish()
        return Response().success(data=products.products)

    def get_products_ext_export(self, products):
        extend = Prodict()
        for product in products:
            product_id = to_str(product.id)
            meta = self.api("products/{}/metafields.json".format(product.id))
            extend.set_attribute(product_id, Prodict())
            extend[to_str(product_id)].meta = meta.metafields
        return Response().success(extend)

    def get_product_id_import(self, convert: Product, product, products_ext):
        return product.id

    def updated_at_to_timestamp(self, updated_at, time_format='%Y-%m-%d %H:%M:%S'):
        return to_timestamp(''.join(updated_at.rsplit(':', 1)), '%Y-%m-%dT%H:%M:%S%z', limit_len=False)

    def _convert_product_export(self, product, products_ext: Prodict):
        product_id = to_str(product.id)
        product_data = Product()
        channel_id = to_str(self._state.channel.id)
        product_data.tags = product.tags
        count_children = to_len(product.variants) if product.variants else None
        if not count_children:
            return Response().error(Errors.SHOPIFY_API_INVALID)
        # if product.variants[0].compare_at_price:
        # 	if to_decimal(product.variants[0].compare_at_price) > to_decimal(product.variants[0].price):
        # 		product_data.special_price.price = product.variants[0].price
        # 		product_data.special_price.special_price = ''
        # 		product_data.special_price.end_date = ''
        # 		product_data.price = product.variants[0].compare_at_price
        # 	else:
        # 		product_data.price = product.variants[0].price
        # else:
        all_collection = list()
        custom_collection = self.api('custom_collections.json', data={
                                     'product_id': product_id})
        smart_collections = self.api('smart_collections.json', data={
                                     'product_id': product_id})
        if custom_collection and custom_collection.custom_collection:
            all_collection += custom_collection.custom_collection
        if smart_collections and smart_collections.smart_collections:
            all_collection += smart_collections.smart_collections
        for collection in all_collection:
            product_data.category_name_list.append(collection.title)
        product_data.price = product.variants[0].price
        # product['variants'][0]['grams'] if product['variants'][0]['weight_unit'] == 'g' else
        product_data.weight = product.variants[0].weight
        # product['variants'][0]['grams'] if product['variants'][0]['weight_unit'] == 'g' else
        product_data.weight_units = product.variants[0].weight_unit
        product_data.status = True if product.published_at else False
        product_data.manage_stock = True if product.variants[0].inventory_management else False
        if product_data.manage_stock:
            product_data.is_in_stock = True if to_int(
                product.variants[0].inventory_quantity) > 0 else False
        else:
            product_data.is_in_stock = True
        product_data.created_at = convert_format_time(
            ''.join(product.created_at.rsplit(':', 1)), '%Y-%m-%dT%H:%M:%S%z')
        product_data.updated_at = convert_format_time(
            ''.join(product.updated_at.rsplit(':', 1)), '%Y-%m-%dT%H:%M:%S%z')
        product_data.name = product.title
        product_data.description = product.body_html
        product_data.barcode = product.variants[0].barcode
        if product.image and product.image.src:
            product_data.thumb_image.url = product.image.src
            product_data.thumb_image.label = product.image.alt

        if product.images:
            for image in product.images:
                if image['id'] == product['image']['id']:
                    continue
                product_image_data = ProductImage()
                product_image_data.url = image.src
                product_image_data.label = image.alt
                product_image_data.position = image.position
                product_data.images.append(product_image_data)
        product_data.brand = product.vendor
        product_data.seo_url = f"{self.get_channel_url()}/products/{product.handle.strip('/')}"
        if products_ext and products_ext.get_attribute(product_id).meta:
            for metafields in products_ext.get_attribute(product_id).meta:
                if metafields.key == 'short_description':
                    product_data.short_description = metafields.value
                elif metafields.key == 'description_tag':
                    product_data.meta_description = metafields.value
                elif metafields.key == 'title_tag':
                    product_data.meta_title = metafields.value
                else:
                    attribute_data = ProductAttribute()
                    attribute_data.id = metafields.id
                    attribute_data.attribute_name = metafields.key
                    attribute_data.attribute_value_name = metafields.value
                    attribute_data.attribute_type = 'text'
                    product_data.attributes.append(attribute_data)
        if product.variants:
            qty = 0
            is_in_stock = False
            manage_stock = False
            for variant in product.variants:
                qty += to_int(variant.inventory_quantity)

                if variant.inventory_management:
                    variant_is_in_stock = True if to_int(
                        variant.inventory_quantity) > 0 else False
                else:
                    variant_is_in_stock = True
                if variant_is_in_stock:
                    is_in_stock = True
                variant_manage_stock = True if variant.inventory_management else False
                if variant_manage_stock:
                    manage_stock = True
                if variant.title.lower() in ['default title', 'default']:
                    product_data.sku = variant.sku
                    continue

                variant_data = ProductVariant()
                variant_data.id = to_str(variant.id)
                # variant_data.set_attribute('channel_{}'.format(channel_id), variant_id)
                # variant_channel = ProductChannel()
                # variant_channel.product_id = variant_id
                # variant_data.channel.append(variant_channel)
                variant_data.name = product.title + "-" + variant.title
                variant_data.sku = variant.sku
                variant_data.status = product.status
                variant_data.price = variant.price
                if variant.compare_at_price and to_decimal(variant.compare_at_price) > to_decimal(variant.price):
                    variant_data.special_price.price = variant.price
                    variant_data.price = variant.compare_at_price
                image = get_row_value_from_list_by_field(
                    product.images, 'id', variant.image_id, 'src')
                if image:
                    variant_data.thumb_image.url = image
                variant_data.qty = to_int(variant.inventory_quantity)
                variant_data.manage_stock = variant_manage_stock
                variant_data.is_in_stock = variant_is_in_stock
                variant_data.weight = variant['weight']
                variant_data.created_at = convert_format_time(
                    ''.join(variant.created_at.rsplit(':', 1)), '%Y-%m-%dT%H:%M:%S%z')
                variant_data.updated_at = convert_format_time(
                    ''.join(variant.updated_at.rsplit(':', 1)), '%Y-%m-%dT%H:%M:%S%z')
                variant_sku = to_str(variant.sku)
                for index in range(1, 4):
                    if variant.get_attribute('option{}'.format(index)):
                        variant_attribute = ProductVariantAttribute()
                        variant_attribute.id = "{}_{}".format(
                            product_id, index)
                        variant_attribute.attribute_type = 'select'
                        variant_attribute.attribute_name = get_row_value_from_list_by_field(
                            product.options, 'position', index, 'name')
                        variant_attribute.attribute_value_name = variant.get_attribute(
                            'option{}'.format(index))
                        variant_sku = variant_sku.replace(
                            variant_attribute.attribute_value_name, '')
                        variant_data.attributes.append(variant_attribute)
                if not variant_data.attributes:
                    continue
                if not product_data.sku:
                    variant_sku = variant_sku.strip(' -_')
                    if to_str(variant.sku).startswith(variant_sku):
                        product_data.sku = variant_sku
                    else:
                        product_data.sku = variant.sku
                product_data.variants.append(variant_data)
            product_data.qty = qty
            product_data.is_in_stock = is_in_stock
            product_data.manage_stock = manage_stock

        # if product_data.variants:
        # 	real_sku = to_str(product_data.sku)
        # 	product_data.sku = None
        # 	sku = real_sku.split('-')
        # 	if len(sku) > 1:
        # 		suffix = to_str(sku[-1]).strip(' ')
        # 		if suffix.isnumeric():
        # 			del sku[-1]
        # 			sku = "-".join(sku)
        # 			real_sku = sku
        # 	product_data.sku = real_sku
        if not product_data.sku:
            product_data.sku = product.id
        return Response().success(product_data)

    def extend_images(self, product):
        images = list()
        if product.thumb_image.url:
            main_image = self.process_image_before_import(
                product.thumb_image.url, product.thumb_image.path)
            images.append(main_image['url'])
        # image_data = self.resize_image(main_image['url'])
        # if image_data:
        # 	images.append(image_data)
        # else:
        # 	images.append({'src': html_unquote(main_image['url'])})
        for img_src in product.images:
            if 'status' in img_src and not img_src['status']:
                continue
            image_process = self.process_image_before_import(
                img_src.url, img_src.path)
            if image_process['url'] not in images:
                images.append(image_process['url'])
        return images

    def product_import(self, convert: Product, product, products_ext):
        convert_product = self.product_to_shopify_data(product, products_ext)
        if convert_product.result != Response.SUCCESS:
            return convert_product
        post_data, images = convert_product.data
        response = self.api('products.json', post_data, 'Post')
        check_response = self.check_response_import(
            response, product, 'product')
        if check_response.result != Response.SUCCESS:
            if 'Image' in check_response['msg']:
                del post_data['product']['images']
                response = self.api('products.json', post_data, 'Post')
                response = json_decode(response)
                check_response = self.check_response_import(
                    response, convert, 'product')
                if check_response['result'] != 'success':
                    return check_response
            else:
                return check_response

        product_id = response['product']['id']
        # Product variants, inventory
        product_images = dict()
        for index, image in enumerate(images):
            try:
                product_images[image] = response.product.images[index]['id']
            except:
                pass
        self.set_last_product_response(response, product_images)
        return Response().success(product_id)

    def product_to_shopify_data(self, product: Product, product_ext):
        if not product.name:
            return Response.error(Errors.PRODUCT_DATA_INVALID)
        # name = to_str(product.name).replace('/', '-')
        # Add thumbnail, images
        images = self.extend_images(product)
        # if product.variants:
        # 	for variant in product.variants:
        # 		images += self.extend_images(variant)
        # images = list(set(images))
        shopify_images = list()
        for index, image in enumerate(images):
            image_data = self.resize_image(image)
            if not image_data:
                image_data = {'src': html_unquote(image)}
            image_data['position'] = index + 1
            shopify_images.append(image_data)

        # Initiate Post data

        post_data = {
            'product': {
                'title': product.name[0:255],
                'body_html': nl2br(product.description if product.description else product.short_description),
                'vendor': product.brand,
                'product_type': '',
                'images': shopify_images,
                # 'created_at': product.created_at,
                'updated_at': product.updated_at
            }
        }
        if product.weight:
            post_data['product']['weight'] = to_decimal(product.weight)
            post_data['product']['weight_unit'] = product.weight_units or 'oz'
        # Add product's status
        if not product.status:
            post_data['product']["published"] = False
            post_data['product']['published_at'] = None

        if product.meta_keyword or product.meta_title:
            post_data['product']['metafields_global_title_tag'] = product.meta_title
            post_data['product']['metafields_global_description_tag'] = product.meta_keyword
        metafields_keys = list()
        post_data['product']['metafields'] = list()
        special_attribute = ('description', 'short_description')
        if product.attributes:
            for attribute in product.attributes:
                if to_str(attribute.attribute_name) in special_attribute or not attribute.attribute_name:
                    continue
                option_name = self.name_to_code(attribute.attribute_name)
                if option_name == 'brand' and not post_data['product']['vendor']:
                    post_data['product']['vendor'] = attribute.attribute_value_name
                    continue
                index = 2
                while option_name in metafields_keys:
                    option_name = attribute.option_name + \
                        ' ' + to_str(index) + 'nd'
                    index += 1
                metafields_keys.append(option_name)
                if to_len(option_name) < 3:
                    continue
                metafield = {
                    'key': option_name[:30],
                    'value': attribute.attribute_value_name,
                    'type': 'single_line_text_field',
                    'namespace': 'global'
                }
                post_data['product']['metafields'].append(metafield)
        # add metafield Dimensions
        dimensions = ('length', 'width', 'height')
        for dimension in dimensions:
            if dimension in metafields_keys:
                continue
            if to_decimal(product.get_attribute(dimension)):
                metafield = {
                    'key': dimension,
                    'value': to_str(to_decimal(product.get_attribute(dimension))),
                    'type': 'single_line_text_field',
                    'namespace': 'global'
                }
                post_data['product']['metafields'].append(metafield)
        if not product.description and product.short_description:
            option_name = 'short_description'
            index = 2
            while option_name in metafields_keys:
                option_name = 'short_description' + ' ' + to_str(index) + 'nd'
                index += 1
            metafields_keys.append(option_name)
            metafield = {
                'key': option_name[:30],
                'value': product.short_description,
                'type': 'single_line_text_field',
                'namespace': 'global'
            }
            post_data['product']['metafields'].append(metafield)
        tags = to_str(product['tags']).split(',')
        template_category = product.get(
            'template_data', {}).get('category', {})
        if template_category and template_category.get('categories'):
            for category in template_category['categories']:
                if category.get('collection_type') == self.SMART_COLLECTION:
                    tags.append(category.category_name)

        elif self.is_auto_import_category() and product.category_path:
            category_name = product.category_path.split('>')[-1].strip()
            check_smart_collection = self.get_smart_collection_by_name(
                category_name)
            tags.append(category_name)

        if tags:
            tags = ','.join(list(set(tags)))
            post_data['product']['tags'] = to_str(tags).strip(', ')
        return Response().success((post_data, images))

    def variant_to_shopify_data(self, product_id, variant, options, images):
        compare_price, sale_price = self.to_shopify_price(variant)

        variant_post_data = {
            'title': variant.name,
            'compare_at_price': compare_price,
            'price': sale_price,
            'sku': variant.sku,
            'barcode': variant.barcode or variant.upc or variant.ean,
            'weight': to_decimal(variant.weight) if to_decimal(variant.weight) > 0 else 0,
            'inventory_management': 'shopify' if variant.manage_stock else None,
            # 'inventory_quantity': to_int(variant.qty),
            'cost': variant.cost,
            'inventory_policy': 'deny' if variant.manage_stock else 'continue',
        }
        if variant.thumb_image.url:
            main_image = self.process_image_before_import(
                variant.thumb_image.url, variant.thumb_image.path)
            image_url = main_image['url']
            if images.get(image_url):
                variant_post_data['image_id'] = images.get(image_url)
        for attribute in variant.attributes:
            attribute_name = to_str(attribute.attribute_name).replace('/', '-')

            variant_post_data['option' + to_str(
                options[attribute_name]['position'])] = attribute.attribute_value_name
        return variant_post_data

    def after_product_import(self, product_id, convert: Product, product, products_ext):
        template_category = product.get(
            'template_data', {}).get('category', {})
        if template_category and template_category.get('categories'):
            for category in template_category['categories']:
                if category.get('collection_type') == self.SMART_COLLECTION:
                    continue
                cat_post_data = {
                    'collect': {
                        'collection_id': category.category_id,
                        'product_id': product_id
                    }
                }
                self.api('collects.json', cat_post_data, 'Post')
        response, images = self.get_last_product_response()
        if product.variants:
            options = self.get_options_from_variants(product.variants)
            variants_post_data = []
            for variant in product.variants:
                variant_post_data = self.variant_to_shopify_data(
                    product_id, variant, options, images)
                variants_post_data.append(variant_post_data)
            # Add options post data
            options_post_data = []
            for option_key, option_value in options.items():
                options_post_data.append(
                    {
                        'name': option_key,
                        'values': option_value['values']
                    }
                )
            post_data = {
                'product': {
                    'id': product_id,
                    'variants': variants_post_data,
                    'options': options_post_data
                }
            }
            var_response = self.api(
                'products/' + to_str(product_id) + '.json', post_data, 'Put')
            check_response = self.check_response_import(
                var_response, product, 'product')
            if check_response.result != Response.SUCCESS:
                return check_response
            for index, variant_res in enumerate(var_response['product']['variants']):
                child = product.variants[index]
                self.insert_map_product(child, child['_id'], variant_res.id)
        # Import inventory for simple product
        else:
            default_variant = response['product']['variants'][0]
            compare_price, sale_price = self.to_shopify_price(product)

            variants_post_data = {
                'id': default_variant['id'],
                'title': 'Default Title',
                'compare_at_price': compare_price,
                'price': sale_price,
                'sku': product.sku,
                'barcode': product.barcode or product.upc or product.ean,
                'weight': to_decimal(product.weight) if to_decimal(product.weight) > 0 else 0,
                'inventory_management': 'shopify' if product.manage_stock else None,
                'inventory_quantity': to_int(product.qty),
                'cost': product.cost,
                'inventory_policy': 'deny' if product.manage_stock else 'continue',
            }
            post_data = {
                'product': {
                    'id': product_id,
                    'variants': [variants_post_data],
                }
            }
            var_response = self.api(
                'products/' + to_str(product_id) + '.json', post_data, 'Put')
            check_response = self.check_response_import(product, var_response)
            if check_response.result != Response().SUCCESS:
                return check_response
        if var_response.get('product', dict()).get('variants'):
            location_id = self.get_location_id()
            if location_id:
                variants = var_response.get('product', dict()).get('variants')
                if variants:
                    if not product.variants:
                        inventory = self.set_inventory_level(
                            variants[0]['inventory_item_id'], product.qty)
                    else:
                        for index, row in enumerate(variants):
                            variant = product.variants[index]
                            # for variant in product.variants:
                            self.set_inventory_level(
                                row['inventory_item_id'], variant.qty)

        return Response().success()

    def product_channel_update(self, product_id, product: Product, products_ext):
        # Get product shopify data
        convert_product = self.product_to_shopify_data(product, products_ext)
        if convert_product.result != Response.SUCCESS:
            return convert_product
        product_data, images = convert_product.data
        update = self.api(f'products/{product_id}.json', product_data, 'Put')
        update_response = self.check_response_import(update, product)
        if update_response.result != Response.SUCCESS:
            return update_response
        template_category = product.get(
            'template_data', {}).get('category', {})
        if template_category and template_category.get('categories'):
            collects = self.api('collects.json', data={
                                'product_id': product_id})
            old_collection_id = dict()
            new_collection_id = list()
            if collects and collects.get('collects'):
                old_collection_id = [
                    {to_int(collect.collection_id): collect.id} for collect in collects.collects]

            for category in template_category['categories']:
                if category.get('collection_type') == self.SMART_COLLECTION:
                    continue
                new_collection_id.append(to_int(category.category_id))
            delete_ids = list(
                set(list(old_collection_id.keys())) - set(new_collection_id))
            create_ids = list(set(list(new_collection_id)) -
                              set(old_collection_id.keys()))
            for collection_id in delete_ids:
                self.api(
                    f'collects/{new_collection_id[collection_id]}.json', api_type='delete')
            for collection_id in create_ids:
                cat_post_data = {
                    'collect': {
                        'collection_id': collection_id,
                        'product_id': product_id
                    }
                }
                self.api('collects.json', cat_post_data, 'Post')

        shopify_product = update.product
        # Update product price, sku, inventory, barcode etc..
        location_id = self.get_location_id()

        if not product.variants:
            default_variant_id = shopify_product.variants[0]['id']
            compare_price, sale_price = self.to_shopify_price(product)

            variants_post_data = {
                'id': default_variant_id,
                'title': product.name,
                'compare_at_price': compare_price,
                'price': sale_price,
                'sku': product.sku,
                'barcode': product.barcode or product.upc or product.ean,
                'weight': to_decimal(product.weight) if to_decimal(product.weight) > 0 else 0,
                'inventory_management': 'shopify' if product.manage_stock else None,
                'inventory_quantity': to_int(product.qty),
                'cost': to_decimal(product.cost),
                'inventory_policy': 'deny' if product.manage_stock else 'continue',
            }
            response = self.api(f'products/{product_id}.json', {
                'product': {
                    'variants': [variants_post_data]
                }
            }, 'Put')
            check_response = self.check_response_import(product, response)
            if check_response.result != Response().SUCCESS:
                return check_response
            inventory = self.set_inventory_level(
                shopify_product.variants[0]['inventory_item_id'], product.qty)
            return Response().success()
        options = self.get_options_from_variants(product.variants)
        variant_update = list()
        shopify_variants = dict()
        for variant in product.variants:
            variant_id = variant.channel[f'channel_{self.get_channel_id()}'].get(
                'product_id')
            variant_post_data = self.variant_to_shopify_data(
                product_id, variant, options, images)
            if not variant_id:
                create_variant = self.api(
                    f"products/{product_id}/variants.json", variant_post_data, 'post')
                if create_variant and create_variant.variant:
                    self.insert_map_product(
                        variant, variant['_id'], create_variant.variant.id)
                    variant_id = create_variant.variant.id
                else:
                    continue
            else:
                variant_post_data['id'] = variant_id
                variant_update.append(variant_post_data)
            shopify_variants[to_int(variant_id)] = variant
        response = self.api(
            f'products/{product_id}.json', {'product': {'variants': variant_update}}, 'Put')
        check_response = self.check_response_import(response, product)
        if check_response.result != Response.SUCCESS:
            return check_response
        for variant in response.product.variants:
            shopify_variant = shopify_variants.get(variant.id)
            if not shopify_variant:
                continue
            inventory = self.set_inventory_level(
                variant['inventory_item_id'], shopify_variant.qty)
            pass
        return Response().success()

    def set_inventory_level(self, inventory_item_id, qty):
        ivt_data = {
            'location_id': self.get_location_id(),
            'inventory_item_id': inventory_item_id,
            'available': to_int(qty)
        }
        inventory = self.api('inventory_levels/set.json', ivt_data, 'Post')
        return inventory

    def channel_sync_inventory_level(self, variant, shopify_variant):
        update_data = dict()
        if variant.manage_stock and not shopify_variant.get('inventory_management'):
            update_data['inventory_management'] = 'shopify'
        if not variant.manage_stock and shopify_variant.get('inventory_management'):
            update_data['inventory_management'] = None
        if update_data:
            self.api(
                f'variants/{shopify_variant["id"]}.json', {'variant': update_data}, 'put')
        if variant.manage_stock:
            self.set_inventory_level(
                shopify_variant['inventory_item_id'], variant.qty)

    def channel_sync_inventory(self, product_id, product, products_ext):
        setting_price = True if self._state.channel.config.setting.get(
            'price', {}).get('status') != 'disable' else False
        setting_qty = True if self._state.channel.config.setting.get(
            'qty', {}).get('status') != 'disable' else False
        if not setting_price and not setting_qty:
            return Response().success()
        product_shopify_data = self.api(f'products/{product_id}.json')
        if not product_shopify_data.product:
            return Response().error()
        shopify_variants = {
            row['id']: row for row in product_shopify_data.product.variants}
        # Update product price, sku, inventory, barcode etc..
        update_data = {
            'product': {
                'id': product_id,
            }
        }
        # Update product price, sku, inventory, barcode etc..
        if not product.variants:
            default_variant_id = product_shopify_data['product']['variants'][0]['id']
            inventory_item_id = product_shopify_data['product']['variants'][0]['inventory_item_id']
            if setting_qty:
                self.channel_sync_inventory_level(
                    product, product_shopify_data['product']['variants'][0])

            variants_post_data = {
                'id': default_variant_id,
            }
            if setting_price:
                compare_price, sale_price = self.to_shopify_price(product)
                # price = product.price
                # compare_price = None
                # if self.is_special_price(product):
                # 	sale_price = special_price.price
                # 	compare_price = price if price and to_decimal(price) > to_decimal(sale_price) else None
                # else:
                # 	if product.msrp:
                # 		compare_price = product.msrp
                # 		sale_price = price
                # 	else:
                # 		sale_price = price
                variants_post_data['compare_at_price'] = compare_price
                variants_post_data['price'] = sale_price
                variants_post_data['cost'] = to_decimal(product.cost)

            update_data['product']['variants'] = [variants_post_data]
            response = self.api(
                'products/' + to_str(product_id) + '.json', update_data, 'Put')
            check_response = self.check_response_import(product, response)
            if check_response.result != Response().SUCCESS:
                return check_response
        else:
            variants_post_data = []
            channel_id = self._state.channel.id
            for variant in product.variants:
                variant_id = to_int(variant['channel'].get(
                    f'channel_{channel_id}', {}).get('product_id'))
                if not variant_id:
                    continue
                if setting_qty and shopify_variants.get(variant_id):
                    self.channel_sync_inventory_level(
                        variant, shopify_variants[variant_id])

                # self.set_inventory_level(shopify_variants[variant_id]['inventory_item_id'], variant.qty)
                # special_price = variant.special_price
                # price = variant.price
                # compare_price = None
                # if special_price.price and to_timestamp(special_price.start_date) < time.time() and (to_timestamp(special_price.end_date > time.time() or special_price.end_date == '0000-00-00' or special_price.end_date == '0000-00-00 00:00:00') or special_price.end_date == '' or not special_price.end_date):
                # 	sale_price = special_price.price
                # 	compare_price = price if price and to_decimal(price) > to_decimal(sale_price) else None
                # else:
                # 	sale_price = price
                manage_stock = variant.manage_stock
                variant_post_data = {
                    'id': variant_id,
                }
                if setting_price:
                    compare_price, sale_price = self.to_shopify_price(variant)

                    variant_post_data['compare_at_price'] = compare_price,
                    variant_post_data['price'] = sale_price,
                    variant_post_data['cost'] = to_decimal(product.cost)
                # if setting_qty:
                # 	variant_post_data['inventory_management'] = 'shopify' if product.manage_stock else None
                # 	variant_post_data['inventory_quantity'] = to_int(product.qty)
                # 	variant_post_data['inventory_policy'] = 'deny' if manage_stock else 'continue'
                variants_post_data.append(variant_post_data)
            update_data['product']['variants'] = variants_post_data
            response = self.api(
                'products/' + to_str(product_id) + '.json', update_data, 'Put')
            check_response = self.check_response_import(product, response)
            if check_response.result != Response().SUCCESS:
                return check_response
        return Response().success()

    def delete_product_import(self, product_id):
        remove = self.api(f'products/{product_id}.json', None, 'delete')
        return Response().success()

    def get_options_from_variants(self, variants):
        options = {}
        position = 1
        for variant in variants:
            for attribute in variant.attributes:
                if not attribute.use_variant:
                    continue
                attribute_name = to_str(
                    attribute.attribute_name).replace('/', '-')
                if attribute_name not in options.keys():
                    options[attribute_name] = {
                        'values': [attribute.attribute_value_name],
                        'position': position
                    }
                    position += 1
                elif attribute.attribute_value_name not in options[attribute_name]['values']:
                    options[attribute_name]['values'].append(
                        attribute.attribute_value_name)

        return options

    # orders

    def get_order_by_id(self, order_id):
        order = self.api(f'orders/{order_id}.json')
        if not order or not order.get('order'):
            return Response().error()
        return Response().success(order['order'])

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
                "created_at_min": start_time,
                "status": 'any',
                'limit': limit_data,
            }
            if last_modifier:
                params['updated_at_min'] = last_modifier
            orders = self.api('orders.json', data=params)
        if not orders or not orders.orders:
            if self._last_status != 200:
                return Response().error(Errors.SHOPIFY_GET_PRODUCT_FAIL)
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
        return Response().success(data=orders.orders)

    def get_orders_ext_export(self, orders):
        return Response().success()

    def order_canceled(self, channel_order_id, order_id, order: Order, current_order: Order, setting_order=True):
        cancel_order = self.api(
            f'{channel_order_id}/cancel.json', api_type='post')
        if self._last_status == 200:
            update_data = {
                f"channel.channel_{self.get_channel_id()}.order_status": Order.CANCELED,
                f"channel.channel_{self.get_channel_id()}.cancelled_at": cancel_order.cancelled_at
            }
            self.get_model_order().update(order_id, update_data)

        return self._order_sync_inventory(order, '+')

    def order_completed(self, channel_order_id, order_id, order: Order, current_order: Order, setting_order=True):
        return self.channel_order_completed(channel_order_id, order, current_order)

    def order_sync_inventory(self, convert: Order, setting_order):
        return self._order_sync_inventory(convert)

    def _order_sync_inventory(self, convert: Order, prefix='-'):
        for row in convert.products:
            product_id = None
            variant_id = None
            if row['product_id'] and row['parent_id']:
                variant_id = row['product_id']
                product_id = row['parent_id']
            else:
                product_id = row['product_id']
                if product_id:
                    product_info = self.api(
                        'products/' + to_str(product_id) + '.json')
                    if product_info:
                        if isinstance(product_info, dict) and product_info.get('product'):
                            variant_id = product_info['product']['variants'][0]['id']
                            if row['product'].get('sku'):
                                for variant in product_info['product']['variants']:
                                    if row['product'].get('sku') == variant['sku']:
                                        variant_id = variant['id']
                                        break
            row_qty = to_int(row['qty']) if to_int(row.qty) > 0 else 1
            if (prefix == '-' and convert.status != Order.CANCELED) or (prefix == '+' and convert.status == Order.CANCELED):
                variant = self.api(f'variants/{variant_id}.json')
                if variant.get('variant') and variant.variant.inventory_management:
                    inventory_quantity = to_int(
                        variant['variant']['inventory_quantity'])
                    new_qty = to_int(inventory_quantity) - to_int(
                        row_qty) if prefix == '-' else to_int(inventory_quantity) + to_int(row_qty)
                    if new_qty < 0:
                        new_qty = 0
                    inventory = self.set_inventory_level(
                        variant['variant']['inventory_item_id'], new_qty)
        return Response().success()

    def order_import(self, order: Order, convert: Order, orders_ext):
        if convert.get('financial_status'):
            financial_status = convert['financial_status']
        else:
            financial_status = self.FINANCIAL_ORDER_STATUS.get(
                convert['status'], 'pending')
        if convert.get('fulfillment_status'):
            fulfillment_status = convert['fulfillment_status']
        else:
            fulfillment_status = self.FULFILLMENT_STATUS.get(
                convert['status'], None)

        post_data = {
            'order': {
                'financial_status': financial_status,
                'fulfillment_status': fulfillment_status,
                'confirmed': True,
                'total_price': round(to_decimal(convert.total), 2),
                'subtotal_price': round(to_decimal(convert.subtotal), 2),
                'currency': convert.currency or 'USD',
                'processed_at': convert.created_at,
                'updated_at': convert.updated_at,
                'send_receipt': False,
                'send_fulfillment_receipt': False,
                'suppress_notifications': True,
                # 'name': convert.order_number,
            }
        }
        if convert.channel_order_number:
            post_data['order']['tags'] = f"{to_str(convert.order_number_prefix)}{to_str(convert.channel_order_number)}"
        if post_data['order']['financial_status'] == 'paid' and post_data['order']['total_price'] > 0:
            post_data['order']['transactions'] = [
                {
                    'amount': round(to_decimal(post_data['order']['total_price']), 2),
                    'kind': 'sale',
                            'test': False,
                            'status': 'success'
                }
            ]

        if convert.discount.amount and (abs(to_decimal(convert.discount.amount)) > 0):
            post_data['order']['discount_codes'] = list()
            discount_code = dict()
            post_data['order']['total_discounts'] = round(
                abs(to_decimal(convert.discount.amount)), 2)
            discount_code_title = 'dc'
            if convert.discount.code:
                discount_code_title = convert.discount.code
            elif convert.discount.title:
                discount_code_title = convert.discount.title
            discount_code['code'] = discount_code_title
            discount_code['amount'] = round(
                abs(to_decimal(convert.discount.amount)), 2)
            discount_code['type'] = ''
            post_data['order']['discount_codes'].append(discount_code)

        if convert.tax.amount and to_decimal(convert.tax.amount) > 0:
            post_data['order']['total_tax'] = round(
                to_decimal(convert.tax.amount), 2)
            total_ex_tax = to_decimal(
                convert.total) - to_decimal(convert.tax.amount)
            rate = 0
            if total_ex_tax > 0:
                rate = round(to_decimal(convert.tax.amount) / total_ex_tax, 2)
            elif to_decimal(convert.total) > 0:
                rate = round(to_decimal(convert.tax.amount) /
                             to_decimal(convert.total), 2)
            post_data['order']['tax_lines'] = [{
                'rate': rate,
                'title': 'TAX',
                'price': round(to_decimal(convert.tax.amount), 2)
            }]

        if convert.shipping.amount and to_decimal(convert.shipping.amount) > 0:
            post_data['order']['shipping_lines'] = list()
            ship_lines = dict()
            ship_lines['price'] = round(to_decimal(convert.shipping.amount), 2)
            ship_lines['title'] = convert.shipping.title or 'Shipping'
            ship_lines['code'] = 'Shipping'
            post_data['order']['shipping_lines'].append(ship_lines)
        else:
            post_data['order']['shipping_lines'] = list()
            ship_lines = dict()
            ship_lines['price'] = 0
            ship_lines['title'] = 'Free Shipping'
            ship_lines['code'] = 'Shipping'
            post_data['order']['shipping_lines'].append(ship_lines)

        customer_data = {
            'first_name': convert.customer.first_name or convert.billing_address.first_name or convert.shipping_address.first_name,
            'last_name': convert.customer.last_name or convert.billing_address.last_name or convert.shipping_address.last_name,
            'email': re.sub("gmail.com.+", 'gmail.com', convert.customer.email),
            # 'total_spent': round(to_decimal(convert.total), 2),
        }
        post_data['order']['customer'] = customer_data
        billstate_code = {
            'name': None,
            'code': None,
        }
        if convert.billing_address.state.state_name or convert.billing_address.state.state_code:
            billstate_code = self.get_province_from_country(
                convert.billing_address.country.country_code, convert.billing_address.state.state_name, convert.billing_address.state.state_code)

        billing_data = {
            'first_name': convert.billing_address.first_name or '',
            'last_name': convert.billing_address.last_name or '',
            'address1': convert.billing_address.address_1 or '',
            'address2': convert.billing_address.address_2 or '',
            'city': convert.billing_address.city or 'City',
            'city': convert.billing_address.city or 'City',
            'province': convert.billing_address.state.state_name or billstate_code['name'],
            'country': convert.billing_address.country.country_name or '',
            'province_code': convert.billing_address.state.state_code or billstate_code['code'],
            'country_code': convert.billing_address.country.country_code or '',
            'zip': convert.billing_address.postcode or '',
            'phone': convert.billing_address.telephone or '',
            'name': ' '.join([convert.billing_address.first_name or '', convert.billing_address.last_name or '']),
            'latitude': None,
            'longitude': None,
            'company': convert.billing_address.company or '',
        }

        shipstate_code = {
            'name': None,
            'code': None,
        }
        if convert.shipping_address.state.state_name or convert.shipping_address.state.state_code:
            shipstate_code = self.get_province_from_country(
                convert.shipping_address.country.country_code, convert.shipping_address.state.state_name, convert.shipping_address.state.state_code)

        shipping_data = {
            'first_name': convert.shipping_address.first_name or '',
            'last_name': convert.shipping_address.last_name or '',
            'address1': convert.shipping_address.address_1 or '',
            'address2': convert.shipping_address.address_2 or '',
            'city': convert.shipping_address.city or 'City',
            'province': convert.shipping_address.state.state_name or shipstate_code['name'],
            'country': convert.shipping_address.country.country_name or '',
            'province_code': convert.shipping_address.state.state_code or billstate_code['code'],
            'country_code': convert.shipping_address.country.country_code or '',
            'zip': convert.shipping_address.postcode or '',
            'phone': convert.shipping_address.telephone or '',
            'name': ' '.join([convert.shipping_address.first_name or '', convert.shipping_address.last_name or '']),
            'latitude': None,
            'longitude': None,
            'company': convert.shipping_address.company or '',
        }
        post_data['order']['billing_address'] = billing_data
        post_data['order']['shipping_address'] = shipping_data
        comment = ''
        for history in convert.history:
            if history['comment']:
                comment += self.clear_tags(
                    to_str(history['comment']).replace('<br />', '\n'))
        post_data['order']['note'] = comment[:5000]

        order_items = list()
        for row in convert.products:
            product_id = None
            variant_id = None
            if row['product_id'] and row['parent_id']:
                variant_id = row['product_id']
                product_id = row['parent_id']
            else:
                product_id = row['product_id']
                if product_id:
                    product_info = self.api(
                        'products/' + to_str(product_id) + '.json')
                    if product_info:
                        if isinstance(product_info, dict) and product_info.get('product'):
                            variant_id = product_info['product']['variants'][0]['id']
                            if row['product'].get('sku'):
                                for variant in product_info['product']['variants']:
                                    if row['product'].get('sku') == variant['sku']:
                                        variant_id = variant['id']
                                        break
            row_qty = to_int(row['qty']) if to_int(row.qty) > 0 else 1
            # if convert.status != Order.CANCELED:
            # 	variant = self.api(f'variants/{variant_id}.json')
            # 	if variant.get('variant'):
            # 		inventory_quantity = to_int(variant['variant']['inventory_quantity'])
            # 		if inventory_quantity < to_int(row_qty):
            # 			return Response().error(msg = f"Product {row.product_sku} out of stock")
            # 		ivt_data = {
            # 			'location_id': self.get_location_id(),
            # 			'inventory_item_id': variant['variant']['inventory_item_id'],
            # 			'available': to_int(inventory_quantity) - to_int(row_qty)
            # 		}
            # 		inventory = self.api('inventory_levels/set.json', ivt_data, 'Post')
            if not variant_id:
                return Response().error(code=Errors.SHOPIFY_ORDER_NO_ITEM)

            item = {
                'variant_id': variant_id,
                'title': to_str(row.product_name)[0:255],
                'price': round(to_decimal(row.price), 2),
                'quantity': row_qty,
                'sku': to_str(row.product_sku),
                'product_id': product_id if product_id else None,
                'total_discount': round(to_decimal(row.discount_amount), 2),
                'variant_title': None,
                'name': to_str(row.product_name)[0:255],
                'properties': [],
                # 'grams': to_int(row['product']['weight'] if row['product'] else 0)
            }
            order_items.append(item)
        if not order_items or len(order_items) == 0:
            return Response().error(code=Errors.SHOPIFY_ORDER_NO_ITEM)
        post_data['order']['line_items'] = order_items
        response = self.api('orders.json', post_data, 'Post')
        # response = json_decode(response)

        retry = 5
        while retry > 0 and response and response.get('errors'):
            retry -= 1
            if response['errors'].get('order'):
                # retry if error Phone is invalid
                if response['errors']['order'] and 'Phone is invalid' in response['errors']['order']:
                    del post_data['order']['phone']
                    del post_data['order']['billing_address']['phone']
                    del post_data['order']['shipping_address']['phone']

            if (response['errors'].get('customer') and response['errors']['customer'][0] in ['Email contains an invalid domain name', 'Email is invalid']) or response['errors'].get('customer.email_address'):
                # retry if error Email contains an invalid domain name
                cust_email = post_data['order']['customer'].get('email')
                # replace special characters
                cust_email = re.sub('[^A-Za-z0-9]+', '', to_str(cust_email))
                # convert into @gmail.com
                cust_email = cust_email + "@shopify.com"

                self.log("Retry with " + post_data['order']['customer'].get(
                    'email') + " = " + cust_email, "orders_errors")
                post_data['order']['customer']["email"] = cust_email

            if 'Exceeded  API rate limit, please try again in a minute.' in response['errors']:
                time.sleep(60)
            # call api again
            response = self.api('orders.json', post_data, 'Post')

        check_response = self.check_response_import(response, convert, 'order')
        if check_response['result'] != 'success':
            return check_response

        id_desc = response['order']['id']
        order_number = response['order']['name']
        # update customer phone
        customer_id = response['order']['customer']['id']
        # phone = get_value_by_key_in_dict(convert['billing_address'], 'telephone', get_value_by_key_in_dict(convert['shipping_address'], 'telephone', ''))
        # if customer_id and phone:
        # 	customer_data = {
        # 		'customer': {
        # 			'phone': phone
        # 		}
        # 	}
        # 	a = self.api('customers/' + str(customer_id) + '.json', customer_data, 'PUT')
        order_return = {
            'order_id': response['order']['id'],
            'order_status': response['order']['financial_status'],
            'order_number': response['order']['order_number'],
            'created_at': response['order']['created_at'],
        }
        return Response().success([id_desc, order_return])

    def channel_order_canceled(self, order_id, order: Order, current_order):
        order_canceled = self.api(f"orders/{order_id}/cancel", api_type='post')

        return Response().success()

    def channel_order_completed(self, order_id, order: Order, current_order):
        channel_default = self.get_channel_default()
        order_channel = current_order.channel[f"channel_{channel_default['id']}"]
        order_data = {
            "fulfillment": {
                "location_id": self.get_location_id(),
                "notify_customer": False,
                "tracking_number": order_channel['order_id'] or order_channel.get('id'),
                "tracking_urls": [channel_default['url']]
            }
        }
        self.api(f'orders/{order_id}/fulfillments.json', order_data)
        return Response().success()

    def convert_order_status(self, status):
        order_status = {
            "pending": Order.OPEN,
            "partially_refunded": Order.OPEN,
            "authorized": Order.AWAITING_PAYMENT,
            "partially_paid": Order.SHIPPING,
            "paid": Order.COMPLETED,
            "voided": Order.CANCELED,
            "refunded": Order.CANCELED,
            Order.CANCELED: Order.CANCELED,

        }
        return order_status.get(status, 'open') if status else 'open'

    def convert_order_export(self, order, orders_ext, channel_id=None):
        self.set_order_max_last_modifier(order.updated_at)
        order_data = Order()
        order_data.id = order.id
        order_data.channel_order_number = order.name
        if order.cancelled_at:
            order.financial_status = Order.CANCELED
        if order.fulfillment_status == 'fulfilled':
            order_data.status = Order.COMPLETED
        else:
            if order.financial_status == 'paid':
                order_data.status = Order.SHIPPING
            else:
                order_data.status = self.convert_order_status(
                    order.financial_status)

        order_data.tax.amount = to_decimal(order.total_tax)
        order_data.tax.amount = to_decimal(order.total_tax)
        order_data.discount.amount = to_decimal(order.total_discounts)
        if order.discount_codes:
            order_data.discount.code = order['discount_codes'][0]['code']
            order_data.discount.title = order['discount_codes'][0]['code']
        if order.shipping_lines:
            order_data.shipping.title = order['shipping_lines'][0]['title']
            order_data.shipping.amount = order['shipping_lines'][0]['price']
        order_data.subtotal = order.subtotal_price
        order_data.total = order.total_price
        order_data.currency = order.currency
        order_data.created_at = isoformat_to_datetime(
            order.created_at).strftime("%Y-%m-%d %H:%M:%S")
        order_data.updated_at = isoformat_to_datetime(
            order.updated_at).strftime("%Y-%m-%d %H:%M:%S")
        order_data.channel_data = {
            'order_status': order.financial_status if order_data.status != Order.COMPLETED else 'fulfilled',
            'created_at': order_data.created_at,
            'order_number': order.order_number,
        }
        if order.fulfillments:
            fulfillments = order.fulfillments[0]
            order_data.shipments.tracking_number = fulfillments.tracking_number
            order_data.shipments.tracking_url = to_str(fulfillments.tracking_url).replace(
                '[{track}]', to_str(fulfillments.tracking_number))
            order_data.shipments.tracking_company = fulfillments.tracking_company
            order_data.shipments.tracking_company_code = fulfillments.tracking_company
        if order.customer:
            order_data.customer.id = order.customer.id
            order_data.customer.email = order.customer.email
            order_data.customer.first_name = order.customer.first_name
            order_data.customer.last_name = order.customer.last_name
            if order.customer.default_address:
                order_data.customer_address.id = order.customer.default_address.id
                order_data.customer_address.first_name = order.customer.default_address.first_name
                order_data.customer_address.last_name = order.customer.default_address.last_name
                order_data.customer_address.address_1 = order.customer.default_address.address1
                order_data.customer_address.address_2 = order.customer.default_address.address2
                order_data.customer_address.city = order.customer.default_address.city
                order_data.customer_address.country.country_name = order.customer.default_address.country
                order_data.customer_address.country.country_code = order.customer.default_address.country_code
                order_data.customer_address.state.state_name = order.customer.default_address.province
                order_data.customer_address.state.state_code = order.customer.default_address.province_code
                order_data.customer_address.postcode = order.customer.default_address.zip
                order_data.customer_address.telephone = order.customer.default_address.phone
                order_data.customer_address.company = order.customer.default_address.company
            if order.customer.note:
                order_history = OrderHistory()
                order_history.comment = order.customer.note
        if order.billing_address:
            # order_data.billing_address.id = order.customer.billing_address.id
            order_data.billing_address.first_name = order.billing_address.first_name
            order_data.billing_address.last_name = order.billing_address.last_name
            order_data.billing_address.address_1 = order.billing_address.address1
            order_data.billing_address.address_2 = order.billing_address.address2
            order_data.billing_address.city = order.billing_address.city
            order_data.billing_address.country.country_name = order.billing_address.country
            order_data.billing_address.country.country_code = order.billing_address.country_code
            order_data.billing_address.state.state_name = order.billing_address.province
            order_data.billing_address.state.state_code = order.billing_address.province_code
            order_data.billing_address.postcode = order.billing_address.zip
            order_data.billing_address.telephone = order.billing_address.phone
            order_data.billing_address.company = order.billing_address.company
        if order.shipping_address:
            # order_data.shipping_address.id = order.customer.shipping_address.id
            order_data.shipping_address.first_name = order.shipping_address.first_name
            order_data.shipping_address.last_name = order.shipping_address.last_name
            order_data.shipping_address.address_1 = order.shipping_address.address1
            order_data.shipping_address.address_2 = order.shipping_address.address2
            order_data.shipping_address.city = order.shipping_address.city
            order_data.shipping_address.country.country_name = order.shipping_address.country
            order_data.shipping_address.country.country_code = order.shipping_address.country_code
            order_data.shipping_address.state.state_name = order.shipping_address.province
            order_data.shipping_address.state.state_code = order.shipping_address.province_code
            order_data.shipping_address.postcode = order.shipping_address.zip
            order_data.shipping_address.telephone = order.shipping_address.phone
            order_data.shipping_address.company = order.shipping_address.company
        if order.payment_gateway_names:
            order_data.payment.title = order['payment_gateway_names'][0]
            order_data.payment.method = order['payment_gateway_names'][0]
        for item in order.line_items:
            order_item = OrderProducts()
            order_item.id = item.id
            sub_total = 0
            product_id = None
            if item.product_id:
                count_variant = self.api(
                    f'products/{item.product_id}/variants/count.json')
                if count_variant and to_int(count_variant.get('count')) > 1:
                    product_id = item.variant_id
                else:
                    product_id = item.product_id
            order_item.product_id = product_id
            # order_item.product_id = item.variant_id
            order_item.product_name = item.title
            order_item.sku = item.sku
            order_item.qty = item.quantity
            order_item.price = item.price
            if not sub_total:
                sub_total = to_decimal(item.price)
            order_item.original_price = round(
                sub_total / to_int(item.quantity), 2)
            if item.tax_lines:
                tax_amount = tax_percent = 0
                for row in item.tax_lines:
                    tax_amount += to_decimal(row.price)
                    tax_percent += to_decimal(row.rate)

                order_item.tax_amount = tax_amount
            order_item.discount_amount = item.total_discount
            order_item.subtotal = sub_total
            order_item.subtotal = to_decimal(order_item['price']) * to_int(
                item['quantity']) - to_decimal(order_item['discount_amount'])
            if item.properties:
                for custom_option in item['properties']:
                    order_item_option = OrderItemOption()
                    order_item_option.option_name = custom_option.name
                    order_item_option.option_value_name = custom_option.value
                    order_item.options.append(order_item_option)
            order_data.products.append(order_item)

        return Response().success(order_data)

    def get_order_id_import(self, convert: Order, order, orders_ext):
        return order.id

    # if self._state['config']['img_des'] and post_data['product']['body_html']:
    # 	theme_data = self.get_theme_data()
    # 	if theme_data:
    # 		check = False
    # 		description = post_data['product']['body_html']
    # 		match = re.findall(r"<img[^>]+>", to_str(description))
    # 		links = list()
    # 		if match:
    # 			for img in match:
    # 				img_src = re.findall(r"(src=[\"'](.*?)[\"'])", to_str(img))
    # 				if not img_src:
    # 					continue
    # 				img_src = img_src[0]
    # 				if img_src[1] in links:
    # 					continue
    # 				links.append(img_src[1])
    # 		for link in links:
    # 			# download and replace
    # 			if self._state['src']['config'].get('auth'):
    # 				link = self.join_url_auth(link)
    # 			if to_int(theme_data['count']) >= 1500:
    # 				theme_data = self.get_theme_data(True)
    # 			if not theme_data:
    # 				break
    # 			if not self.image_exist(link):
    # 				continue
    # 			asset_post = self.process_assets_before_import(url_image = link, path = '', id_theme = theme_data['id'], name_image = convert['code'])
    # 			asset_post = json_decode(asset_post)
    # 			if asset_post and asset_post.get('asset'):
    # 				self.update_theme_data(theme_data['count'])
    # 				check = True
    # 				description = to_str(description).replace(link, asset_post['asset']['public_url'])
    # 		if check:
    # 			product_update = {
    # 				'product': {
    # 					'body_html': description
    # 				}
    # 			}
    # 			res = self.api('products/' + to_str(product_id) + '.json', product_update, 'PUT')

    def get_sizes(self, url):
        req = Request(url, headers={'User-Agent': get_random_useragent()})
        try:
            file = urlopen(req)
        except:
            self.log('image: ' + to_str(url) + ' 404', 'image_error')
            return False, False
        size = file.headers.get("content-length")
        # date = datetime.strptime(file.headers.get('date'), '%a, %d %b %Y %H:%M:%S %Z')
        # type = file.headers.get('content-type')
        if size:
            size = to_int(size)
        p = ImageFile.Parser()
        while 1:
            data = file.read(1024)
            if not data:
                break
            p.feed(data)
            if p.image:
                return size, p.image.size
        file.close()
        return size, False

    def resize_image(self, url):
        name = os.path.basename(url)
        result = dict()
        result['filename'] = name
        result['attachment'] = ''
        try:
            image_size, wh = self.get_sizes(url)
            w = 4000
            h = 4000
            if wh:
                w = wh[0]
                h = wh[1]
                if to_decimal(to_decimal(w) * to_decimal(h), 2) > to_decimal(4000 * 4000, 2):
                    if to_decimal(w) > to_decimal(h):
                        h = 4000 * h / w
                        w = 4000
                    else:
                        w = 4000 * w / h
                        h = 4000
                else:
                    return None
            time.sleep(0.4)
            r = requests.get(url)
            if r.status_code != 200:
                return result
            # image extension *.png,*.jpg
            img = Image.open(io.BytesIO(r.content))
            new_width = to_int(w)
            new_height = to_int(h)
            img = img.resize((new_width, new_height), Image.ANTIALIAS)
            output = io.BytesIO()
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(output, format='JPEG')
            im_data = output.getvalue()
            image_data = base64.b64encode(im_data)
            if not isinstance(image_data, str):
                # Python 3, decode from bytes to string
                image_data = image_data.decode()
                result['attachment'] = image_data
                return result
        except Exception as e:
            self.log(url, 'url_fail')
            self.log_traceback("url_fail")
        return None

    def check_response_import(self, response, convert, entity_type=''):
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
            return Response().error(msg=msg_errors)

        else:
            return Response().success()

    def validate_channel_url(self):
        parent = super().validate_channel_url()
        if parent.result != Response.SUCCESS:
            return parent
        return self.validate_shopify_url(self._channel_url)

    def validate_shopify_url(self, cart_url):
        shopify_code = re.findall("https://(.*).myshopify.com", cart_url)
        if not shopify_code:
            return Response().error(Errors.SHOPIFY_URL_INVALID)
        return Response().success()

    def format_url(self, url, **kwargs):
        url = super().format_url(url, **kwargs)
        url.strip('[]')
        url_parse = urllib.parse.urlparse(url)
        url = "https://" + url_parse.hostname
        validate = self.validate_shopify_url(url)
        if validate['result'] != 'success':
            detect = self.detect_shopify_url(url)
            if detect['result'] == 'success':
                url = detect['data']
        return url

    def detect_shopify_url(self, url):
        url_admin = url + "/admin"
        try:
            response = requests.get(url_admin, allow_redirects=False)
            if response.status_code == 302:
                redirect_url = response.headers.get('location')
                redirect_url = redirect_url.replace('/admin', '')
                validate = self.validate_shopify_url(redirect_url)
                if validate.result == Response.SUCCESS:
                    return Response().success(redirect_url)
        except Exception as e:
            pass
        return Response().error()

    def get_shopify_countries(self):
        if self._shopify_countries:
            return self._shopify_countries
        countries_js = self.requests(
            'https://www.shopify.com/services/countries.json', None, {"Content-Type": "application/json"})
        if not countries_js:
            return dict()
        self._shopify_countries = json_decode(countries_js)
        return self._shopify_countries

    def get_province_from_country(self, country_code, province_name=None, province_code=None):
        result = {
            'name': '',
            'code': ''
        }
        countries_data = self.get_shopify_countries()
        if countries_data:
            for country in countries_data:
                if country['code'] != country_code:
                    continue
                country_provinces = list()
                if 'provinces' in country:
                    country_provinces = country['provinces']
                if province_name or province_code:
                    for p in country_provinces:
                        if (to_str(province_name) and (to_str(province_name).lower() in to_str(p['name']).lower() or to_str(p['name']).lower() in to_str(province_name).lower())) or (to_str(province_code) and to_str(province_code).lower() == to_str(p['code']).lower()):
                            result = p
                            break
                if not result['code'] and country_provinces:
                    result = self.py_reset(country_provinces)
                break
        return result

    def check_country_code(self, country_code):
        result = False
        countries_data = self.get_shopify_countries()
        if countries_data:
            for country in countries_data:
                if country['code'] == country_code:
                    return True
        return result

    def py_reset(self, tmp):
        return tmp[0]

    def clear_tags(self, text_src):
        tag_re = re.compile(r'<[^>]+>')
        return tag_re.sub('', to_str(text_src))

    def get_location_id(self):
        if self._location_id:
            return self._location_id
        location = self.api('locations.json')
        try:
            for location_data in location['locations']:
                if location_data['active'] and not location_data.get('legacy'):
                    self._location_id = location_data['id']
            if not self._location_id:
                self._location_id = location['locations'][0]['id']
        except Exception as e:
            self.log_traceback()
            self._location_id = None
        return self._location_id

    def get_smart_collection_by_name(self, category_name):
        smart_exist = self.api('smart_collections.json', {
                               'title': category_name, 'limit': 1})
        if smart_exist and smart_exist.smart_collections:
            return True
        post_data = {
            'smart_collection': {
                'title': category_name,
                'published': True,
                'disjunctive': True,
                'rules': [
                    {
                        'column': 'tag',
                        'relation': 'equals',
                        'condition': category_name.replace(',', '')
                    }
                ]
            }
        }
        response = self.api('smart_collections.json', post_data, 'Post')
        response = json_decode(response)
        if response and response.smart_collection:
            return True
        return False

    def to_shopify_price(self, product: Product):
        special_price = product.special_price
        price = product.price
        compare_price = None
        if self.is_special_price(product):
            sale_price = special_price.price
            compare_price = price if price and to_decimal(
                price) > to_decimal(sale_price) else None
        else:
            if product.msrp and to_decimal(product.msrp) > to_decimal(price):
                compare_price = product.msrp
                sale_price = price
            else:
                sale_price = price
        return round(to_decimal(compare_price), 2), round(to_decimal(sale_price), 2)

    def get_draft_extend_channel_data(self, product):
        extend_data = dict()
        description = nl2br(product.description)
        if description != product.description:
            extend_data['description'] = description
        return extend_data
