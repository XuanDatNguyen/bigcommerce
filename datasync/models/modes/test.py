import os

from datasync.libs.mysql import Mysql
from datasync.libs.prodict import Prodict
from datasync.libs.response import Response
from datasync.libs.utils import to_len, get_root_path, parse_version
from datasync.models.mode import ModelMode


class ModelModesTest(ModelMode):
    _db: Mysql
    TABLE_PROCESS = "sync_process"
    TABLE_CHANNEL = "sync_channel"
    DB_VERSION = "1.0.0"

    def __init__(self):
        super().__init__()
        self._db = None

    def get_db(self):
        if self._db:
            return self._db
        self._db = Mysql()
        return self._db

    def set_db(self, _db):
        self._db = _db

    def query_raw(self, query):
        return self.get_db().query_raw(query)

    def dict_to_create_table_sql(self, dictionary):
        return self.get_db().dict_to_create_table_sql(dictionary)

    def dict_to_insert_condition(self, dictionary, allow_key=None):
        return self.get_db().dict_to_insert_condition(dictionary, allow_key)

    def dict_to_where_condition(self, dictionary):
        return self.get_db().dict_to_where_condition(dictionary)

    def dict_to_set_condition(self, dictionary):
        return self.get_db().dict_to_set_condition(dictionary)

    def list_to_in_condition(self, list_data):
        return self.get_db().list_to_in_condition(list_data)

    def insert_obj(self, table, data, insert_id=True):
        return self.get_db().insert_obj(table, data, insert_id)

    def insert_raw(self, query, insert_id=True):
        return self.get_db().insert_raw(query, insert_id)

    def update_obj(self, table, data, where=None):
        return self.get_db().update_obj(table, data, where)

    def select_obj(self, table, where, select_field=None):
        return self.get_db().select_obj(table, where, select_field)

    def insert_multiple_obj(self, table, data):
        return self.get_db().insert_multiple_obj(table, data)

    def select_page(self, table, where=None, select_field=None, limit=None, offset=None, order_by=None):
        return self.get_db().select_page(table, where, select_field, limit, offset, order_by)

    def count_table(self, table, where=None):
        return self.get_db().count_table(table, where)

    def select_row(self, table, where, select_field=None):
        obj = self.select_obj(table, where, select_field)
        data = obj.get('data', [])
        if data and to_len(data) > 0:
            return data[0]
        return False

    def select_raw(self, query):
        return self.get_db().select_raw(query)

    def delete_obj(self, table, where=None):
        return self.get_db().delete_obj(table, where)

    def escape(self, value):
        return self.get_db().escape(value)

    def get_table_name(self, table):
        return self.get_db().get_table_name(table)

    def setup(self):
        current_version = self.get_current_version()
        setup_version = self.setup_version()
        for setup in setup_version:
            if parse_version(current_version) < parse_version(setup['version']):
                getattr(self, setup['def'])()
        return

    def setup_100(self):
        table_migration_process = {
            'table': self.TABLE_PROCESS,
            'rows': {
                'id': 'BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY',
                'pid': "int(11) NULL",
                'server_id': "int(11) NULL",
                'state_id': "varchar(25) NULL",
                'status': "varchar(100) Null",
                'mode': "tinyint(4) DEFAULT 1",
                        'created_at': "timestamp NULL",
                        'updated_at': "timestamp NULL",
                        'type': "varchar(125) NULL",
                        'user_id': "int(11)",
                        'channel_id': "int(11)"

            },
        }
        table_channel = {
            'table': self.TABLE_CHANNEL,
            'rows': {
                'id': 'BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY',
                'type': "varchar(11) NOT NULL",
                'name': "varchar(25) NOT NULL",
                        'identifier': "varchar(255) NOT NULL",
                        'url': "varchar(255) NULL",
                        'user_id': "int(11)",
                        'api': "text NULL",
                        'position': "int(11)",
                        'sync_price': "tinyint(2) DEFAULT 2",
                        'sync_price_config': "varchar(255)",
                        'sync_qty': "tinyint(2) DEFAULT 2",
                        'sync_qty_config': "varchar(255)",
                        'created_at': "timestamp NULL",
                        'updated_at': "timestamp NULL",
                        'status': "varchar(255) DEFAULT 'connect'",
                        'default': "tinyint(2) DEFAULT 1"
            },
            'unique': (
                ('name', 'user_id'),
                ('identifier', 'type', 'user_id')
            )
        }
        table_warehouse = {
            'table': self.TABLE_CHANNEL,
            'rows': {
                'id': 'BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY',
                'name': "varchar(25) NOT NULL",
                'user_id': "int(11) NOT NULL",
                'address': "varchar(255) NOT NULL",
                        'address_2': "varchar(255) NULL",
                        'city': "varchar(25) NOT NULL",
                        'state': "varchar(25) NOT NULL",
                        'zipcode': "varchar(25) NOT NULL",
                        'country': "varchar(25) NOT NULL",
                        'created_at': "timestamp NULL",
                        'updated_at': "timestamp NULL",
                        'status': "tinyint(2) DEFAULT 1"
            },
            'unique': (
                ('name', 'user_id'),
            )
        }
        tables = (table_channel, table_migration_process, table_warehouse)
        for table in tables:
            query = self.dict_to_create_table_sql(table)
            if query['result'] != 'success':
                continue
            res = self.query_raw(query['query'])
            if res['result'] != 'success':
                continue
        version_file = self.get_version_file()
        with open(version_file, 'w') as log_file:
            log_file.write("1.0.0")

    def is_channel_exist(self, channel_type, identifier):
        where = {
            'type': channel_type,
            'identifier': identifier,
            'user_id': self._user_id
        }
        channel = self.select_row(self.TABLE_CHANNEL, where)
        return True if channel else False

    def is_channel_name_exist(self, channel_name):
        where = {
            'name': channel_name,
            'user_id': self._user_id
        }
        channel = self.select_row(self.TABLE_CHANNEL, where)
        return True if channel else False

    def create_channel(self, channel_id_exist=None):
        channel_data = self.get_channel_create_data()
        channel_check = self.select_row(
            self.TABLE_CHANNEL, {'user_id': self._user_id})
        if not channel_check:
            channel_data['default'] = 1
        channel_id = self.insert_obj(self.TABLE_CHANNEL, channel_data)['data']
        channel = self.select_obj(self.TABLE_CHANNEL, {'id': channel_id})
        channel_respon = {
            'id': channel['data'][0]['id'], 'position': channel['data'][0]['position']}
        return Response().success(channel_respon)

    def delete_channel(self, channel_id):
        return self.delete_obj(self.TABLE_CHANNEL, {'id': channel_id})

    def create_product_sync_process(self, state_id, channel_id_exist=None):
        process_data = self.get_process_create_data(state_id)
        process = self.insert_obj(self.TABLE_PROCESS, process_data)
        return process

    def delete_sync_process(self, sync_id):
        return self.delete_obj(self.TABLE_PROCESS, {'id': sync_id})

    def get_sync_info(self, sync_id):
        where = {
            'id': sync_id,
        }
        sync = self.select_row(self.TABLE_PROCESS, where)
        if not sync:
            return sync
        return Prodict(**sync)

    def save_sync(self, sync_id, **kwargs):
        return self.update_obj(self.TABLE_PROCESS, kwargs, {'id': sync_id})

    def setup_version(self):
        setup = (
            {
                'version': "1.0.0",
                'def': "setup_100"
            },
        )
        return setup

    def get_version_file(self):
        return os.path.join(get_root_path(), 'etc', 'version')

    def get_current_version(self):
        version_file = self.get_version_file()
        if not os.path.isfile(version_file):
            return "0.0.0"
        with open(version_file, "r") as file_version:
            current_version = file_version.readline()
        return current_version

    def get_all_channels(self):
        where = {
            'user_id': self._user_id
        }
        # if channel_id:
        # 	where['id'] = channel_id
        query = "SELECT tb1.state_id,tb1.id as sync_id, tb2.* FROM `{}` AS tb1 LEFT JOIN `{}` AS tb2 ON tb1.`channel_id` = tb2.`id` WHERE tb1.`user_id` = {}".format(
            self.TABLE_PROCESS, self.TABLE_CHANNEL, self._user_id)
        # if channel_id:
        # 	query += " AND tb2.`id` = {}".format(channel_id)
        channels = self.select_raw(query)
        if channels['result'] == 'success' and channels['data']:
            return channels['data']
        return ()

    def get_warehouse_locations(self):
        return [{"id": 1}]

    def get_warehouse_location_default(self):
        return 1

    def get_warehouse_location_fba(self):
        return 2

    def get_channel_by_id(self, channel_id):
        where = {
            'id': channel_id,
        }
        sync = self.select_row(self.TABLE_CHANNEL, where)
        if not sync:
            return sync
        return Prodict(**sync)

    def get_channel_default(self):
        params = {
            'default': 1,
            'user_id': self._user_id,
        }
        channel = self.select_row(self.TABLE_CHANNEL, params)
        if not channel:
            return False
        return channel

    def get_process_by_type(self, channel_id, process_type):
        params = {
            'type': process_type,
            'user_id': self._user_id,
            'channel_id': channel_id,
        }
        channel = self.select_row(self.TABLE_PROCESS, params)
        if not channel:
            return False
        return channel
