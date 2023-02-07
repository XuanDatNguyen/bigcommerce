import copy
import unicodedata
from itertools import product

import chardet
import requests
import sendgrid
import validators as python_validators
from dateutil import relativedelta
from sendgrid.helpers.mail import *

from datasync.libs.db.nosql import Nosql
from datasync.libs.errors import Errors
from datasync.libs.messages import Messages
from datasync.libs.response import Response
from datasync.libs.utils import *
from datasync.models.collections.activity import CollectionActivity
from datasync.models.collections.catalog import Catalog
from datasync.models.collections.category import Category
from datasync.models.collections.order import CollectionOrder
from datasync.models.collections.state import State
from datasync.models.collections.template import Template
from datasync.models.constructs.activity import Activity
from datasync.models.constructs.category import CatalogCategory, CategoryChannel
from datasync.models.constructs.order import OrderChannel, Order
from datasync.models.constructs.product import Product, ProductChannel, ProductVariant
from datasync.models.constructs.state import SyncState, StateChannelAuth, StateChannelConfigPriceSync, StateChannelConfigQtySync, EntityProcess
from datasync.models.mode import ModelMode


class ModelChannel:
    INIT_INDEX_FIELDS = []
    _state: SyncState or None
    _model_sync_mode: ModelMode or None
    _model_state: State or None
    _db: Nosql or None
    COLLECTION_CATALOG_NAME = 'catalog'
    COLLECTION_ORDER_NAME = 'order'
    COLLECTION_TEMPLATE_NAME = 'template'
    DOCUMENT_CHANNEL_FIELD = 'channel'
    CONNECTOR_SUFFIX = 'le_connector'
    URL_IMAGE_PROXY = "http://45.56.81.195/img_proxy.php?img="
    PROCESS_STOPPED = 'stopped'
    PROCESS_PUSHING = 'pushing'
    PROCESS_PULLING = 'pulling'
    PROCESS_COMPLETED = 'completed'
    PROCESS_KILLED = 'killed'
    PROCESS_TYPE_PRODUCT = 'product'
    PROCESS_TYPE_CATEGORY = 'category'
    PROCESS_TYPE_ORDER = 'order'
    PROCESS_TYPE_INVENTORY = 'inventory'
    PROCESS_TYPE_REFRESH = 'refresh'
    TEMPLATE_REQUIRED_ASSIGN = ['price', 'title']
    _model_catalog: Catalog or None
    _model_category: Category or None
    _model_template: Template or None
    _model_order: CollectionOrder or None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._request_data = dict()
        self._user_id = kwargs.get('user_id')
        self._channel_type = kwargs.get('channel_type')
        self._state = None
        self._model_state = State()
        self._model_catalog = None
        self._model_category = None
        self._model_template = None
        self._model_order = None
        self._sync_id = None
        self._channel_id = None
        self._product_id = None
        self._is_test = False
        self._channel_url = ''
        self._response = Response()
        self._error = Errors()
        self._model_sync_mode = None
        self._identifier = ''
        self._name = ''
        self._type = ''
        self._id = ''
        self._last_header = None
        self._last_status = None
        self._db = None
        self._state_id = None
        self._action_stop = False
        self._warehouse_location_default = None
        self._warehouse_location_fba = None
        self._date_requested = None
        self._is_update = False
        self._process_type = ''
        self._user_plan = None
        self._user_info = None
        self._is_inventory_process = False
        self._publish_action = None
        self._src_channel_id = None
        self._channel_action = None
        self._channel_default_id = None
        self._product_available_import = None
        self._order_available_import = None
        self._user_info = None
        self._limit_process = None
        self._all_channel = dict()
        self._all_channel_by_id = dict()
        self._product_max_last_modified = ''
        self._order_max_last_modified = ''
        self._template_update = False
        self._custom_data = None
        self._extend_product_map = {}
        self._total_product = 0
        self._total_product_batch_import = 0

    def set_data(self, data):
        if not data:
            data = {}
        self._request_data = data

    def set_channel_action(self, channel_action):
        self._channel_action = channel_action

    def set_template_update(self, template_update):
        self._template_update = template_update

    def is_channel_action(self):
        return True if self._channel_action else False

    def set_src_channel_id(self, channel_id):
        self._src_channel_id = channel_id

    def get_src_channel_id(self):
        if self._src_channel_id:
            return self._src_channel_id
        return self._state.channel.id

    def set_publish_action(self, publish_action):
        self._publish_action = publish_action

    def get_publish_action(self):
        return self._publish_action

    def get_process_type(self):
        return self._process_type

    def set_process_type(self, _process_type):
        self._process_type = _process_type

    def set_channel_id(self, channel_id):
        self._channel_id = to_int(channel_id)

    def set_limit_process(self, limit):
        self._limit_process = limit

    def get_channel_id(self):
        if self._channel_id:
            return self._channel_id
        self._channel_id = to_int(self._state.channel.id)
        return self._channel_id

    def get_channel_url(self):
        if self._channel_url:
            return self._channel_url.strip('/')
        return self._state.channel.url.strip('/')

    def get_user_plan(self):
        if self._user_plan:
            return self._user_plan
        self._user_plan = self.get_model_sync_mode().get_user_plan()
        return self._user_plan

    def get_user_info(self):
        if self._user_info:
            return self._user_info
        self._user_info = self.get_model_sync_mode().get_user_info()
        return self._user_info

    def get_category_path(self, channel_type, type_search, params):
        return self.get_model_sync_mode().get_category_path(channel_type, type_search, params)

    def is_center_inventory_sync(self):
        user_info = self.get_user_info()
        return user_info and user_info.get('app_type') == 'cis'

    def is_multi_store_sync(self):
        user_info = self.get_user_info()
        return user_info and user_info.get('app_type') == 'mss'

    def get_model_catalog(self):
        if self._model_catalog:
            return self._model_catalog
        self._model_catalog = Catalog()
        self._model_catalog.set_user_id(self._user_id)
        self._model_catalog.set_db(self.get_db())
        return self._model_catalog

    def get_model_category(self):
        if self._model_category:
            return self._model_category
        self._model_category = Category()
        self._model_category.set_user_id(self._user_id)
        self._model_category.set_db(self.get_db())
        return self._model_category

    def get_model_template(self):
        if self._model_template:
            return self._model_template
        self._model_template = Template()
        self._model_template.set_user_id(self._user_id)
        self._model_template.set_db(self.get_db())
        return self._model_template

    def get_model_order(self):
        """

        :rtype: CollectionOrder
        """
        if self._model_order:
            return self._model_order
        self._model_order = CollectionOrder()
        self._model_order.set_user_id(self._user_id)
        self._model_order.set_db(self.get_db())
        return self._model_order

    def set_state_id(self, state_id):
        self._state_id = state_id
        self.get_model_state().set_document_id(state_id)

    def set_is_inventory_process(self, value):
        self._is_inventory_process = value

    def get_action_stop(self):
        return self._action_stop

    def set_action_stop(self, action_stop):
        self._action_stop = action_stop

    def get_state_id(self):
        return self._state_id

    def get_sync_id(self):
        return self._sync_id

    def get_db(self):
        if self._db:
            return self._db
        self._db = self.get_model_state().get_db()
        return self._db

    def set_db(self, db):
        if self._db:
            return
        self._db = db
        self.get_model_state().set_db(db)

    def set_sync_id(self, sync_id):
        self._sync_id = sync_id
        if self._state:
            self._state.sync_id = sync_id

    def set_product_id(self, product_id):
        self._product_id = product_id
        self.get_model_catalog().set_document_id(product_id)

    def set_name(self, name):
        self._name = name

    def set_channel_url(self, url):
        self._channel_url = url

    def set_channel_type(self, channel_type):
        self._type = channel_type

    def set_identifier(self, identifier):
        """

        :type identifier: unique for each channel
        """
        self._identifier = identifier
        self._state.channel.identifier = identifier

    def get_identifier(self):
        return self._identifier

    def set_id(self, _id):
        self._id = _id

    def set_user_id(self, user_id):
        self._user_id = user_id
        self._model_state.set_user_id(user_id)
        self.get_model_sync_mode().set_user_id(user_id)

    def set_date_requested(self, date_requested):
        self._date_requested = date_requested

    def set_is_update(self, _is_update):
        self._is_update = _is_update

    def get_model_state(self):
        return self._model_state

    def set_is_test(self, is_test=False):
        self._is_test = is_test

    def set_state(self, state):
        self._state = state
        self.get_model_sync_mode().set_state(state)

    def get_state(self):
        return self._state

    def get_state_by_id(self, state_id, sync_info=False):
        if state_id == 'litcommerce':
            state = SyncState()
            state.channel.id = self.get_channel_default_id()
            state.channel.channel_type = 'litcommerce'
            state.channel.default = True
            state.user_id = self._user_id
            return state
        state = self.get_model_state().get(state_id)
        if state:
            state = SyncState(**state)
            if not sync_info and state.sync_id:
                sync_info = self.get_sync_info(state.sync_id)

            if sync_info and sync_info.get('config') and json_decode(sync_info['config']):
                state.channel.config.api = json_decode(sync_info['config'])
                return state
            channel = self.get_channel_by_id(state.channel.id)
            if channel and json_decode(channel.api):
                state.channel.config.api = json_decode(channel.api)
            return state
        return False

    def save_state(self):
        self.get_model_state().set_data(self._state)
        return self.get_model_state().save()

    def save_pull_process(self, data=None):
        if self.is_product_process() and data and isinstance(data, dict) and data.get('condition'):
            return Response().success()
        return self.get_model_state().update_field(self._state_id, "pull", self._state.pull)

    def save_push_process(self, data=None):
        if self.is_product_process() and data and isinstance(data, dict) and data.get('condition'):
            return Response().success()
        return self.get_model_state().update_field(self._state_id, "push", self._state.push)

    def save_sync(self, **kwargs):
        # process = self.get_process_by_id(self._sync_id)
        # state_id = self.get_state_id() or process['state_id']
        # self.get_model_state().update_field(state_id,'process', kwargs)
        return True
        return self.get_model_sync_mode().save_sync(self._sync_id, **kwargs)

    def init_state(self):
        if self._sync_id:
            info = False
            if not self._state and not self._state_id:
                info = self.get_sync_info()
                if info:
                    self.set_process_type(info.type)
                    self.set_channel_id(info.channel_id)
                    self.set_limit_process(info.limit)
                if info and info.state_id:
                    if not self._user_id:
                        self.set_user_id(info.user_id)
                    self.set_state_id(info.state_id)
            if self._state_id:
                state = self.get_state_by_id(self._state_id, info)
                if state:
                    self._state = state
                    self.set_state_id(self._state_id)

        if not self._state:
            self._state = SyncState()
        return self._state

    def list_to_dict(self, list_data):
        if isinstance(list_data, dict):
            return list_data
        dict_data = dict()
        if not isinstance(list_data, list) or not list_data:
            return dict_data
        for index, value in enumerate(list_data):
            dict_data[str(index)] = value
        return dict_data

    def set_migration_id(self, migration_id):
        self._sync_id = migration_id

    def validate_data_setup(self, data):
        return Response().success()

    def get_channel(self, channel_type, channel_version):
        channel_file = None
        channel_class = None
        if not channel_type:
            return channel_file, channel_class
        if channel_type in self.all_cart():
            channel_file = 'channels.cart'
        elif channel_type == 'woocommerce':
            channel_file = 'channels.woo'
        else:
            channel_file = 'channels.{}'.format(channel_type)
        if channel_type == 'file':
            if self._is_inventory_process:
                channel_file = 'channels.files.inventory'
                channel_class = 'ModelChannelsInventoryFile'
            else:
                if self._state and self._state.channel.config.api.feed_type == 'update':
                    channel_class = 'ModelChannelsProductFileUpdate'
                    channel_file = 'channels.files.file_update'

                else:
                    channel_class = 'ModelChannelsProductFile'
        if channel_type == 'bulk_edit':
            channel_file = 'channels.files.bulk_edit'
            channel_class = 'ProductBulkEdit'
        if channel_type == 'etsy':
            channel_file = 'channels.etsyv3'
            channel_class = 'ModelChannelsEtsyV3'
        return channel_file, channel_class

    def all_cart(self):
        return ('3dcart',)

    def get_all_channels(self):
        if self._all_channel:
            return self._all_channel
        all_channels = self.get_model_sync_mode().get_all_channels()
        for channel in all_channels:
            self._all_channel[channel.id] = channel
        return self._all_channel

    def format_url(self, url, **kwargs):
        if not url:
            return ""
        if self.CONNECTOR_SUFFIX in url:
            url = url.replace(self.CONNECTOR_SUFFIX, '')
        filter_url = ['index.php', '?']
        for char in filter_url:
            find_char = url.find(char)
            if find_char >= 0:
                url = url[:find_char]
        url = url.rstrip('/')
        return url

    def channel_setup_type(self, channel_type):
        setup_type = {
            # api
            'shopify': 'api',
            'amazone': 'api',
            'ebay': 'api',

            'bigcommerce': 'cart',
            'magento': 'cart',
        }
        return setup_type[channel_type] if channel_type in setup_type else 'api'

    def get_msg_error(self, error_code):
        return self._error.get_msg_error(error_code)

    def get_url_suffix(self, suffix):
        url = self._channel_url.rstrip('/') + '/' + to_str(suffix).lstrip('/')
        return url

    def validate_channel_url(self):
        return Response().success()

    def channel_is_local_host(self):
        url = self._channel_url
        if not python_validators.url(url):
            return Response().error(Errors.URL_INVALID)
        localhost = ['localhost', 'localhost.com', '127.0.0.1',
                     '192.168.100.222', '192.168.100.222:8888']
        import urllib.parse
        scheme, netloc, path, qs, anchor = urllib.parse.urlsplit(url)
        if netloc in localhost or to_str(netloc).startswith('192.168'):
            return Response().error(Errors.URL_IS_LOCALHOST)
        return Response().success()

    def validate_setup_data(self, data):
        if not data.get('channel_name'):
            return Response().error(code=Errors.CHANNEL_NAME_REQUIRED)
        validate_channel_url = self.validate_channel_url()
        if validate_channel_url.result != Response.SUCCESS:
            return validate_channel_url
        return Response().success()

    def prepare_display_setup_channel(self, data=None):
        channel_type = self._state.channel.channel_type
        setup_type = self.channel_setup_type(channel_type)
        self._state.channel.setup_type = setup_type
        validate_setup_data = self.validate_setup_data(data)
        if validate_setup_data.result != Response().SUCCESS:
            code = Errors.SETUP_DATA_INVALID
            if validate_setup_data.code:
                code = validate_setup_data.code
            response = Response().error(code=code)
            return response
        if setup_type == 'connector':
            pass
        return Response().success()

    def display_setup_channel(self, data=None):
        configs = ('api', 'database')
        for config in configs:
            value = data.get(config, dict())
            if not value:
                value = dict()
            if value and isinstance(value, dict):
                value = Prodict(**value)
            if value:
                self._state.channel.config.set_attribute(config, value)
            method = 'validate_{}_info'.format(config)
            if hasattr(self, method):
                validate = getattr(self, method)()
                if validate.result != Response().SUCCESS:
                    return validate

        return Response().success()

    def update_custom_data(self, custom_data):
        self._custom_data = custom_data
        return Response().success()

    def set_channel_identifier(self):
        return Response().success()

    def get_api_info(self):
        return {}

    def validate_api_info(self):
        api_info = self.get_api_info()
        if api_info:
            for api_key, api_label in api_info.items():
                if not self._state.channel.config.api.get(api_key):
                    return Response().error(msg=Messages.API_FIELD_REQUIRED.format(api_label))
        return Response().success()

    def validate_database_info(self):
        return Response().success()

    def get_model_sync_mode(self):
        if self._model_sync_mode:
            self._model_sync_mode.set_state(self._state)
            return self._model_sync_mode
        server_mode = get_config_ini('local', 'mode')
        if not server_mode or self._is_test or (self._state and self._state.config.test):
            server_mode = 'test'

        model_name = 'modes.{}'.format(server_mode)
        model = get_model(model_name)
        if model:
            self._model_sync_mode = model
            self._model_sync_mode.set_state(self._state)
            self._model_sync_mode.set_sync_id(self._sync_id)
            self._model_sync_mode.set_user_id(self._user_id)
        return self._model_sync_mode

    def update_channel(self, **kwargs):
        return self.get_model_sync_mode().update_channel(self.get_channel_id(), **kwargs)

    def create_channel(self):
        channel_id = None
        sync_id = None
        state_id = None
        if self._sync_id:
            sync_id = self._sync_id
            sync_info = self.get_sync_info(sync_id)
            channel_id = sync_info.channel_id
            state_id = sync_info.state_id
        channel_id_exist = None
        if not channel_id:
            check = self.get_model_sync_mode().is_channel_exist(self._type, self._identifier)
            if check is True:
                return Response().error(code=Errors.CHANNEL_EXIST)
            if check:
                channel_id_exist = check['id']
            channel = self.get_model_sync_mode().create_channel(channel_id_exist)
            if channel.result != Response().SUCCESS:
                channel.code = Errors.CHANNEL_NOT_CREATE
                return channel
            channel_id = channel.data['id']
            self._state.channel.position = channel.data['position']
            if channel.data.get('default') == 1:
                self._state.channel.default = True
        self._state.channel.id = channel_id
        if not state_id:
            self._state.channel.created_at = get_current_time()
            state_id = self._model_state.create(self._state)
        if not state_id:
            return Response().error(code=Errors.STATE_NOT_CREATE)
        if not sync_id:
            process_data = {
                'state_id': state_id,
                'channel_id_exist': channel_id_exist
            }
            if self.is_file_channel():
                process_data['config'] = json_encode(
                    self._state.channel.config.api)
                process_data['feed_type'] = 'add'
            sync = self.get_model_sync_mode().create_product_sync_process(**process_data)
            if sync.result != Response().SUCCESS:
                self.delete_channel(channel_id)
                sync.code = Errors.PROCESS_NOT_CREATE
                return sync
            sync_id = sync.data
        else:
            self.get_model_sync_mode().set_state_id_for_sync(sync_id, state_id)
        inventories = self.get_model_sync_mode().get_warehouse_locations()
        location_ids = duplicate_field_value_from_list(inventories, 'id')
        self._state.sync_id = sync_id
        self._state.channel.config.setting.inventory = {
            'active': location_ids, 'disable': []}
        self.init_index(channel_id)
        data = {
            'channel_id': channel_id,
            'process_id': sync_id,
            'state_id': state_id
        }
        # if self._state.channel.default and self.is_shopping_cart():
        # 	self.create_refresh_process_scheduler()
        print("data", data)
        return Response().success(data)

    def is_shopping_cart(self):
        return self.get_channel_type() in ['woocommerce', 'shopify', 'wix', 'bigcommerce', 'magento', 'squarespaces']

    def init_index(self, channel_id):
        field_index = ['status', 'product_id', 'name', 'sku']
        if self.INIT_INDEX_FIELDS:
            field_index.extend(self.INIT_INDEX_FIELDS)
        for field in field_index:
            self.get_model_catalog().create_index(
                f"channel.channel_{channel_id}.{field}")
        self.get_model_catalog().create_compound_index(
            [f"channel.channel_{channel_id}.status", 'is_variant', 'parent_id'])

        if self.is_channel_default():
            self.get_model_order().create_index('channel_id')
            self.get_model_template().create_index('channel_id')
            self.get_model_state().create_index('channel_id')
            self.get_model_order().create_index("status")
            field_index = ['is_variant', 'name',
                           'sku', 'is_in_stock', 'parent_id']
            for field in field_index:
                self.get_model_catalog().create_index(field)

    def init_catalog_text_index(self, channel_id):
        index_key = 'catalog_text_index'
        channel_field = [
            f'channel.channel_{channel_id}.sku', f'channel.channel_{channel_id}.name']
        default_field = ['name', 'sku']
        if self.is_channel_default():
            self.get_model_catalog().create_text_index(
                ['name', 'sku'], index_key)
        else:
            text_index = self.get_model_catalog().get_index(index_key)
            fields = default_field + channel_field

            if text_index:
                fields += list(dict(text_index['weights']).keys())
            fields = list(set(fields))
            self.get_model_catalog().drop_index(index_key)
            self.get_model_catalog().create_text_index(fields, index_key)

    # def init_catalog_text_index(self, channel_id):
    # 	index_key = 'catalog_text_index'
    # 	channel_field = [f'channel.channel_{channel_id}.sku', f'channel.channel_{channel_id}.name']
    # 	default_field = ['name', 'sku']
    # 	if self.is_channel_default():
    # 		self.get_model_catalog().create_text_index(['name', 'sku'], index_key)
    # 	else:
    # 		text_index = self.get_model_catalog().get_index(index_key)
    # 		fields = default_field + channel_field
    #
    # 		if text_index:
    # 			fields += list(dict(text_index['weights']).keys())
    # 		fields = list(set(fields))
    # 		self.get_model_catalog().drop_index(index_key)
    # 		self.get_model_catalog().create_text_index(fields, index_key)

    def delete_channel(self, channel_id):
        return self.get_model_sync_mode().delete_channel(channel_id)

    def get_channel_default(self):
        if self._request_data.get('channels'):
            for channel_id, channel_data in self._request_data['channels'].items():
                if channel_data['default']:
                    return Prodict.from_dict(channel_data)
        return self.get_model_sync_mode().get_channel_default()

    def get_channel_default_id(self):
        if self._channel_default_id:
            return self._channel_default_id
        channel_default = self.get_channel_default()
        self._channel_default_id = channel_default['id']
        return self._channel_default_id

    def delete_sync_process(self, sync_id):
        return self.get_model_sync_mode().delete_sync_process(sync_id)

    def after_create_channel(self, data):
        return Response().success()

    def combine_request_options(self, custom_options=None):
        options = {
            'verify': False,
            'allow_redirects': True,
            'timeout': 30
        }
        if not custom_options:
            return options
        for option_key, option_value in custom_options.items():
            options[option_key] = option_value
        return options

    def no_clear(self):
        return Response().success()

    def log(self, msg, log_type='exceptions'):
        prefix = "user/" + to_str(self._user_id)
        if self._channel_id:
            prefix = os.path.join('channel', to_str(self._channel_id))
            if self._process_type:
                prefix += '/' + self._process_type
        elif self._sync_id:
            prefix = os.path.join('processes', to_str(self._sync_id))
        elif self._product_id:
            prefix = os.path.join(prefix, 'product', to_str(self._product_id))

        log(msg, prefix, log_type)

    def log_request_error(self, url, log_type='request', **kwargs):
        msg_log = 'Url: ' + to_str(url)
        for log_key, log_value in kwargs.items():
            msg_log += '\n{}: {}'.format(to_str(log_key).capitalize(),
                                         to_str(log_value))
        self.log(msg_log, log_type)

    def log_traceback(self, type_error='exceptions', msg=''):
        error = traceback.format_exc()
        if msg:
            error += "\n" + msg
        self.log(error, type_error)

    def notify(self, code, data=None):
        pass

    def get_entity_limit(self):
        return {
            'products': self._limit_process,
            'orders': self._limit_process,
        }

    def get_sync_info(self, sync_id=None):
        if not sync_id:
            sync_id = self._sync_id
        if self._request_data.get('processes') and self._request_data['processes'].get(to_str(sync_id)):
            return Prodict.from_dict(self._request_data['processes'].get(to_str(sync_id)))
        return self.get_model_sync_mode().get_sync_info(sync_id)

    # Todo: display pull

    def prepare_display_pull(self, data=None):
        self._state.pull.process.products.auto_build = True
        self._state.pull.process.products.auto_import_category = False
        if isinstance(data, dict):
            if data.get('include_deleted'):
                self._state.pull.process.products = EntityProcess()
            if 'auto_build' in data:
                self._state.pull.process.products.auto_build = to_bool(
                    data.get('auto_build'))
            self._state.pull.process.products.auto_import_category = to_bool(
                data.get('auto_import_category'))
            self._state.pull.process.products.include_inactive = to_bool(
                data.get('include_inactive'))
        entities = ('taxes', 'categories', 'products', 'orders')
        if get_config_ini('local', 'mode') != 'live':
            limits = dict()
            for entity in entities:
                limits[entity] = get_config_ini(
                    'limit', entity, '-1', file='local.ini')
                self._state.config[entity] = to_bool(
                    get_config_ini('config', entity, False, file='local.ini'))
        else:
            limits = self.get_entity_limit()
            if self.is_order_process():
                self._state.config.orders = self._state.channel.support.orders
                self._state.config.taxes = False
                self._state.config.categories = False
                self._state.config.products = False
            elif self.is_category_process():
                self._state.config.orders = False
                self._state.config.taxes = False
                self._state.config.categories = True
                self._state.config.products = False
            else:
                self._state.config.orders = False
                self._state.config.taxes = False
                self._state.config.categories = False
                self._state.config.products = True
        for entity in entities:
            if limits.get(entity):
                self._state.pull.process[entity].limit = limits[entity]
        return Response().success()

    def is_auto_build(self):
        return self._state.pull.process.products.auto_build

    def is_auto_import_category(self):
        return True
        return self._state.pull.process.products.auto_build

    def display_pull_channel(self):
        return Response().success()

    def display_pull_warehouse(self):
        return Response().success()

    def display_pull(self):
        return Response().success()

    # Todo: Prepare pull

    def prepare_pull_channel(self, data=None):
        return Response().success()

    def prepare_pull(self):
        return Response().success()

    # TODO taxes

    def prepare_taxes_import(self):
        return self

    def prepare_taxes_export(self):
        return self

    def get_taxes_main_export(self):
        return Response().success()

    def get_taxes_ext_export(self, taxes):
        return Response().success()

    def convert_tax_export(self, tax, taxes_ext):
        return Response().success()

    def get_tax_id_import(self, convert, tax, taxes_ext):
        return convert['id']

    def check_tax_import(self, tax_id, convert: Product):
        return False

    def before_tax_import(self, convert, tax, taxes_ext):
        return Response().success()

    def tax_import(self, convert, tax, taxes_ext):
        return response_success(0)

    def tax_channel_import(self, convert, tax, taxes_ext):
        return self.tax_import(convert, tax, taxes_ext)

    def after_tax_import(self, tax_id, convert, tax, taxes_ext):
        return Response().success()

    def after_tax_pull(self, tax_id, convert, tax, taxes_ext):
        return Response().success()

    def addition_tax_import(self, convert, tax, taxes_ext):
        return Response().success()

    def finish_tax_import(self):
        return Response().success()

    # TODO: categories

    def prepare_categories_import(self):
        return self

    def prepare_categories_export(self):
        return self

    def get_categories_main_export(self):
        return Response().success()

    def get_categories_ext_export(self, categories):
        return Response().success()

    def convert_category_export(self, category, categories_ext):
        return Response().success()

    def add_channel_to_convert_tax_data(self, tax, category_channel_id):
        # channel = Tax()
        # channel.category_id = category_channel_id
        # channel.channel_id = self._state.channel.id
        # category.channel.set_attribute("channel_{}".format(self._state.channel.id), channel.to_dict())
        return tax

    def add_channel_to_convert_category_data(self, category: CatalogCategory, category_channel_id):
        channel = CategoryChannel()
        channel.category_id = to_str(category_channel_id)
        channel.channel_id = self._state.channel.id
        if not category.channel:
            category.channel = dict()
        category['channel'][f'channel_{self.get_channel_id()}'] = channel
        return category

    def get_category_total_import(self):
        return 0

    def get_category_id_import(self, convert: CatalogCategory, category, categories_ext):
        return False

    def check_category_import(self, category_id, convert: CatalogCategory):
        return False

    def before_category_import(self, convert: Product, category, categories_ext):
        return Response().success()

    def category_import(self, convert: CatalogCategory, category, categories_ext):
        return Response().success()

    def category_channel_import(self, convert: CatalogCategory, category, categories_ext):
        return self.category_import(convert, category, categories_ext)

    def edit_category_channel(self, category: Product, data):
        return Response().success()

    def update_category(self, data):
        channel_id = self._state.channel.id
        update_data = dict()
        for data_key, data_value in data.items():
            update_data['channel.channel_{}.{}'.format(
                channel_id, data_key)] = data_value
        return Response().success(update_data)

    def get_category_channel_data(self, category, category_channel_id):
        category_channel = CategoryChannel()
        category_channel.channel_id = self._state.channel.id
        category_channel.category_id = category_channel_id
        category_channel.category_code = category.code
        return category_channel

    def insert_map_category(self, category, category_id, category_channel_id):
        map_field = "channel_{}".format(self._state.channel.id)
        category_channel_data = self.get_category_channel_data(
            category, category_channel_id)
        category.channel.set_attribute(map_field, category_channel_data)
        update_field = "channel.{}".format(map_field)
        self.get_model_catalog().update_field(
            category_id, update_field, category_channel_data)
        return Response().success()

    def after_category_import(self, category_id, convert: CatalogCategory, category, categories_ext):
        return Response().success()

    def after_category_pull(self, category_id, convert: CatalogCategory, category, categories_ext):
        return Response().success()

    def addition_category_import(self):
        return Response().success()

    def finish_category_import(self):
        return Response().success()

    def filter_field_category(self, data):
        filter_data = dict()
        fields = Catalog.FILTER
        for data_key, data_value in data.items():
            if data_key in fields:
                filter_data[data_key] = data_value
        if filter_data.get('price') and self._state.channel.config.price_sync.status == StateChannelConfigPriceSync.DISABLE:
            del filter_data['price']
        if filter_data.get('qty') and self._state.channel.config.qty_sync.status == StateChannelConfigQtySync.DISABLE:
            del filter_data['qty']
        return filter_data

    # TODO products

    def prepare_products_import(self, data=None):
        return self

    def prepare_products_export(self):
        return self

    def get_product_main_export(self, product_id):
        product_channel_id = product_id
        product = self.get_model_catalog().get(product_id, ['channel'])
        field_check = 'channel_{}'.format(self._state.channel.id)
        if not product or not product['channel'].get(field_check):
            return Response().finish()
        product_channel_id = product['channel'][field_check].get('product_id')

        product_channel = self.get_product_by_id(product_channel_id)
        # if product_channel.result != Response.SUCCESS:
        # 	return product_channel
        return product_channel

    def get_product_by_id(self, product_id):
        return Response().success()

    def get_products_main_export(self):
        return Response().success()

    def get_product_by_updated_at(self):
        return Response().success()

    def get_products_ext_export(self, products):
        return Response().success()

    def convert_product_export(self, product, products_ext):
        # if self.is_refresh_process():
        # 	self.set_product_max_last_modified(product)
        return self._convert_product_export(product, products_ext)

    def _convert_product_export(self, product, products_ext):
        return Response().success()

    def get_product_updated_at(self, product):
        return product.updated_at

    def updated_at_to_timestamp(self, updated_at, time_format='%Y-%m-%d %H:%M:%S'):
        return to_timestamp(updated_at, time_format)

    def set_product_max_last_modified(self, product):
        updated_at = self.get_product_updated_at(product)
        if not self._product_max_last_modified:
            self._product_max_last_modified = updated_at
            return
        old_timestamp = self.updated_at_to_timestamp(
            self._product_max_last_modified)
        new_timestamp = self.updated_at_to_timestamp(updated_at)
        if new_timestamp > old_timestamp:
            self._product_max_last_modified = updated_at

    def add_channel_to_convert_product_data(self, product, product_channel_id):
        channel = ProductChannel()
        channel.product_id = to_str(product_channel_id)
        unescape = ['name', 'sku', 'description',
                    'short_description', 'meta_title', 'meta_keyword']
        for row in unescape:
            product[row] = html_unescape(product.get(row)).strip(' ')
        channel.sku = product.sku
        channel.name = product.name
        channel.channel_id = self._state.channel.id
        channel.qty = to_int(product.qty)
        channel.price = product.price
        if self.is_channel_default():
            channel.link_status = ProductChannel.LINKED
        else:
            if self.is_center_inventory_sync() and self.is_auto_build():
                channel_default = ProductChannel()
                channel_default.channel_id = self.get_channel_default_id()
                channel_default.product_id = product.get('id')
                channel_default.link_status = ProductChannel.LINKED
                product.channel.set_attribute("channel_{}".format(
                    self.get_channel_default_id()), channel_default.to_dict())
                channel.link_status = ProductChannel.LINKED

        if product.template_data:
            channel.template_data = copy.deepcopy(product.template_data)
            del product['template_data']
        if product.channel_data:
            channel.update(product.channel_data)
        # del product['channel_data']
        # product.channel.append(channel)
        product.channel.set_attribute("channel_{}".format(
            self._state.channel.id), channel.to_dict())
        product.src.channel_type = self._state.channel.channel_type
        product.src.channel_id = to_int(self._state.channel.id)
        if product.variants:
            for variant in product.variants:
                variant_channel = ProductChannel()
                for row in unescape:
                    variant[row] = html_unescape(variant.get(row))
                variant_channel.qty = variant.qty
                variant_channel.name = variant.name
                variant_channel.sku = variant.sku
                variant_channel.product_id = to_str(variant.id)
                variant_channel.code = variant.code
                if variant.template_data:
                    variant_channel.template_data = copy.deepcopy(
                        variant.template_data)
                    del variant['template_data']
                if variant.channel_data:
                    variant_channel.update(variant.channel_data)
                    del variant['channel_data']
                if self.is_channel_default():
                    variant_channel.link_status = ProductChannel.LINKED
                else:
                    if self.is_center_inventory_sync() and self.is_auto_build():
                        variant_channel_default = ProductChannel()
                        variant_channel_default.channel_id = self.get_channel_default_id()
                        variant_channel_default.product_id = variant.get('id')
                        variant_channel_default.link_status = ProductChannel.LINKED
                        variant.channel.set_attribute("channel_{}".format(
                            self.get_channel_default_id()), variant_channel_default.to_dict())
                        variant_channel.link_status = ProductChannel.LINKED
                variant.channel.set_attribute("channel_{}".format(
                    self._state.channel.id), variant_channel.to_dict())

        return product

    def get_product_id_import(self, convert: Product, product, products_ext):
        return convert['id']

    def check_tax_available_import(self, notify=False):
        return True

    def check_category_available_import(self, notify=False):
        return True

    # TODO: product

    def get_product_total_import(self):
        all_channel = self.get_all_channels()
        channel_filter = list()
        for channel_id, channel in all_channel.items():
            if channel.get('default') or channel.get('type') in ['file', 'bulk_edit']:
                continue
            channel_filter.append(channel)
        total = 0
        for channel in channel_filter:
            where = self.get_model_catalog().create_where_condition("is_variant", False)
            where.update(self.get_model_catalog().create_where_condition(
                f"channel.channel_{channel['id']}.status", '', '>'))
            total += self.get_model_catalog().count(where)
        return total

    def check_product_available_import(self, notify=False, push=False):
        if self._product_available_import is False:
            return False
        if get_config_ini('local', 'mode') != 'live' or self.is_staff_user():
            return True
        if not self.check_product_rate_limit(push):
            user_plan = self.get_user_plan()
            if not user_plan or to_int(user_plan['monthly_fee']) == 0:
                # email
                self.count_number_products()

                self._product_available_import = False
                self.notify_limit_product(notify)
                return False
            upgrade = self.try_upgrade_plan()
            if not upgrade or to_int(upgrade['code']) != 200:
                self._product_available_import = False
                self.notify_limit_product(notify)
                self.count_number_products()

                return False
            self._user_plan = upgrade['data']
        return True

    def try_upgrade_plan(self):
        return self.get_model_sync_mode().try_upgrade_plan()

    def check_product_rate_limit(self, push=False):
        if get_config_ini('local', 'mode') != 'live':
            return True
        user_plan = self.get_user_plan()
        if not user_plan:
            return False
        if to_int(user_plan['products_limit']) == 0:
            return True
        products_limit = to_int(
            user_plan['products_limit']) if not user_plan.get('expired') else 20
        if not self._total_product or self._total_product_batch_import >= 25:
            # 	self._total_product += 1
            # 	self._total_product_batch_import += 1
            # else:
            total_import = self.get_product_total_import()
            self._total_product = total_import
            self._total_product_batch_import = 0
        return to_int(self._total_product) < products_limit

    def notify_limit_product(self, notify=False):
        if not notify:
            return
        notification_data = {
            'code': '',
            'content': Messages.PRODUCT_RATE_LIMIT_TITLE,
            'activity_type': 'product_rate_limit',
            'description': Messages.PRODUCT_RATE_LIMIT_DESCRIPTION,
            'date_requested': self._date_requested,
            'result': Activity.FAILURE
        }
        notification = self.create_activity_notification(**notification_data)

    def notify_limit_order(self, notify=False):
        if not notify:
            return
        notification_data = {
            'code': '',
            'content': Messages.ORDER_RATE_LIMIT_TITLE,
            'activity_type': 'order_rate_limit',
            'description': Messages.PRODUCT_RATE_LIMIT_DESCRIPTION,
            'date_requested': self._date_requested,
            'result': Activity.FAILURE
        }
        notification = self.create_activity_notification(**notification_data)

    def check_product_import(self, product_id, convert: Product):
        catalog = self.get_product_map(product_id)
        if catalog:
            return catalog
        return False

    def before_product_import(self, convert: Product, product, products_ext):
        return Response().success()

    def product_import(self, convert: Product, product, products_ext):
        return Response().success()

    def product_channel_import(self, convert: Product, product, products_ext):
        # if self.is_channel_default():
        # 	if not self.check_product_available_import(push = True):
        # 		return Response().stop(code = Errors.PRODUCT_RATE_LIMIT)
        return self.product_import(convert, product, products_ext)

    def product_update(self, product_id, convert: Product, product, products_ext):
        return self.product_channel_update(product_id, convert, products_ext)

    def product_channel_update(self, product_id, product: Product, products_ext):
        return Response().success()

    def edit_product_channel(self, product: Product, data):
        return Response().success()

    def update_product(self, data):
        channel_id = self._state.channel.id
        update_data = dict()
        for data_key, data_value in data.items():
            update_data['channel.channel_{}.{}'.format(
                channel_id, data_key)] = data_value
        return Response().success(update_data)

    def get_product_channel_data(self, product: Product, product_channel_id, channel_id=None):
        if not channel_id:
            channel_id = self._state.channel.id
        map_field = f"channel_{channel_id}"
        if product.channel.get(map_field):
            product_channel = product.channel.get(map_field)
        else:
            product_channel = ProductChannel()
        if not product_channel.channel_id:
            product_channel.channel_id = channel_id
        if product_channel_id and not product_channel.product_id:
            product_channel.product_id = to_str(product_channel_id)
        product_channel.sku = product.sku
        product_channel.name = product.name
        return product_channel

    def extend_data_insert_map_product(self):
        if not self._extend_product_map:
            return {}
        extend = copy.deepcopy(self._extend_product_map)
        self._extend_product_map = {}
        return extend

    def insert_map_product(self, product, product_id, product_channel_id):
        map_field = "channel_{}".format(self.get_channel_id())
        extend_data = self.extend_data_insert_map_product()
        if self.is_channel_default() and product.channel.get(map_field) and product.channel.get(map_field).status == ProductChannel.ACTIVE and product.channel.get(map_field).product_id:
            product_clone = copy.deepcopy(product)
            product_clone.channel[map_field]['product_id'] = to_str(
                product_channel_id)
            product_clone.channel[f"channel_{self.get_src_channel_id()}"]['link_status'] = ProductChannel.LINKED
            if extend_data:
                product_clone.channel[map_field].update(extend_data)
            del product_clone['_id']
            if product.is_variant:
                product_clone.clone_parent_id = product_clone.parent_id
                product_clone.hidden = True
            product_clone_id = self.get_model_catalog().create(product_clone)
            self.get_model_catalog().update(
                product_id, {f'channel.channel_{self.get_src_channel_id()}': {}})
            if not product.is_variant and product.variants:
                where_update = self.get_model_catalog().create_where_condition(
                    'clone_parent_id', product['_id'])
                self.get_model_catalog().update_many(
                    where_update, {'parent_id': product_clone_id, 'hidden': False})
            return Response().success()
        product_channel_data = self.get_product_channel_data(
            product, product_channel_id)
        if product_channel_id:
            product_channel_data.status = ProductChannel.ACTIVE
            product_channel_data.link_status = ProductChannel.LINKED
        else:
            product_channel_data.publish_status = ProductChannel.PUSHING
            product_channel_data.status = ProductChannel.DRAFT
        product.channel.set_attribute(map_field, product_channel_data)
        if extend_data:
            product_channel_data.update(extend_data)
        update_field = "channel.{}".format(map_field)
        update_data = {
            update_field: product_channel_data
        }
        if self.is_channel_default() and self.get_src_channel_id() != self.get_channel_id():
            update_data[f"channel.channel_{self.get_src_channel_id()}.link_status"] = ProductChannel.LINKED
        self.get_model_catalog().update(product_id, update_data)
        return Response().success()

    def update_map_product(self, product, product_id, product_channel_id):
        self.get_model_catalog().update_field(product_id,
                                              f"channel.channel_{self.get_channel_id()}.product_id", to_str(product_channel_id))

    def after_product_import(self, product_id, convert: Product, product, products_ext):
        return Response().success()

    def delete_product_import(self, product_id):
        return Response().success()

    def after_product_pull(self, product_id, convert: Product, product, products_ext):
        return Response().success()

    def addition_product_import(self):
        return Response().success()

    def finish_product_import(self):
        return Response().success()

    def finish_product_export(self):
        self._state.pull.process.products.finished = True
        if self.is_refresh_process() and self._product_max_last_modified:
            self._state.pull.process.products.last_modified = self._product_max_last_modified

    def after_product_update(self, product_id, product: Product):
        return Response().success()

    def filter_field_product(self, data):
        filter_data = dict()
        fields = Catalog.FILTER
        for data_key, data_value in data.items():
            if data_key in fields:
                filter_data[data_key] = data_value
        if filter_data.get('price') and self._state.channel.config.price_sync.status == StateChannelConfigPriceSync.DISABLE:
            del filter_data['price']
        if filter_data.get('qty') and self._state.channel.config.qty_sync.status == StateChannelConfigQtySync.DISABLE:
            del filter_data['qty']
        return filter_data

    # TODO: orders

    def get_order_total_import(self):
        if get_config_ini('local', 'mode') != 'live':
            return 0
        user_plan = self.get_user_plan()
        current_time = datetime.now()
        started_at = datetime.strptime(
            user_plan['started_at'], get_default_format_date())
        difference_month = diff_month(current_time, started_at)
        if difference_month > 0:
            started_at += relativedelta.relativedelta(months=difference_month)
            if started_at.day > current_time.day:
                started_at -= relativedelta.relativedelta(months=1)

        where = self.get_model_catalog().create_where_condition(
            "imported_at", started_at.strftime(get_default_format_date()), ">=")
        return self.get_model_catalog().count(where)

    def prepare_orders_import(self):
        return self

    def prepare_orders_export(self):
        return self

    def get_order_main_export(self, order_id):
        order = self.get_model_order().get(order_id, ['channel'])
        field_check = 'channel_{}'.format(self.get_channel_id())
        if not order or not order['channel'].get(field_check):
            return Response().finish()
        order_channel_id = order['channel'][field_check].get('order_id')

        order_channel = self.get_order_by_id(order_channel_id)
        if order_channel.result != Response.SUCCESS:
            return Response().finish()
        return order_channel

    def get_orders_main_export(self):
        return Response().success()

    def get_order_by_id(self, order_id):
        return Response().success()

    def get_orders_ext_export(self, orders):
        return Response().success()

    def convert_order_export(self, order, orders_ext, channel_id=None):
        return Response().success(order)

    def add_channel_to_convert_order_data(self, order: Order, order_channel_id):
        channel = OrderChannel()
        channel.order_id = to_str(order_channel_id)
        channel.order_number = to_str(order.channel_order_number)
        if order.channel_data:
            channel.update(order.channel_data)
            del order['channel_data']
        channel.channel_id = self.get_channel_id()
        channel.channel_type = self.get_channel_type()

        order.channel.set_attribute("channel_{}".format(
            self._state.channel.id), channel.to_dict())
        return order

    def get_order_id_import(self, convert: Order, order, orders_ext):
        return False

    def check_order_import(self, order_id, convert: Order):
        return False

    def before_order_import(self, convert: Product, order, orders_ext):
        return Response().success()

    def order_import(self, convert: Order, order, orders_ext):
        return Response().success()

    def order_channel_import(self, convert: Order, order, orders_ext):
        # if not self.check_order_available_import():
        # 	return Response().stop(code = Errors.ORDER_RATE_LIMIT)
        return self.order_import(convert, order, orders_ext)

    def edit_order_channel(self, order: Product, data):
        return Response().success()

    def update_order(self, data):
        channel_id = self._state.channel.id
        update_data = dict()
        for data_key, data_value in data.items():
            update_data['channel.channel_{}.{}'.format(
                channel_id, data_key)] = data_value
        return Response().success(update_data)

    def get_order_channel_data(self, order, order_channel_id):
        order_channel = OrderChannel()
        order_channel.channel_id = self._state.channel.id
        order_channel.order_id = order_channel_id
        order_channel.order_code = order.code
        return order_channel

    def insert_map_order(self, order, order_id, order_channel_id):
        map_field = "channel_{}".format(self._state.channel.id)
        order_channel_data = self.get_order_channel_data(
            order, order_channel_id)
        order.channel.set_attribute(map_field, order_channel_data)
        update_field = "channel.{}".format(map_field)
        self.get_model_catalog().update_field(order_id, update_field, order_channel_data)
        return Response().success()

    def after_order_import(self, order_id, convert: Order, order, orders_ext):
        return Response().success()

    def order_sync_inventory(self, order: Order, setting_order):
        return Response().success()

    def channel_order_sync_inventory(self, order: Order, setting_order):
        if order.sync_inventory:
            return Response().success()
        sync = self.order_sync_inventory(order, setting_order)
        update_data = {
            'setting_order': setting_order
        }
        if sync.result == Response.SUCCESS:
            update_data['sync_inventory'] = True
        self.get_model_order().update(order['_id'], update_data)
        return sync

    def update_order_to_channel(self, order: Order, current_order):
        channel_id = self.get_channel_id()
        if not order.channel.get(f'channel_{channel_id}', dict()).get('order_id'):
            return Response().success()
        channel_update = self.order_channel_update(
            order.channel[f'channel_{channel_id}']['order_id'], order, current_order)
        if channel_update.result != Response.SUCCESS:
            return channel_update
        if channel_update.data and channel_update.data.status:
            self.get_model_order().update_field(
                order['_id'], f'channel.channel_{channel_id}.order_status', channel_update.data.status)
        return channel_update

    def order_channel_update(self, order_id, order: Order, current_order):
        if current_order.status != order.status:
            order_status = order.status
            if hasattr(self, f"channel_order_{order_status}"):
                return getattr(self, f"channel_order_{order_status}")(order_id, order, current_order)
        return Response().success()

    def check_order_available_import(self, notify=False):
        return True
        if self._order_available_import is False:
            return False
        if get_config_ini('local', 'mode') != 'live' or self.is_staff_user():
            return True
        if not self.check_order_rate_limit():
            user_plan = self.get_user_plan()
            if not user_plan or to_int(user_plan['monthly_fee']) == 0:
                # email
                return Response().create_response('stop')
            upgrade = self.try_upgrade_plan()
            if not upgrade or to_int(upgrade['code']) != 200:
                self._order_available_import = False
                self.notify_limit_order(notify)
                return Response().create_response('stop')
            self._user_plan = upgrade['data']
        return True

    def check_order_rate_limit(self):
        if get_config_ini('local', 'mode') != 'live':
            return True
        user_plan = self.get_user_plan()
        if not user_plan:
            return False
        if to_int(user_plan['orders_limit']) == 0:
            return True
        total_import = self.get_order_total_import()
        return to_int(total_import) < to_int(user_plan['products_limit'])

    def delete_order_import(self, order_id):
        return Response().success()

    def after_order_pull(self, order_id, convert: Order, order, orders_ext):
        return Response().success()

    def addition_order_import(self):
        return Response().success()

    def finish_order_import(self):
        return Response().success()

    def finish_order_export(self):
        if self._order_max_last_modified:
            self._state.pull.process.orders.max_last_modified = self._order_max_last_modified

    def after_order_update(self, channel_order_id, order_id, order: Order, current_order=None, setting_order=True):
        if not current_order:
            current_order = self.get_model_order().get(order_id)
        if not current_order:
            return Response().success()
        if current_order.status != order.status:
            order_status = order.status
            if hasattr(self, f"order_{order_status}"):
                return getattr(self, f"order_{order_status}")(channel_order_id, order_id, order, current_order, setting_order)
        # return self.order_canceled(channel_order_id, order_id, order, current_order)
        return Response().success()

    def order_canceled(self, channel_order_id, order_id, order: Order, current_order: Order, setting_order=True):
        return Response().success()

    def filter_field_order(self, data):
        filter_data = dict()
        fields = Catalog.FILTER
        for data_key, data_value in data.items():
            if data_key in fields:
                filter_data[data_key] = data_value
        if filter_data.get('price') and self._state.channel.config.price_sync.status == StateChannelConfigPriceSync.DISABLE:
            del filter_data['price']
        if filter_data.get('qty') and self._state.channel.config.qty_sync.status == StateChannelConfigQtySync.DISABLE:
            del filter_data['qty']
        return filter_data

    # TODO: PUSH

    def prepare_display_push(self):
        entities = ('taxes', 'categories', 'products', 'orders')
        if get_config_ini('local', 'mode') != 'live':
            limits = dict()
            for entity in entities:
                limits[entity] = get_config_ini(
                    'limit', entity, '-1', file='local.ini')
                self._state.config[entity] = get_config_ini(
                    'config', entity, False, file='local.ini')
        else:
            limits = self.get_entity_limit()
            if self.is_order_process():
                self._state.config.orders = self._state.channel.support.orders
                self._state.config.taxes = False
                self._state.config.categories = False
                self._state.config.products = False
            elif self.is_inventory_process():
                self._state.config.orders = False
                self._state.config.taxes = False
                self._state.config.categories = False
                self._state.config.products = True

            else:
                self._state.config.orders = False
                self._state.config.taxes = False
                self._state.config.categories = False
                self._state.config.products = self._state.channel.support.products
        for entity in entities:
            if limits.get(entity):
                self._state.push.process[entity].limit = limits[entity]
        # entity_config = get_config_ini('config', entity, -1, file = 'local.ini')
        # if entity_config != -1:
        # 	self._state.config.set_attribute(entity, to_bool(entity_config))
        return Response().success()

    def display_push_channel(self, data=None):
        return Response().success()

    def display_push(self):
        return Response().success()

    def prepare_push_channel(self):
        return Response().success()

    def prepare_push(self):
        return Response().success()

    def after_push_product(self, product_id, import_data, product: Product):
        if self.is_inventory_process() or self._template_update:
            return Response().success(product)

        if self._state.channel.channel_type not in self.channel_no_after_push():
            update_field = dict()
            if import_data.result in (Response.ERROR, Response.WARNING):
                publish_status = ProductChannel.ERRORS
                if import_data.code and import_data.msg:
                    msg = Errors().get_msg_error(import_data.code) + ": " + \
                        f"{self.replace_msg(import_data.msg)}"
                elif import_data.code:
                    msg = Errors().get_msg_error(import_data.code)
                elif import_data.msg:
                    msg = import_data.msg
                else:
                    msg = Errors().get_msg_error(Errors.EXCEPTION_IMPORT)

                status = ProductChannel.ERRORS
            else:
                msg = ''
                publish_status = ProductChannel.COMPLETED
                status = ProductChannel.ACTIVE
                update_field[f'channel.channel_{self.get_channel_id()}.price'] = product.price
                qty = product.qty
                if product.variants:
                    qty = 0
                    for variant in product.variants:
                        variant_update = dict()
                        qty += to_int(variant.qty)
                        for row in ['qty', 'price']:
                            if variant[row] != variant['channel'][f'channel_{self.get_channel_id()}'].get(row):
                                variant_update[f"channel.channel_{self.get_channel_id()}.{row}"] = variant.get(
                                    row)
                        if variant_update:
                            self.get_model_catalog().update(
                                variant['_id'], variant_update)
                update_field[f'channel.channel_{self.get_channel_id()}.qty'] = qty

            src_channel_key = f"channel_{self.get_src_channel_id()}"
            channel_key = f"channel_{self._state.channel.id}"
            update_field[f"channel.{src_channel_key}.publish_status"] = publish_status
            update_field[f"channel.{src_channel_key}.publish_action"] = None
            update_field[f"channel.{src_channel_key}.error_message"] = msg
            product['channel'][src_channel_key] = self.get_product_channel_data(
                product, '', channel_id=self.get_src_channel_id())
            product['channel'][src_channel_key]['publish_status'] = publish_status
            product['channel'][src_channel_key]['error_message'] = msg
            product['channel'][src_channel_key]['publish_action'] = None
            if self.is_channel_default():
                product_channel = self.get_product_channel_data(product, '')
                if product_channel.get('status') != 'active':
                    update_field[f"channel.{channel_key}.status"] = status
                    update_field[f"channel.{channel_key}.publish_status"] = publish_status
                    update_field[f"channel.{channel_key}.publish_action"] = None
                    update_field[f"channel.{channel_key}.error_message"] = msg
                    product['channel'][channel_key] = self.get_product_channel_data(
                        product, '')
                    product['channel'][channel_key]['publish_status'] = publish_status
                    product['channel'][channel_key]['error_message'] = msg
                    product['channel'][channel_key]['publish_action'] = None
                    product['channel'][channel_key]['status'] = status
            else:
                update_field[f"channel.{src_channel_key}.status"] = status
                product['channel'][src_channel_key]['status'] = status

            self.get_model_catalog().update(product_id, update_field)
        return Response().success(product)

    # TODO: CLEAR TARGET DATA

    def clear_channel(self):
        if not self._state.config.clear_shop and not self._state.config.reset_clear:
            return Response().success()
        if not hasattr(self, self._state.channel.clear_process.function):
            return Response().success()
        fn_clear = getattr(self, self._state.channel.clear_process.function)
        clear = fn_clear()
        if clear.result == Response().SUCCESS:
            entities = ['taxes', 'manufacturers', 'categories', 'products', 'customers',
                        'orders', 'reviews', 'pages', 'blogs', 'coupons', 'cartrules']
            entity_select = list()
            for entity in entities:
                if self._state.config[entity]:
                    entity_select.append(entity)
            if entity_select:
                msg = "Current " + ', '.join(entity_select) + ' cleared'
                if not clear.msg:
                    clear.msg = ''
                clear['msg'] += msg
        # clear['msg'] += self.get_msg_start_import('taxes')
        return clear

    # process image

    def process_image_before_import(self, url, path):
        if not path:
            full_url = url
            path = strip_domain_from_url(url)
        else:
            full_url = join_url_path(url, path)
        path = re.sub(r"[^a-zA-Z0-9.\-_/]", '', path)
        full_url = self.parse_url(full_url)
        return Prodict(**{
            'url': full_url,
            'path': path
        })

    def parse_url(self, url):
        if not url:
            return url
        url = self.remove_duplicate_ds(url)
        scheme, netloc, path, qs, anchor = urllib.parse.urlsplit(url)
        path = urllib.parse.quote(path, '/%=$')
        qs = urllib.parse.quote_plus(qs, ':&=')
        new_url = to_str(urllib.parse.urlunsplit(
            (scheme, netloc, path, qs, anchor)))
        if anchor and anchor.lower().endswith(('.png', '.jpg', '.jpeg', '.tiff', '.bmp', '.gif')):
            new_url = to_str(new_url).replace('#', '%23')
        return new_url

    def join_url_auth(self, url, auth: StateChannelAuth):
        if not url:
            return url
        auth_user = urllib.parse.quote(auth.username)
        auth_pass = urllib.parse.quote(auth.password)
        scheme, netloc, path, qs, anchor = urllib.parse.urlsplit(url)
        netloc = to_str(auth_user) + ':' + \
            to_str(auth_pass) + '@' + to_str(netloc)
        return to_str(urllib.parse.urlunsplit((scheme, netloc, path, qs, anchor)))

    def name_to_code(self, name):
        if not to_str(name).strip(' / - _'):
            return ''
        str_convert = html.unescape(name)
        if isinstance(str_convert, bool):
            if str_convert:
                str_convert = 'yes'
            else:
                str_convert = 'no'
        result = self.generate_url(str_convert)
        if not result:
            return self.parse_url(str_convert).lower()
        try:
            check_encode = chardet.detect(result.encode())
            if check_encode['encoding'] != 'ascii' or not result:
                return self.parse_url(result).lower()
        except Exception:
            pass
        return result.strip('- ')

    def generate_url(self, title):
        if not title:
            return ''
        title = self.remove_special_char(title).lower()
        title = title.strip(' -')
        special = {
            'Æ': 'AE',
            'Đ': 'd',
            'Ø': 'O',
            'Þ': 'TH',
            'ß': 'ss',
            'æ': 'ae',
            'ð': 'd',
            'ø': 'o',
            'þ': 'th',
            'Œ': 'OE',
            'œ': 'oe',
            'ƒ': 'f',
        }
        for index, val in special.items():
            title = title.replace(index, val)
        chars = list(title)
        res = list()
        for char in chars:
            text = unicodedata.normalize('NFD', char).encode('ascii', 'ignore')
            res.append(text.decode() if text.decode() else char)
        res = ''.join(res)
        res = self.replace_url(res)
        return res

    def remove_special_char(self, name):
        if not to_str(name).strip(' / - _'):
            return ''
        name = html.unescape(name)
        result = name.replace(' ', '-').replace('_', '-').replace('.', '-')
        result = result.replace('/', '')
        result = ''.join(e for e in result if e.isalnum() or e == '-')
        result = result.strip(' -')
        while result.find('--') != -1:
            result = result.replace('--', '-')
        return result.strip(' -')

    def replace_url(self, url):
        result = url.strip(' -')
        result = result.replace(' ', '-').replace('_', '-')
        while result.find('--') != -1:
            result = result.replace('--', '-')
        result = result.replace(' ', '-').replace('_', '-')
        return result.strip(' -')

    def reset_process(self, process_id):
        process_info = self.get_sync_info(process_id)
        state = False
        if process_info and process_info.state_id:
            state = self.get_state_by_id(process_info.state_id)
        if not state:
            return False
        action = self._state.resume.action
        for key, value in state.get(action).process.items():
            value = self.reset_entity_process(value)
        state.config.reset = True
        state[action].resume.action = 'display_{}'.format(action)
        state[action].resume.type = ''
        if action == 'pull':
            state.channel.clear.function = 'clear_channel_taxes'
            state.channel.clear.result = 'process'

        res = self.get_model_state().update(
            process_info.state_id, {action: state.get(action)})
        return res

    def reset_entity_process(self, process):
        new_process = EntityProcess()
        new_process.total = process.total
        new_process.limit = process.limit
        for key, value in process.items():
            if key not in new_process:
                # reset smart collection shopify
                if key == 'id_src_smart':
                    new_process[key] = 0
                else:
                    new_process[key] = value
        return new_process

    def prepare_display_finish_pull(self):
        return Response().success()

    def prepare_display_finish_push(self):
        return Response().success()

    def display_finish_channel_pull(self):
        return Response().success()

    def display_finish_channel_push(self):
        return Response().success()

    def display_finish_push(self):
        if self.is_inventory_process() and self._state.push.process.products.total:
            notification_data = {
                'code': '',
                'content': Messages.INVENTORY_SYNC_CONTENT,
                'activity_type': 'inventory_sync',
                'description': Messages.INVENTORY_SYNC_IMPORT.format(self._state.channel.channel_type),
                'date_requested': self._date_requested,
                'result': Activity.SUCCESS
            }
            self.create_activity_recent(**notification_data)
        if self.is_product_process() and not self.is_refresh_process():
            self.count_number_products()
        return Response().success()

    def count_number_products(self):
        where_product = self.get_model_catalog().create_where_condition(
            f'channel.channel_{self.get_channel_id()}.status', 'active')
        where_product.update(self.get_model_catalog(
        ).create_where_condition('is_variant', False))
        number_products = self.get_model_catalog().count(where_product)
        number_products_linked = number_products
        if not self.is_channel_default():
            where_product.update(self.get_model_catalog().create_where_condition(
                f'channel.channel_{self.get_channel_id()}.link_status', 'linked'))
            number_products_linked = self.get_model_catalog().count(where_product)
        self.update_channel(number_products=number_products,
                            number_products_linked=number_products_linked)

    def display_finish_pull(self):
        if self.is_product_process() and not self.is_refresh_process():
            self.count_number_products()
        # self.get_model_sync_mode().after_import(self.get_channel_id(), self.get_sync_id())
        return Response().success()

    # TODO: MAP

    def get_category_map(self, category_id):
        catalog = self.get_model_category().get(to_str(category_id))
        return catalog.channel.get("channel_{}".format(self._state.channel.id)).category_id if catalog else False

    def get_product_map(self, product_id):
        catalog = self.get_model_catalog().get(product_id)
        if not catalog:
            return False

        if self._state.channel.default:
            field_check = 'channel_{}'.format(self.get_src_channel_id())
            if not catalog['channel'].get(field_check) or catalog['channel'][field_check].get('link_status') != ProductChannel.LINKED:
                return False
        field_check = 'channel_{}'.format(self.get_channel_id())
        if not catalog['channel'].get(field_check) or catalog['channel'][field_check].get('status') != ProductChannel.ACTIVE:
            return False

        return catalog['channel'][field_check].get('product_id')

    def get_product_warehouse_map(self, product_id, channel_id=None, return_product=False):
        if not product_id:
            return False
        if not channel_id:
            channel_id = self._state.channel.id
        field_check = "channel.channel_{}.product_id".format(channel_id)
        product = self.get_model_catalog().find(field_check, to_str(product_id))
        if not product:
            return False
        product = Prodict(**product)
        return product.get('_id') if not return_product else product

    # ================================

    def get_warehouse_location_default(self):
        if self._warehouse_location_default is not None:
            return to_int(self._warehouse_location_default)
        self._warehouse_location_default = self.get_model_sync_mode(
        ).get_warehouse_location_default()
        return to_int(self._warehouse_location_default)

    def get_warehouse_location_fba(self):
        if self._warehouse_location_fba is not None:
            return to_int(self._warehouse_location_fba)
        self._warehouse_location_fba = self.get_model_sync_mode().get_warehouse_location_fba()
        return to_int(self._warehouse_location_fba)

    def create_activity_feed(self, **kwargs):
        model = CollectionActivity()
        model.set_user_id(self._user_id)
        return model.create_feed(channel_id=self._state.channel.id, channel_type=self._state.channel.channel_type, **kwargs)

    def create_activity_notification(self, **kwargs):
        model = CollectionActivity()
        model.set_user_id(self._user_id)
        return model.create_notification(channel_id=self._state.channel.id, channel_type=self._state.channel.channel_type, **kwargs)

    def create_activity_process(self, **kwargs):
        model = CollectionActivity()
        model.set_user_id(self._user_id)
        model.create_process(channel_id=self._state.channel.id,
                             channel_type=self._state.channel.channel_type, **kwargs)

    def create_activity_recent(self, **kwargs):
        model = CollectionActivity()
        model.set_user_id(self._user_id)
        model.create_recent(channel_id=self._state.channel.id,
                            channel_type=self._state.channel.channel_type, **kwargs)

    def update_state(self, data):
        if self._state_id == 'litcommerce':
            return True
        return self.get_model_state().update(self._state_id, data)

    def update_field_state(self, field, value):
        return self.get_model_state().update_field(self._state_id, field, value)

    def get_process_by_type(self, process_type, channel_id=None):
        if not channel_id:
            channel_id = self._channel_id
        if self._request_data.get('processes'):
            for process_id, process_data in self._request_data['processes'].items():
                if to_int(process_data['channel_id']) == to_int(channel_id) and process_data['type'] == process_type:
                    return Prodict.from_dict(process_data)
        return self.get_model_sync_mode().get_process_by_type(channel_id, process_type)

    def get_process_by_id(self, process_id):
        if self._request_data.get('processes') and self._request_data['processes'].get(to_str(process_id)):
            return Prodict.from_dict(self._request_data['processes'].get(to_str(process_id)))

        return self.get_model_sync_mode().get_process_by_id(process_id)

    def create_order_process(self, state):
        order_state = SyncState()
        order_state.channel = state.channel
        order_state.user_id = self._user_id
        state_id = self.get_model_state().create(order_state)
        if not state_id:
            return False
        process_id = self.get_model_sync_mode().create_order_sync_process(
            state_id, self._channel_id)
        if not process_id:
            return False
        self.get_model_state().update_field(state_id, 'sync_id', process_id)
        order_state.sync_id = process_id
        return {
            'process_id': process_id,
            'state_id': state_id,
            'state': order_state
        }

    def create_inventory_process(self, state):
        inventory_state = SyncState()
        inventory_state.channel = state.channel
        inventory_state.user_id = self._user_id
        inventory_state.push.process.products['condition'] = [
            Prodict.from_dict({
                'field': f"channel.channel_{state.channel.id}.status",
                'value': ProductChannel.ACTIVE,
                'condition': '='
            }),
            Prodict.from_dict({
                'field': f"channel.channel_{state.channel.id}.link_status",
                'value': ProductChannel.LINKED,
                'condition': '='
            })
        ]
        state_id = self.get_model_state().create(inventory_state)
        if not state_id:
            return False
        process_id = self.get_model_sync_mode().create_inventory_sync_process(
            state_id, self._channel_id)
        if not process_id:
            return False
        self.get_model_state().update_field(state_id, 'sync_id', process_id)
        inventory_state.sync_id = process_id
        return {
            'process_id': process_id,
            'state_id': state_id,
            'state': inventory_state
        }

    def create_refresh_process_scheduler(self):
        return self.get_model_sync_mode().create_refresh_process_scheduler(self.get_channel_id())

    def after_create_order_process(self, process):
        return Response().success()

    def after_create_inventory_process(self, process):
        return Response().success()

    def get_scheduler_info(self, scheduler_id):
        return self.get_model_sync_mode().get_scheduler_info(scheduler_id)

    def create_scheduler_process(self, process_id):
        return self.get_model_sync_mode().create_scheduler_process(process_id)

    def set_last_time_scheduler(self, scheduler_id):
        return self.get_model_sync_mode().set_last_time_scheduler(scheduler_id)

    def _adjustment_price(self, adjustment, price):
        price = to_decimal(price)
        value = to_decimal(adjustment['value'])
        if adjustment['modifier'] == 'percent':
            value = round((price * value) / 100, 2)
        return round(price + value if adjustment['direction'] == 'increment' else price - value, 2)

    def adjustment_price(self, price_template, price):
        if price_template.get('custom_price') and price_template['custom_price'].get('status') == 'enable':
            return round(price_template['custom_price']['value'], 2)
        adjustment = price_template.get('adjustment') or price_template
        price = self._adjustment_price(adjustment, price)
        if price_template.get('extend_adjustment'):
            for row in price_template['extend_adjustment']:
                if not row.get('value'):
                    continue
                price = self._adjustment_price(row, price)
        if adjustment.get('rounding'):
            price = rounding_price(adjustment.get('rounding'), price)
        return price

    def allow_attribute_title_template(self):
        return ['sku', 'name', 'description', 'brand', 'price', 'condition', 'condition_notes', 'category', 'manufacturer', 'model', 'ean', 'asin', 'espn', 'upc', 'gtin', 'gcid', 'epid', 'weight', 'width', 'length', 'height', 'mpn']

    def assign_title_template_channel(self, channel_type, title_template, product, **kwargs):
        try:
            module_class = importlib.import_module(
                "merchant.{}.utils".format(channel_type))
            model_class = getattr(
                module_class, 'Merchant{}Utils'.format(channel_type.capitalize()))
            utils = model_class()
            if hasattr(utils, 'assign_title_template'):
                getattr(utils, 'assign_title_template')(
                    title_template, product, **kwargs)
        except:
            pass
        return True

    def assign_title_template(self, title_template, product, **kwargs):
        if not title_template:
            return True
        allow_field = self.allow_attribute_title_template()
        title = title_template['title']
        changed = False
        for field in allow_field:
            value = to_str(product.get(field))
            if not value:
                continue
            title = to_str(title).replace("{" + field + "}", value)
            changed = True
        if not changed:
            return True
        model_product = self.get_model_catalog()
        field = f"channel.channel_{self._channel_id}.name"
        model_product.update_field(product['_id'], field, title)
        self.assign_title_template_channel(
            self._channel_type, title_template, product, **kwargs)
        return True

    def assign_template(self, product: Product, templates_data=None, update=True):
        # if self.is_inventory_process():
        # 	return product
        product = self._assign_template(product, templates_data, update)
        if product.variants:
            for variant in product.variants:
                variant.channel[f'channel_{self.get_channel_id()}']['templates'] = copy.deepcopy(
                    product.channel[f'channel_{self.get_channel_id()}']['templates'])
                variant.channel[f'channel_{self.get_channel_id()}']['template_data'] = copy.deepcopy(
                    product.channel[f'channel_{self.get_channel_id()}']['template_data'])
                variant = self._assign_template(
                    variant, templates_data, update)
        return product

    def variants_to_option(self, variants):
        max_attribute = 0
        option_src = list()
        for variant in variants:
            attributes = list(
                filter(lambda x: x.use_variant, variant.attributes))
            if max_attribute <= to_len(attributes):
                max_attribute = to_len(attributes)
                option_src = attributes
        all_option_name = list()
        for option in option_src:
            if option.attribute_name in all_option_name:
                continue
            all_option_name.append(option.attribute_name)
        options = dict()
        for variant in variants:
            if variant and 'visible' in variant:
                if not to_bool(variant.visible):
                    continue
            for attribute in variant.attributes:
                if attribute.attribute_name not in all_option_name:
                    continue
                if attribute.attribute_name not in options:
                    options[attribute.attribute_name] = list()
                if not attribute.attribute_value_name or attribute.attribute_value_name in options[attribute.attribute_name]:
                    continue
                options[attribute.attribute_name].append(
                    attribute.attribute_value_name)
        return options

    def _assign_template(self, product: Product, templates_data=None, update=True):
        channel_data = product.channel[f"channel_{self.get_channel_id()}"]
        template_data = channel_data.get('templates')
        if not template_data:
            return product
        edited = False
        required_template = self.TEMPLATE_REQUIRED_ASSIGN
        if self.is_inventory_process():
            required_template = ['price']
        for template_type in required_template:
            template_id = template_data.get(template_type)
            if not template_id:
                continue
            if templates_data and templates_data.get(template_type):
                template_type_data = templates_data[template_type]
            else:
                template_type_data = self.get_model_template().get(template_id)
            if not hasattr(self, f'channel_assign_{template_type}_template') or not template_type_data:
                continue
            edited = True
            template_type_data = Prodict.from_dict(template_type_data)
            product = getattr(self, f'channel_assign_{template_type}_template')(
                product, template_type_data)
        if edited and update:
            self.get_model_catalog().update_field(
                product['_id'], f'channel.channel_{self.get_channel_id()}', product.channel.get(f'channel_{self.get_channel_id()}'))
        return product

    def channel_assign_template(self, product: Product, templates_data=None, update=True):
        return product

    def channel_assign_price_template(self, product, templates_data):
        price = round(self.adjustment_price(templates_data, product.price), 2)
        product.price = price
        product.channel[f'channel_{self.get_channel_id()}']['price'] = price
        return product

    def is_channel_strip_html_in_description(self):
        return self.get_channel_type() in ['etsy', 'facebook', 'google', 'ebay']

    def channel_assign_title_template(self, product, templates_data):
        draft_data = self.get_draft_extend_channel_data(product)
        if draft_data.get('description'):
            product.description = draft_data['description']
        if draft_data.get('name'):
            product.name = draft_data['name']
        title = templates_data['title']
        title = self.assign_attribute_to_field(title, product)
        product.name = title
        product.channel[f'channel_{self.get_channel_id()}']['name'] = title
        description = templates_data['description']
        description = self.assign_attribute_to_field(description, product)
        product.description = description
        product.channel[f'channel_{self.get_channel_id()}']['description'] = description
        return product

    def assign_attribute_to_field(self, field, product):
        field = to_str(field)
        allow_field = self.allow_attribute_title_template()
        for attribute in allow_field:
            value = product.get(attribute)
            if isinstance(value, (dict, Prodict)):
                if 'name' in value:
                    value = value.get('name')
                else:
                    value = ''
            else:
                value = to_str(value)

            if field.find("{{" + attribute + "}}") == -1:
                continue
            if not value:
                value = ''
            field = field.replace("{{" + attribute + "}}", value)
        for attribute in product.attributes:
            value = attribute.attribute_value_name
            if field.find("{{" + attribute.attribute_name + "}}") == -1:
                continue
            field = to_str(field).replace(
                "{{" + attribute.attribute_name + "}}", value)
        field = re.sub("{{.*?}}", '', field)
        return field

    def apply_channel_setting(self, product: Product):
        # if not self.is_inventory_process():
        # 	return product
        product = self._apply_channel_setting(product, None)
        if product.variants:
            for variant in product.variants:
                variant = self._apply_channel_setting(variant, product)
        return product

    def get_setting_max_qty(self):
        qty_setting = self._state.channel.config.setting.get('qty')
        if isinstance(qty_setting, dict) and to_decimal(qty_setting.get('adjust')):
            if qty_setting['max_qty']:
                return to_int(qty_setting['max_qty'])
        return False

    def _apply_channel_setting(self, product: Product, parent=None):
        channel_data = product.channel[f"channel_{self.get_channel_id()}"]
        template_data = channel_data.get('templates')
        if not template_data and parent:
            channel_data = parent.channel[f"channel_{self.get_channel_id()}"]
            template_data = channel_data.get('templates')
        price_template = template_data.get('price') if template_data else False
        price_setting = self._state.channel.config.setting.get('price')
        qty_setting = self._state.channel.config.setting.get('qty')
        if not price_template and price_setting and isinstance(price_setting, dict) and price_setting.get('value'):
            adjust_value = to_decimal(
                price_setting['value']) if price_setting['modifier'] == 'fixed' else product['price'] * to_decimal(price_setting['value']) / 100
            product['price'] = product['price'] + \
                adjust_value if price_setting['direction'] == 'increase' else product['price'] - adjust_value
            product['price'] = to_decimal(product['price'], 2)
        if isinstance(qty_setting, dict) and to_decimal(qty_setting.get('adjust')):
            qty = round(product['qty'] *
                        to_decimal(qty_setting['adjust']) / 100)
            if not product.is_in_stock:
                qty = 0
            elif not product.manage_stock:
                qty = 999
            if qty_setting['max_qty'] and qty >= qty_setting['max_qty']:
                qty = qty_setting['max_qty']
            if qty_setting['min_qty'] and qty <= qty_setting['min_qty']:
                qty = qty_setting['min_qty']
            product['qty'] = qty
        return product

    # todo: listing

    def _listing_product(self, product, channel_id, template_data, product_channel_default):
        product_channel = copy.deepcopy(product_channel_default)
        special_field = ['sku', 'name']
        product_channel_data_extend = self.get_draft_extend_channel_data(
            product)
        if product_channel_data_extend:
            product_channel.update(product_channel_data_extend)
        product['channel'][f'channel_{channel_id}'] = copy.deepcopy(
            product_channel)
        if product.get('variants'):
            for variant in product['variants']:
                variant['channel'][f'channel_{channel_id}'] = copy.deepcopy(
                    product_channel_default)

        product = self.assign_template(product, template_data, False)
        product_channel_product = product.channel[f'channel_{self.get_channel_id()}']
        for field in special_field:
            if not product_channel_product.get(field) and product.get(field):
                product_channel_product[field] = product[field]
        if product.variants:
            product_qty = 0
            for variant in product.variants:
                variant_channel_data_extend = self.get_draft_extend_channel_data(
                    variant)
                if not variant.seo_url:
                    variant.seo_url = product.seo_url
                variant_channel_product = variant.channel[f'channel_{self.get_channel_id()}']
                for field in special_field:
                    if not variant_channel_product.get(field) and variant.get(field):
                        variant_channel_product[field] = variant[field]
                if variant_channel_data_extend:
                    for row, value in variant_channel_data_extend.items():
                        if to_str(value).strip(' /-_'):
                            variant_channel_product[row] = value
                variant_qty = variant_channel_product.get('qty') or variant.qty
                product_qty += to_int(variant_qty)
                product_channel_product['qty'] = product_qty
                self.get_model_catalog().update_field(
                    variant['_id'], f"channel.channel_{channel_id}", variant_channel_product)
        self.get_model_catalog().update_field(
            product['_id'], f"channel.channel_{channel_id}", product_channel_product)

    def listing(self, channel_id, product_ids):
        where_draft = dict()
        where_draft.update(self.get_model_catalog().create_where_condition(
            'channel.channel_{}.status'.format(channel_id), ProductChannel.DRAFT))
        where_draft.update(self.get_model_catalog(
        ).create_where_condition('_id', product_ids, "in"))
        product_exist = self.get_model_catalog().find_all(where_draft, select_fields='id')
        product_ids_exist = [product['_id']
                             for product in product_exist] if product_exist else []
        where_active = dict()
        where_active.update(self.get_model_catalog().create_where_condition(
            'channel.channel_{}.status'.format(channel_id), ProductChannel.ACTIVE))
        where_active.update(self.get_model_catalog().create_where_condition(
            'channel.channel_{}.link_status'.format(channel_id), ProductChannel.LINKED))
        where_active.update(self.get_model_catalog(
        ).create_where_condition('_id', product_ids, "in"))
        product_exist = self.get_model_catalog().find_all(
            where_active, select_fields='id')
        product_ids_exist += [product['_id']
                              for product in product_exist] if product_exist else []
        where_active_unlink = where_active
        where_active_unlink.update(self.get_model_catalog().create_where_condition(
            'channel.channel_{}.link_status'.format(channel_id), ProductChannel.UNLINK))
        product_unlink = self.get_model_catalog().find_all(where_active)
        new_product_ids = self.listing_product_unlink(
            product_unlink, channel_id)
        product_ids = list(
            filter(lambda x: x not in product_ids_exist, product_ids))

        product_channel_default = ProductChannel()
        product_channel_default.status = ProductChannel.DRAFT
        product_channel_default.channel_id = channel_id

        where_update = self.get_model_catalog(
        ).create_where_condition('_id', product_ids, 'in')
        # self.get_model_catalog().update_many(where_update, {"channel.channel_{}".format(channel_id): product_channel.to_dict()})

        tem = dict()
        tem.update(self.get_model_template().create_where_condition(
            "channel_id", channel_id, '='))
        tem.update(self.get_model_template(
        ).create_where_condition("default", True, "="))
        list_tem = self.get_model_template().find_all(tem)
        template_data = {}
        if list_tem:
            for template in list_tem:
                template_data[template['type']] = template
                product_channel_default.templates[template.get(
                    'type')] = template.get('_id')
                product_channel_default.template_data[template.get(
                    'type')] = self.unset_data_template(template)
        # product_channel = copy.deepcopy(product_channel_default)

        products = self.get_model_catalog().find_all(where_update)
        for product in products:
            product_channel = copy.deepcopy(product_channel_default)
            variants = self.get_variants(product, channel_id)
            if variants:
                product['variants'] = variants
            self._listing_product(product, channel_id,
                                  template_data, product_channel)

        # where_update_variant = self.get_model_catalog().create_where_condition('parent_id', product_ids, 'in')
        # self.get_model_catalog().update_many(where_update_variant, {"channel.channel_{}".format(channel_id): product_channel_default.to_dict()})

        return Response().success()

    def listing_product_unlink(self, products, channel_id):
        if not products:
            return []
        product_ids = []
        for product in products:
            product_id = self.clone_product_for_channel(product, channel_id)
            if product_id:
                product_ids.append(product_id)
        return product_ids

    def clone_product_for_channel(self, product, channel_id):
        product_clone = copy.deepcopy(product)
        product_channel_data = product_clone['channel'][f'channel_{channel_id}']
        del product_clone['_id']
        del product_clone['id']
        product_clone['channel'] = {
            f'channel_{channel_id}': product_channel_data
        }
        product_clone_id = self.get_model_catalog().create(product_clone)
        if not product_clone_id:
            return product_clone_id
        variants = self.get_variants(product, channel_id)
        for variant in variants:
            self.clone_variant_for_channel(
                variant, product_clone_id, channel_id)
        return product_clone_id

    def clone_variant_for_channel(self, variant, product_id, channel_id):
        variant_clone = copy.deepcopy(variant)
        variant_channel_data = variant_clone['channel'][f'channel_{channel_id}']
        del variant_clone['_id']
        del variant_clone['id']
        variant['channel'] = {
            f'channel_{channel_id}': variant_channel_data
        }
        variant['parent_id'] = product_id
        variant_clone_id = self.get_model_catalog().create(variant)
        return variant_clone_id

    def unset_data_template(self, data, unset=('id', '_id', 'type', 'channel_id')):
        new_data = copy.deepcopy(data)
        for field in unset:
            if field in new_data:
                del new_data[field]
        return new_data

    def sync_inventory(self, check_import, data, product, products_ext):
        field_check = 'channel_{}'.format(self._state.channel.id)
        if not product or not product['channel'].get(field_check):
            return Response().error(Errors.PRODUCT_DATA_INVALID)
        product_id = product['channel'][field_check].get('product_id')
        if not product_id:
            return Response().error(Errors.PRODUCT_DATA_INVALID)
        channel_sync = self.channel_sync_inventory(
            product_id, product, products_ext)
        if channel_sync.result != Response.SUCCESS:
            return channel_sync
        product = channel_sync.data or product
        qty = product.qty
        price = product.price
        setting_price = True if self._state.channel.config.setting.get(
            'price', {}).get('status') != 'disable' else False
        setting_qty = True if self._state.channel.config.setting.get(
            'qty', {}).get('status') != 'disable' else False
        update_channel = dict()
        if setting_price:
            update_channel[f'channel.channel_{self._state.channel.id}.price'] = price
        if setting_qty:
            update_channel[f'channel.channel_{self._state.channel.id}.qty'] = qty
        if product.variants:
            product_qty = 0
            for variant in product.variants:
                update_channel = dict()
                if not variant.sync_error:
                    variant_qty = to_int(variant.qty)
                else:
                    variant_qty = to_int(variant.channel.get(
                        f'channel_{self.get_channel_id()}', {}).get('qty'))
                product_qty += variant_qty
                if setting_price:
                    update_channel[f'channel.channel_{self._state.channel.id}.price'] = variant.price
                if setting_qty:
                    update_channel[f'channel.channel_{self._state.channel.id}.qty'] = variant_qty
                self.get_model_catalog().update(variant['_id'], update_channel)
            if setting_qty:
                update_channel[f'channel.channel_{self._state.channel.id}.qty'] = product_qty
        self.get_model_catalog().update(product['_id'], update_channel)

        return channel_sync

    def channel_sync_inventory(self, product_id, product, products_ext):
        return Response().success()

    def is_inventory_process(self):
        return self._process_type == self.PROCESS_TYPE_INVENTORY

    def is_refresh_process(self):
        return self._process_type == self.PROCESS_TYPE_REFRESH

    def is_order_process(self):
        return self._process_type == self.PROCESS_TYPE_ORDER

    def is_product_process(self):
        return self._process_type in [self.PROCESS_TYPE_PRODUCT, self.PROCESS_TYPE_REFRESH]

    def is_category_process(self):
        return self._process_type in [self.PROCESS_TYPE_CATEGORY]

    def set_imported_product(self, imported):
        self._state.pull.process.products.imported += imported

    def set_imported_order(self, imported):
        self._state.pull.process.orders.imported += imported

    def set_imported_category(self, imported):
        self._state.pull.process.categories.imported += imported

    def set_imported_tax(self, imported):
        self._state.pull.process.taxes.imported += imported

    def allow_scheduler_pull_order(self):
        return not self._state.channel.default

    def allow_scheduler_pull_product(self):
        return self._state.channel.default and self._state.channel.channel_type in ['magento']

    def is_channel_default(self):
        return self._state.channel.default

    def get_channel_by_id(self, channel_id):
        if self._request_data.get('channels') and self._request_data['channels'].get(to_str(channel_id)):
            return Prodict.from_dict(self._request_data['channels'].get(to_str(channel_id)))
        if self._all_channel_by_id.get(channel_id):
            return self._all_channel_by_id[channel_id]
        channel = self.get_model_sync_mode().get_channel_by_id(channel_id)
        if channel:
            self._all_channel_by_id[channel_id] = channel
        return channel

    def is_special_price(self, product: Product):
        special_price = product.special_price
        if not to_decimal(special_price.price, 2) or to_decimal(special_price.price) >= to_decimal(product.price) or not to_timestamp_or_false(special_price.start_date):
            return False
        if not to_timestamp_or_false(special_price.end_date):
            return True
        if to_timestamp_or_false(special_price.start_date) <= time.time() <= to_timestamp_or_false(special_price.end_date):
            return True
        return False

    def channel_url_to_identifier(self, channel_url=None):
        if not channel_url:
            channel_url = self._channel_url
        from urllib.parse import urlparse
        url = urlparse(channel_url)
        identifier = url.netloc.replace('www.', '')
        if url.path:
            identifier += '/' + url.path.strip('/')
        return identifier

    def is_draft(self, product, channel_id):
        if not product['channel'].get(f'channel_{channel_id}'):
            return True
        return product['channel'][f'channel_{channel_id}'].get('status') in ('draft', 'error')

    def get_variants(self, product, channel_id):
        product_id = product['_id']
        if self.is_draft(product, channel_id):
            channel_id = self.get_channel_default_id()
            if not product.channel.get(f'channel_{channel_id}', dict()).get('product_id'):
                channel_id = product.src.channel_id
        where = dict()

        where.update(self.get_model_catalog().create_where_condition(
            f'channel.channel_{channel_id}.status', 'active'))
        channel = self.get_channel_by_id(channel_id)
        if channel.get('custom_linked_product'):
            where_variant_list = [
                self.get_model_catalog().create_where_condition('is_variant', True),
                self.get_model_catalog().create_where_condition(
                    f'channel.channel_{channel_id}.is_variant', True),
            ]
            where_variant = self.get_model_catalog().create_where_condition(None,
                                                                            where_variant_list, 'or')
            where_parent_list = [
                self.get_model_catalog().create_where_condition('parent_id', to_str(product_id)),
                self.get_model_catalog().create_where_condition(
                    f'channel.channel_{channel_id}.parent_id', to_str(product_id)),
            ]
            where_parent = self.get_model_catalog().create_where_condition(None,
                                                                           where_parent_list, 'or')
            where_variant_parent = self.get_model_catalog().create_where_condition(
                None, [where_parent, where_variant], 'and')
            where = self.get_model_catalog().create_where_condition(
                None, [where, where_variant_parent], 'and')
        else:
            where.update(self.get_model_catalog().create_where_condition(
                'parent_id', product_id))
            where.update(self.get_model_catalog(
            ).create_where_condition('is_variant', True))
        variants = self.get_model_catalog().find_all(where)
        if variants:
            variants = list(map(lambda x: Prodict(**x), variants))
        return variants

    def is_valid_variant(self, variant, attributes):
        if not attributes:
            return False
        if not variant.attributes:
            return False
        variant_attribute = dict()
        for attribute in variant.attributes:
            if not attribute.use_variant:
                continue
            variant_attribute[attribute.attribute_name] = attribute.attribute_value_name
        for attribute in attributes:
            if not variant_attribute.get(attribute):
                return False
        return True

    def unset_template_data(self, template_data, unset=('_id', 'id', 'type', 'name', 'channel_id')):
        result = copy.deepcopy(template_data)
        for field in unset:
            if field in result:
                del result[field]
        return result

    def get_draft_extend_channel_data(self, product):
        return {}

    def add_product_to_draft(self, product_id, product: Product, assign_template=True):
        product_channel_data = ProductChannel()
        product_channel_data.channel_id = self.get_channel_id()
        product_channel_data.status = ProductChannel.DRAFT
        product_channel_data.sku = product.sku
        product_channel_data.name = product.name
        product_channel_data_extend = self.get_draft_extend_channel_data(
            product)
        if product_channel_data_extend:
            product_channel_data.update(product_channel_data_extend)
        where = self.get_model_template().create_where_condition(
            'channel_id', to_int(self.get_channel_id()))
        where.update(self.get_model_template(
        ).create_where_condition('default', True))
        templates = self.get_model_template().find_all(where)
        template_data = dict()
        if templates:
            for template in templates:
                template_data[template['type']] = template
                product_channel_data.templates[template['type']
                                               ] = template['_id']
                product_channel_data.template_data[template['type']] = self.unset_template_data(
                    template)
        product.channel[f'channel_{self.get_channel_id()}'] = product_channel_data
        if assign_template:
            product = self.assign_template(product, template_data, False)
        product_channel_data = product.channel[f'channel_{self.get_channel_id()}']
        self.get_model_catalog().update_field(
            product_id, f'channel.channel_{self.get_channel_id()}', product_channel_data)
        product = self.apply_channel_setting(product)
        return product

    def get_channel_type(self):
        return self._state.channel.channel_type

    def product_deleted(self, product_id, product: Product = None, channel_id=None):
        if not product:
            product = self.get_model_catalog().get(product_id)
        if not product:
            return True
        product = Prodict(**product)
        if not channel_id:
            channel_id = self.get_channel_id()
        # channel_default_id = self.get_channel_default_id()
        channel_data = product.get('channel')
        is_delete = True
        update_data = {
            f'channel.channel_{channel_id}': {}
        }

        if channel_data:
            for channel, channel_data in channel_data.items():
                key_channel_id = to_str(channel).replace('channel_', '')
                if to_int(key_channel_id) != to_int(channel_id):
                    is_delete = False
                    if self.is_channel_default():
                        update_data[f'channel.{channel}.link_status'] = ProductChannel.UNLINK

        if is_delete:
            self.get_model_catalog().delete(product_id)
            self.get_model_catalog().delete_many_document(
                self.get_model_catalog().create_where_condition('parent_id', product_id))
        else:
            if not product.is_variant:
                variants = self.get_model_catalog().find_all(
                    self.get_model_catalog().create_where_condition('parent_id', product_id))
                for variant in variants:
                    self.product_deleted(variant['_id'], variant)
            self.get_model_catalog().update(product_id, update_data)
        return True

    def get_order_start_time(self, time_format='%Y-%m-%d %H:%M:%S'):
        start_time = to_timestamp(self._state.channel.created_at)
        start_time = datetime.fromtimestamp(start_time)
        if self._state.channel.config.start_time:
            start_time = self._state.channel.config.start_time
            if to_str(start_time).isnumeric():
                start_time = datetime.fromtimestamp(start_time)
            else:
                start_time = isoformat_to_datetime(start_time)
        if time_format:
            if time_format == 'iso':
                iso_format = start_time.isoformat()
                if iso_format.endswith("+00:00"):
                    iso_format = iso_format.replace("+00:00", 'Z')
                return iso_format
            return start_time.strftime(time_format)
        return start_time.timestamp()

    def send_email(self, email_to, content_mail, subject=None, email_from=None):
        content_mail = to_str(content_mail).replace(
            'https://', 'ht_tps://').replace('http://', 'ht_tp://')
        api_key = get_config_ini('sendgrid', 'api_key')
        if not email_from:
            email_from = get_config_ini(
                'sendgrid', 'email_from', 'admin@litcommerce.com')
        if not email_to:
            email_to = get_config_ini(
                'sendgrid', 'email_to', 'admin@litcommerce.com')
        sg = sendgrid.SendGridAPIClient(api_key)
        email_from = Email(email_from)
        email_to = Email(email_to)
        subject = subject if subject else "Title"
        mail_content = Content("text/plain", content_mail)
        send_mail = Mail(email_from, subject, email_to, mail_content)
        try:
            sg.client.mail.send.post(request_body=send_mail.get())
        except Exception:
            self.log_traceback('sendgrid')

    def replace_msg(self, msg):
        if msg:
            msg = msg[0].upper() + msg[1:]
        return msg

    def channel_no_parent(self):
        return []
        return ['google', 'amazon']

    def channel_no_after_push(self):
        return ['amazon']

    def after_update_product(self, product_id, import_data, product: Product):
        if self.is_inventory_process():
            return Response().success(product)

        if self._state.channel.channel_type not in self.channel_no_after_push():
            update_field = dict()
            channel_key = f"channel.channel_{self.get_src_channel_id()}"

            if import_data.result in (Response.ERROR, Response.WARNING):
                if import_data.code and import_data.msg:
                    msg = Errors().get_msg_error(import_data.code) + ": " + \
                        f"{self.replace_msg(import_data.msg)}"
                elif import_data.code:
                    msg = Errors().get_msg_error(import_data.code)
                elif import_data.msg:
                    msg = import_data.msg
                else:
                    msg = Errors().get_msg_error(Errors.EXCEPTION_IMPORT)
                publish_status = ProductChannel.ERRORS
            else:
                msg = ""
                publish_status = ProductChannel.COMPLETED
                update_field[f"{channel_key}.edited"] = False

            update_field[f"{channel_key}.publish_status"] = publish_status
            update_field[f"{channel_key}.publish_action"] = None
            update_field[f"{channel_key}.error_message"] = msg

            product.channel[channel_key] = self.get_product_channel_data(
                product, '')
            product.channel[channel_key]['publish_status'] = publish_status
            product.channel[channel_key]['publish_action'] = None
            product.channel[channel_key]['error_message'] = msg
            self.get_model_catalog().update(product_id, update_field)
        return Response().success(product)

    def image_exist(self, url):
        image_process = self.process_image_before_import(url, None)
        return self.url_exist(image_process['url'])

    def url_exist(self, url):
        try:
            exist = requests.get(
                url, headers={"User-Agent": get_random_useragent()}, timeout=5, verify=False)
        except requests.exceptions.Timeout as errt:
            return False
        except Exception as e:
            return False
        return exist.status_code == requests.codes.ok

    def get_current_product(self, product_id):
        return self.get_model_catalog().get(product_id)

    def get_current_order(self, order_id):
        return self.get_model_order().get(order_id)

    def is_run_refresh(self):
        where = self.get_model_catalog().create_where_condition(
            f"channel.channel_{self.get_channel_default_id()}.product_id", '', '>')
        if self.get_model_catalog().count(where) > 0:
            return True
        return False

    def is_run_scheduler(self):
        if time.time() < 1658312100.0 and self._state and self.get_channel_type() == 'etsy':
            return False
        where = self.get_model_catalog().create_where_condition(
            f"channel.channel_{self.get_channel_id()}.product_id", '', '>')
        if self.get_model_catalog().count(where) > 0:
            return True
        return False

    def product_lower_name(self, product_name):
        product_name = to_str(product_name)
        import string
        chars = re.escape(string.punctuation)
        name = re.sub(r'[' + chars + ']', ' ', product_name)
        while name.find('  ') != -1:
            name = name.replace('  ', ' ')
        return name.lower().strip()

    def variant_key_generate_by_attributes(self, attributes):
        key_generate = list()
        for attribute in attributes:
            if not attribute.use_variant:
                continue

            key_generate.append({"id": to_str(attribute.attribute_name).lower(
            ), 'value': to_str(attribute.attribute_value_name).lower()})
        key_generate = sorted(key_generate, key=lambda d: d['id'])
        base64_generate = list()
        for row in key_generate:
            base64_generate.append(f"{row['id']}:{row['value']}")
        str_generate = string_to_base64('|'.join(base64_generate))
        return str_generate

    def variant_key_generate(self, variant):

        return self.variant_key_generate_by_attributes(variant.attributes)

    def get_full_name(self, customer):
        first_name = customer.first_name
        last_name = customer.first_name
        full_name = []
        if first_name:
            full_name.append(first_name)
        if last_name:
            full_name.append(last_name)
        return " ".join(full_name)

    def image_content_type_to_mime_type(self, content_type):
        if not content_type:
            return 'PNG'
        mime_types = {
            'image/bmp': 'BMP',
            'image/webp': 'webp',
            'image/tiff': 'tiff',
            'image/svg+xml': 'SVG',
            'image/png': 'PNG',
            'image/jpeg': 'JPEG',
            'image/vnd.microsoft.icon': 'ICO',
            'image/gif': 'GIF',
        }
        return mime_types.get(content_type, 'PNG')

    def strip_html_from_description(self, text):
        if not text:
            return ''
        text = to_str(text).replace('<br>', '\n').replace('</br>', '\n')
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(text, 'lxml')
        return soup.getText().strip()

    def detect_firewall(self, html):
        html = to_str(html)
        if not html:
            return 0
        if (html.find('Performance') >= 0 and html.find('security by') >= 0 and html.find('Cloudflare') >= 0) or (html.find('cloudflare-static/rocket-loader.min.js') >= 0):
            return 'CloudFlare'
        if html.find('This website is using a security service to protect itself from online attacks') >= 0 and html.find('StackPath') >= 0:
            return 'StackPath'
        if html.find('Sorry, this is not allowed') >= 0 and html.find('getastra.com') >= 0:
            return 'Astra'
        if html.find(
            'R0lGODlhlgAoALMAAPHw8Dw8PNLS06mqqpSVlvRvJvqaZfu2j3V1doSEhuHh4rm6uv3Uv8TFxWVmaP///yH5BAAAAAAALAAAAACWACgAAAT/8MlJKSAuo1XnRdoAdMLQSYojTAlxKgToIIQiLbNbJeBINbkfgnZ68BLFGMI3GSwGuqLUk1k0FhhkBecgDAaJzIoicHA6qcbEoaUMMolv2PxIZZj1DJ0iO0vmDngTIAhFc4ICV1FTUkMVCiZuDiIUCmFqE3ZjlQ6YDwhtEhiUFBh/VZJwFnqcepEVIKGldx2CjEWdjGWvO4GZejacnqAUOH6PI1yhgL43GYtveoUdYbITGM232hSTjI5SXb8NYXhpg6FstwB6PnZ6fnObn2zY8hKxSbTb+w8Y9sJTTKFwYCMDwHttyvw7ge0Mlxjp8swgg+oZtYgdsNniF/BZA0FA/4IVCTmQQ4o25u5FebOxA5CIhzQ+4MJL5iFYGCvI5LhPADY2InG0lEAyD6YyOlJ+avNmH6sHFrlwmCMSasSXx4zknJWN5z4AC0AEK1pE6EBPQEwoJeZsqE4xZXLZIbBu4gSsAADYkYWPoT6vPL+t43VRnKQVuRD+yiolboKbWmlkiATgQIHLmDMbMMDg3tZrfwHzw8HCQeM9Rt/iGLYIxD4ZFp3p8WUgs+3aRAZ9FmVQ9BTGWqlMe5RTaWkV5zgtKoYnmhgqepBYtl2As4SnpxAo0KtAJLbu27f75oZ8wupWHyUAeLPkIM5NbO/OkCfAdavex3NRP1Ah2rDZemDy0/9shIlmCRx91MJMbJwAt44fdpEhwxAaVOVZOMWw80BtmNlS13AAvnNKiMuNBwkBXlhYCRZObATJQg8IsIkTRZSA4gAwljCAhevR+AADmHV2whOkEEnkF2N94YSSMI7n5JNQdsChW1FWaeWV49VmAJZcduklT5bx9+WYZJb5YwFimqnmmlEeICSbcMYp55x01mnnnXjmqeeefPbp55+ABirooGvmReg2VHq1wDENNDleGEWAlaKTF6jIyAKWMhJHP45+hUAAwxQIZQy4EFDCcL516lIA1tyyqQCJarNOAgH4gICoDzQQgG88nKArlxto81itHG1apQq9fhKJTzjm+mn/DZE0esMIzGLSKI6mQCKSAAHsWAkUaHmxwgIjrFdHAw2IsCN7OGKiQFYK7IqhAuh6Ue6OKAbjxUw2nEhurunWoB4U/56oxjqw0nHrA28kEgCsAwTQHbEBLJECwyoAwQEIH/EQL2ERB+BLCgvs0g9BAywx8q661gCAxLvQ64uxa7igazLdllBrvAkk0s2mCn+EolU+53WrAAlgasYuCOcqMdAffeD0dYveAcYDD0vArbKiiJzjHQQkkBcQ64hUdh21/iqBxJ9wgPDZmUg8QrczNcPGyz6UYYQJdJQRQMWfuFA2adeIDQDZ5c0hwgw8DK32ArQymwvbaLfdNWon1EoA4augJJACE59X3sA0L9sQbD8EjL4DKJ2bFhYL2u2qtWn7ghrvCkBYDtWppXD+2O6D0J1sAmqo/bJp3MqeLDEICLgE3fKNgAEAZYzwBVSFQAKVGpuDNRzbe8SLOdwPlK4rB9wKEK8OxEAdb0GFnK5CvGqUXD3DfG/yciSbB6DDOqDiGlT+1z8tEE8UhdifB2jFqmAs4G/NYKALkre5XLWBbbqSnQOI1QTTUKAFXPjbCtb3Nx3sKxchS5kRMIGAEUKwfhCM1aFcVaKyoKpyM/wT3rahukrILod82hyufCWLeI0pAgA7') >= 0 and html.find(
                'Web Site Blocked') >= 0:
            return 'Sonicwall'
        if html.find('_Incapsula_Resource') >= 0:
            return 'Sitelock'
        return 0

    def construct_products_csv_file(self):
        title = "product_id,sku,parent_sku,name,qty,price,description,brand,condition,condition_note,price,msrp,seo_url,manufacturer,mpn,upc,ean,isbn,gtin,gcid,asin,epid,height,length,width,dimension_units,weight,weight_units,variation_1,variation_2,variation_3,variation_4,variation_5,product_image_1,product_image_2,product_image_3,product_image_4,product_image_5,product_image_6,product_image_7,product_image_8,product_image_9,product_image_10"
        return title.split(',')

    def construct_products_csv_bulk_edit(self):
        title = "product_id,sku,parent_id,parent_sku,name,qty,price,brand,height,length,width,dimension_units,weight,weight_units,product_image_1,product_image_2,product_image_3,product_image_4,product_image_5,product_image_6,product_image_7,product_image_8,product_image_9,product_image_10"
        return title.split(',')

    def get_image_limit(self):
        return to_int(self._state.channel.config.limit_image)

    def remove_duplicate_ds(self, url):
        url = url.replace("http://", "http:__")
        url = url.replace("https://", "https:__")
        url = url.replace('//', '/')
        url = url.replace('http:__', 'http://')
        url = url.replace('https:__', 'https://')
        return url

    def is_file_channel(self):
        return self.get_channel_type() == 'file'

    def is_csv_update(self):
        return self.is_file_channel() and self._state.channel.config.api.feed_type == 'update'

    def is_csv_add_new(self):
        return self.is_file_channel() and self._state.channel.config.api.feed_type == 'add'

    def is_staff_user(self):
        user_info = self.get_user_info()
        return user_info and to_int(user_info.get('group')) == 1

    def update_qty_for_parent(self, parent_id, channel_id=None):
        if not channel_id:
            channel_id = self.get_channel_id()
        variants = self.get_variants(
            self.get_model_catalog().get(parent_id), channel_id)
        qty = 0
        min_price = 0
        for variant in variants:
            variant_qty = to_int(variant.qty if self.is_channel_default(
            ) else variant.channel.get(f'channel_{channel_id}', {}).get('qty', variant.qty))
            variant_price = to_decimal(variant.price if self.is_channel_default(
            ) else variant.channel.get(f'channel_{channel_id}', {}).get('price', variant.price))
            qty += variant_qty
            if min_price < to_decimal(variant_price):
                min_price = to_decimal(variant_price)
        if channel_id == self.get_channel_default_id():
            update_data = {
                'qty': qty,
                "price": min_price,
                "updated_time": time.time()
            }
        else:
            update_data = {
                f'channel.channel_{self.get_channel_id()}.qty': qty,
                "channel.channel_{self.get_channel_id()}.price": min_price,
            }
        self.get_model_catalog().update(parent_id, update_data)

    def is_import_inactive(self):
        return self.is_import_product_by_status('inactive')

    def is_import_product_by_status(self, status):
        return self._request_data.get('import_all') or self._request_data.get(f'include_{status}') or self._state.pull.process.products.get(f'include_{status}')

    def is_difference_image(self, images_1, images_2):
        '''

        @param images_1: List[ProductImage]
        @param images_2: List[ProductImage]
        @return: boolean
        '''
        images_1_list = sorted([row.url for row in images_1])
        images_2_list = sorted([row.url for row in images_2])
        return images_1_list != images_2_list

    def get_order_number_prefix(self):
        number_prefix = self._state.channel.config.api.order_number_prefix or ''
        if not number_prefix and self._state.channel.config.setting.get('order', {}).get('order_number_prefix', ''):
            number_prefix = self._state.channel.config.setting.get(
                'order', {}).get('order_number_prefix', '')
        return number_prefix

    def get_order_number_suffix(self):
        return self._state.channel.config.api.order_number_suffix or ''

    def is_custom_manage_stock(self):
        if not self._state.channel.config.api.manage_stock:
            return None
        return self._state.channel.config.api.manage_stock == 'yes'

    def split_customer_fullname(self, fullname):
        first_name = ''
        last_name = ''
        fullname = to_str(fullname)
        customer_name = fullname.split(" ", 1)
        if len(customer_name) >= 2:
            first_name = customer_name[0]
            last_name = customer_name[1]
        else:
            customer_name = re.sub(r"([A-Z])", r" \1", fullname).split()
            if len(customer_name) >= 2:
                first_name = customer_name[0]
                del customer_name[0]
                last_name = ''.join(customer_name)
        if not first_name:
            first_name = fullname
        if not last_name:
            last_name = fullname
        return first_name, last_name

    def is_setting_sync_qty(self):
        return self._state.channel.config.setting.get('qty', {}).get('status') == 'enable'

    def is_setting_sync_price(self):
        return self._state.channel.config.setting.get('price', {}).get('status') == 'enable'

    def combination_from_multi_dict(self, data=None):
        if data is None:
            data = dict()
        data = list(data.values())
        result = list(product(*data))
        return result

    def copy_data_from_parent_product(self, parent):
        children_data = ProductVariant()
        no_copy = [
            'languages',
            'options',
            'group_parent_ids',
            'attributes',
            'variants',
            'group_child_ids',
            'relate',
            'seo', 'images', 'image', 'thumb_image', 'status',
            'description',
            'variant_count',
            'is_variant'
        ]
        for code, value in parent.items():
            if code not in no_copy:
                children_data[code] = value
        return children_data

    def get_price_children(self, price, addition_price, price_prefix='+'):
        if price_prefix == '-':
            new_price = to_decimal(price) - to_decimal(addition_price)
            return new_price if new_price > 0 else 0
        else:
            return to_decimal(price) + to_decimal(addition_price)
